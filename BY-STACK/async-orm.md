# BY-STACK: Async ORM (SQLAlchemy AsyncSession)

## רלוונטיות — הקובץ הזה חל אם בפרויקט יש...
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

או נתק במפורש: `session.expunge(lead)` כדי לנתק (`lead.email` ממשיך לעבוד כ-primitive) — **לפני** הפעולה שיכולה לעשות rollback. באובייקט המנותק נשארים זמינים השדות שכבר נטענו; גישה לשדה שפג תוקפו או שלא נטען — אחרי ה-rollback, או אחרי commit קודם עם `expire_on_commit=True` — זורקת `DetachedInstanceError`. ו-`expunge` מוציא את האובייקט מהמעקב של ה-session: שינוי שעוד לא נשמר בו **לא ייכתב** ב-commit. כשהאובייקט עוד משתנה, או שיש בו שינוי שטרם נשמר — לחלץ primitives ולהשאיר אותו ב-session (נמדד ב-SQLAlchemy 2.1.8 עם asyncpg מול Postgres 16, נובמבר 2026: אובייקט ששונה ונותק לפני commit — הערך במסד לא השתנה).

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

## דפוס 3 — attributes אחרי commit בלולאה: `MissingGreenlet` או ערך ישן

```python
leads = (await session.scalars(select(Lead))).all()   # אובייקטי ORM, לא Row
for lead in leads:
  lead.processed = True
  await session.commit()
  process(lead.status)  # ❌ אחרי commit השדות פגי תוקף או ישנים — ראה למטה
```

ההתנהגות תלויה ב-`expire_on_commit` של ה-session. ב-`True` — ברירת המחדל — commit מסמן את **כל** האובייקטים ב-session כפגי תוקף, והגישה לשדה מנסה טעינה עצלה, שאינה נתמכת ב-async: `MissingGreenlet`. ב-`False` — ההגדרה שבדוגמאות של SQLAlchemy ל-`async_sessionmaker` — השדות נשארים עם הערכים מלפני ה-commit, גם אם המסד השתנה בינתיים. התיקון זהה בשני המצבים (נמדד ב-SQLAlchemy 2.1.8 עם asyncpg מול Postgres 16, נובמבר 2026).

### תיקון
```python
for lead in leads:
  lead.processed = True
  await session.commit()
  await session.refresh(lead)  # רענון מפורש אחרי commit — עמודות וקשרים שנטענים ב-eager
  process(lead.status)
```

‏`refresh` פועל על אובייקט ORM: על `Row` מ-`session.execute(select(...))` הוא זורק `UnmappedInstanceError`. ורענון כללי לא טוען קשר עצל (`lazy="select"`) — גישה ל-`lead.booking` אחריו עדיין זורקת `MissingGreenlet`. קשר נדרש נטען ב-`await session.refresh(lead, attribute_names=["booking"])`, מ-SQLAlchemy 2.0.4 (נמדד ב-SQLAlchemy 2.1.8 עם asyncpg מול Postgres 16, נובמבר 2026).

או קבץ את ה-commits מחוץ ללולאה.

### Commits אמיתיים
- EmailFlow `0e6dc85` — embedding job ניגש ל-attributes ישנים אחרי commit בתוך לולאה.

---

## דפוס 4 — singleton engine מקושר ל-event loop ב-Celery

Celery לא מריץ `async def` כ-task: הוא מחזיר coroutine שאיש לא מחכה לו, וגוף הפונקציה לא רץ בכלל (נבדק ב-Celery 5.7.0 עם `task_always_eager`: התוצאה היא אובייקט `coroutine`, ו-`RuntimeWarning: coroutine ... was never awaited`). לכן קוד async ב-Celery נכתב כ-task סינכרוני שעוטף `asyncio.run(...)` — וכל הרצה של task יוצרת event loop חדש.

```python
# module-level
engine = create_async_engine(...)
SessionLocal = async_sessionmaker(engine, ...)

async def _work():
  async with SessionLocal() as session:  # ❌ ב-task השני: חיבור מה-pool של loop שכבר נסגר
    ...

@app.task
def my_task():
  asyncio.run(_work())
```

ב-import לא נפתח שום חיבור. החיבור הראשון נפתח ב-task הראשון, נקשר ל-loop שלו, וחוזר ל-pool בסוף ה-task. ה-task השני רץ ב-loop חדש, מקבל מה-pool את אותו חיבור, ונופל ב-`RuntimeError: ... attached to a different loop` (נמדד ב-SQLAlchemy 2.1.8 עם asyncpg מול Postgres 16, נובמבר 2026: הריצה הראשונה עוברת, השנייה נופלת).

### תיקון
engine לכל task, שנסגר ב-`await engine.dispose()` בסוף ה-task — אחרי סגירת ה-session ולפני שה-loop נסגר. זו הצורה היחידה שעובדת גם כשה-tasks חופפים. ‏`engine.dispose()` בסוף כל task על engine משותף, או `poolclass=NullPool` — בלי pool אין חיבור שעובר בין loops — מספיקים רק כשה-tasks בתהליך רצים אחד-אחד (prefork): ברצף שניהם עברו, אבל עם ארבעה tasks מקבילים ב-threads (כמו `--pool=threads`), engine משותף נתקע עד ה-timeout בשלושת הווריאנטים — בלי `dispose`, עם `dispose` ועם `NullPool` — ו-engine לכל task עבר 60 מתוך 60 (אותה מדידה). או engine סינכרוני ב-Celery ואסינכרוני רק ב-API layer.
```python
async def _work():
  engine = create_async_engine(DATABASE_URL, ...)
  try:
    async with async_sessionmaker(engine)() as session:
      ...
  finally:
    await engine.dispose()

@app.task
def my_task():
  asyncio.run(_work())
```

### Commits אמיתיים
- Shipment-bot `0f30963`.

---

## דפוס 5 — `joinedload` + `with_for_update` ב-Postgres

```python
q = select(Lead).options(joinedload(Lead.booking)).with_for_update()  # ❌
```

‏`joinedload` נבנה כ-`LEFT OUTER JOIN`, ו-`with_for_update()` בלי `of` נועל את כל הטבלאות בשאילתה. Postgres דוחה: `FOR UPDATE cannot be applied to the nullable side of an outer join`. השגיאה מגיעה מה-DB, עטופה ב-`DBAPIError` — לא מ-SQLAlchemy.

### תיקון
כשהקשר אופציונלי — לנעול רק את הטבלה הראשית, ולהשאיר את ה-LEFT JOIN:
```python
q = select(Lead).options(joinedload(Lead.booking)).with_for_update(of=Lead)
```

‏`contains_eager` עם `join` מפורש גם הוא עובד, אבל זה `INNER JOIN` — שורה בלי קשר **נעלמת מהתוצאה בשקט**. נכון רק כשהקשר חובה:
```python
q = select(Lead).options(contains_eager(Lead.booking)).join(Booking).with_for_update()
```

אותו דבר `joinedload(Lead.booking, innerjoin=True)`, כשאין בשאילתה outer join אחר. ושתי צורות ה-INNER JOIN, בלי `of`, נועלות גם את שורות הטבלה המקושרת — חיבור שני לא הצליח לנעול את ה-booking (`could not obtain lock on row`), ועם `of=Lead` הצליח.

נמדד ב-SQLAlchemy 2.1.8 עם asyncpg מול Postgres 16, נובמבר 2026, על שני לידים שלאחד מהם אין booking: הצורה הראשונה נופלת בשגיאה, `of=Lead` מחזיר את שניהם, ו-`contains_eager` עם `join` מחזיר אחד.

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
