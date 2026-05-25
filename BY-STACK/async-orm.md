# BY-STACK: Async ORM (SQLAlchemy AsyncSession)

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...
- ✅ SQLAlchemy `AsyncSession` / `async_sessionmaker` / `create_async_engine`
- ✅ FastAPI או aiohttp עם כתיבות DB async
- ✅ Celery / RQ tasks שמשתמשים ב-SQLAlchemy async
- ✅ קוד שעושה `await session.commit()` בתוך לולאה
- ✅ קוד שמשתמש ב-`asyncio.gather` עם פעולות DB
- ⏭ דלג אם: רק SQLAlchemy סינכרוני, או ORMs לא של Python (Prisma, Knex, וכו' — כללים שונים)

---

## דפוס 1 — `MissingGreenlet` אחרי rollback (R1)

**חומרה:** MEDIUM — קריסות; לפעמים שחיתות נתונים שקטה

### איך זה נראה
```python
try:
  await session.execute(...)
  await session.commit()
except SomeError:
  await session.rollback()
  logger.error("failed for lead %s", lead.email)  # ❌ MissingGreenlet
```
אחרי `rollback()`, כל אובייקטי ה-ORM ב-session expired. גישה ל-`lead.email` מפעילה lazy load — אבל אנחנו מחוץ ל-greenlet context עכשיו.

### תיקון
חלץ primitives לפני כל פעולה שיכולה לעשות rollback:
```python
lead_id = lead.id
lead_email = lead.email
try:
  await session.execute(...)
  await session.commit()
except SomeError:
  await session.rollback()
  logger.error("failed for lead %s", lead_email)  # ✅
```

או נתק במפורש: `session.expunge(lead)` כדי לנתק (`lead.email` ממשיך לעבוד כ-primitive).

### Commits אמיתיים
- EmailFlow `0fdd247`.
- Shipment-bot `85d7a8e` — לולאה על `expiring` deliveries אחרי `db.commit()` הפעילה `MissingGreenlet` בקריאת attrs מחדש.

---

## דפוס 2 — שיתוף AsyncSession בין `asyncio.gather`

```python
async def process_all(session, items):
  await asyncio.gather(*[process(session, item) for item in items])  # ❌
```
`AsyncSession` אינו task-safe. tasks concurrent משחיתים את ה-state הפנימי של ה-session.

### תיקון
כל task פותח את שלו:
```python
async def process_all(sessionmaker, items):
  async def one(item):
    async with sessionmaker() as session:
      await process(session, item)
  await asyncio.gather(*[one(item) for item in items])
```

### Commits אמיתיים
- EmailFlow `018b166`.

---

## דפוס 3 — attributes ישנים אחרי commit בלולאה

```python
for row in await session.execute(...):
  await session.commit()  # commits any pending changes
  process(row.related_field)  # ❌ עלול להיות ישן (commit מרענן רק PK)
```

### תיקון
```python
for row in ...:
  await session.refresh(row)  # רענון מפורש אחרי commit
  process(row.related_field)
```

או קבץ את ה-commits מחוץ ללולאה.

### Commits אמיתיים
- EmailFlow `0e6dc85` — embedding job ניגש ל-attributes ישנים אחרי commit בתוך לולאה.

---

## דפוס 4 — singleton engine מקושר ל-event loop ב-Celery

```python
# module-level
engine = create_async_engine(...)
SessionLocal = async_sessionmaker(engine, ...)

@app.task
async def my_task():
  async with SessionLocal() as session:  # ❌ engine מקושר ל-loop קודם → task שני נכשל
    ...
```

Celery יוצר event loop טרי לכל task. Engines שנוצרו ב-import time מקושרים ל-loop שהיה קיים אז.

### תיקון
יצירה lazy לכל task, או `engine.dispose()` בין tasks, או השתמש ב-engine סינכרוני ב-Celery ובאסינכרוני רק ב-API layer.
```python
@app.task
async def my_task():
  engine = create_async_engine(DATABASE_URL, ...)
  try:
    async with async_sessionmaker(engine)() as session:
      ...
  finally:
    await engine.dispose()
```

### Commits אמיתיים
- Shipment-bot `0f30963`.

---

## דפוס 5 — `joinedload` + `with_for_update` לא תואמים

```python
q = select(Lead).options(joinedload(Lead.booking)).with_for_update()  # ❌
```

SQLAlchemy זורק (ה-join של eager load לא יכול להינעל באופן נקי).

### תיקון
```python
q = select(Lead).options(contains_eager(Lead.booking)).join(Booking).with_for_update()
```

### Commits אמיתיים
- Shipment-bot `4352bac`.

---

## דפוס 6 — פעולות מחרוזת של Python על Column expressions

```python
q = select(Lead).where(Lead.email.strip() == "x@example.com")  # ❌
# .strip() רץ על metadata של Column, לא ב-SQL — סמנטיקת ה-query נשברת
```

### תיקון
```python
from sqlalchemy import func
q = select(Lead).where(func.trim(Lead.email) == "x@example.com")
```

### Commits אמיתיים
- EmailFlow `dfdf975`.

---

## דפוס 7 — CAS על עמודה nullable (CORE U1 + U4)

```python
result = await session.execute(
  update(Subscription)
    .where(Subscription.id == sid, Subscription.history_id == expected_old)  # ❌ לא תופס NULL
    .values(history_id=new_id)
)
```
אם `expected_old` הוא `None` ולשורה יש `history_id IS NULL`, `col = NULL` מוערך כ-`NULL` (לא `TRUE`) → rowcount = 0 → cursor תקוע לעד.

### תיקון
```python
if expected_old is None:
  where_clause = Subscription.history_id.is_(None)
else:
  where_clause = Subscription.history_id == expected_old

result = await session.execute(
  update(Subscription).where(Subscription.id == sid, where_clause).values(history_id=new_id)
)
```

### Commits אמיתיים
- Noa `cf99698`.

---

## דפוס 8 — `ANY(:ids)` עם אי-התאמת טיפוס

```python
q = select(Lead).where(Lead.id == any_(string_array))  # ❌ אם Lead.id הוא UUID
```

Postgres לא יבצע cast מרומז ממערך מחרוזות למערך UUID.

### תיקון
Cast בשני הצדדים:
```python
q = select(Lead).where(cast(Lead.id, String) == any_(string_array))
# או: העבר אובייקטי uuid.UUID ב-string_array
```

### Commits אמיתיים
- Noa `244286d`.

---

## דפוס 9 — Audit log בכשל UPDATE (מקושר ל-CORE U5)

כש-CAS `UPDATE` מחזיר `rowcount=0`, ה-side-effect לא קרה. אבל צרכנים downstream (cron, dashboards) מסיקים state מ-activity log. אם לוגים רק על הצלחה, הם חושבים שה-event לא קרה → לוקחים פעולה (יוצרים task, שולחים תזכורת) בהנחה השגויה.

### כלל
לכל UPDATE שיכול להיכשל עקב CAS / race / דחיית filter:
```python
result = await session.execute(update(...).where(...))
if result.rowcount == 0:
  await log_activity(type=..., metadata={"applied": False, "reason": "race_or_stale"})
else:
  await log_activity(type=..., metadata={"applied": True})
```

### Commits אמיתיים
- Noa `04cb101` — `_apply_reschedule` עם rowcount=0 השאיר booking בלי activity → cron התייחס לזה כאילו לא קרה.
- Noa `0aff4a1` — webhook החזיר changes=[] בלי לשמור sync_token חדש → לולאה אינסופית.

---

## הפניות צולבות

- **CORE U1** — race conditions בקוד async (הקובץ הזה מכסה ספציפיות צד-ORM)
- **CORE U4** — סמנטיקת NULL של Postgres ב-CAS
- **CORE U5** — atomicity של linked-field (דפוס audit-log-on-failure)
- **R1** — lifecycle של AsyncSession ב-SQLAlchemy (הקובץ הזה הוא ה-deep-dive)
- **`bugbot-rules/race-toctou.md`**, **`postgres-null-cas.md`**, **`linked-field-atomicity.md`**
