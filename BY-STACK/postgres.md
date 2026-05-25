# BY-STACK: Postgres (SQL, migrations, pagination, indexes)

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...
- ✅ PostgreSQL (רוב הקובץ הזה ספציפי ל-PG)
- ✅ כל DB של SQL עם queries של `LIKE` על קלט משתמש (K8 חל באופן רחב)
- ✅ Alembic migrations (דפוס 5 — model drift)
- ✅ MySQL — קרא דפוס 5 (MySQL לא תומך ב-`ADD COLUMN IF NOT EXISTS`)
- ✅ דפדוף דרך `LIMIT` / `OFFSET` או cursor
- ⏭ דלג אם: NoSQL בלבד (MongoDB יש לה gotchas שונים — ראה footnote בדפוס 8)

> Cross-link: **CRITICAL K8** (LIKE wildcard injection) ו-**CORE U4** + **U6** הם הדפוסים הבסיסיים. הקובץ הזה מקפל פנימה את **R2** (pagination tiebreaker).

---

## דפוס 1 — סמנטיקת NULL ב-CAS (CORE U4)

```sql
UPDATE subscription SET history_id = :new WHERE id = :id AND history_id = :expected_old;
```
אם `history_id` הוא `NULL` בשורה ו-`:expected_old` הוא `NULL`, ההשוואה `=` מוערכת כ-`NULL`, מטופל כ-`FALSE` → לא נתפסה שורה → CAS נראה כושל → cursor תקוע לנצח.

### תיקון
הסתעפות בקוד האפליקציה:
```python
if expected_old is None:
  where = Subscription.history_id.is_(None)
else:
  where = Subscription.history_id == expected_old
```

### Commits אמיתיים
- Noa `cf99698`.

---

## דפוס 2 — `VARCHAR(N)` קטן מדי לערך enum (CORE U4)

```python
class Source(StrEnum):
  WHATSAPP = "whatsapp"
  EMAIL_PROVIDER = "email_provider"  # 14 chars

class Lead(Base):
  source = Column(String(10), ...)  # ❌ "email_provider" > 10
```
נכון ב-dev על SQLite (אין אכיפת אורך), נכשל ב-INSERT של Postgres בפרודקשן.

### כלל לזיהוי
- טסט CI: לכל עמודת `String(N)` שמתמלאת מ-enum, ודא `N >= max(len(v) for v in EnumClass)`.
- או השתמש ב-`Enum(EnumClass)` ישירות (יוצר טיפוס enum של PG או עמודת טקסט עם check constraint).

### Commits אמיתיים
- Noa `2c8263a`.

---

## דפוס 3 — עמודת Integer קטנה מדי ל-IDs חיצוניים

```python
class Message(Base):
  telegram_user_id = Column(Integer, ...)  # ❌ 2^31 לא מספיק
```

Telegram, Discord, Stripe, GitHub IDs יכולים לחרוג מ-2³¹.

### תיקון
השתמש ב-`BigInteger` (`BIGINT`).

### Commits אמיתיים
- Shipment-bot `b16b99f`.

---

## דפוס 4 — `ORDER BY` בלי tiebreaker משני (R2)

```python
q = (
  select(Lead)
    .order_by(Lead.updated_at.desc())  # ❌
    .limit(20).offset(40)
)
```
שני leads עם `updated_at` זהה מקבלים סדר לא מוגדר. דפדוף בין דפים יכול לדלג או להכפיל אחד מהם.

### תיקון
```python
q = (
  select(Lead)
    .order_by(Lead.updated_at.desc(), Lead.id.desc())
    .limit(20).offset(40)
)
```

ל-CAS עם סמנטיקת "latest", ה-selector וה-verifier חייבים להשתמש באותו tuple.

### Commits אמיתיים
- EmailFlow `d84daca`, `3987818`, `a0c4603`.
- Shipment-bot `c0c1b74`.

---

## דפוס 5 — סטייה בין migration ל-model (CORE U6)

**חומרה:** MEDIUM (deploys טריים — test, dev, prod-from-scratch — מתפצלים מ-prod ממוגרר).

### כשלים נפוצים
- `op.create_index(...)` ב-migration אבל לא ב-`__table_args__` של המודל. ל-DB טרי אין index.
- `CheckConstraint("a > b")` ב-migration אבל `CheckConstraint("b < a")` (לוגית זהה) במודל. Postgres מנרמל שתי הצורות אבל השמות שונים → autogenerate רואה constraint "חסר".
- `DROP COLUMN` ב-migration אבל הקוד עדיין מתייחס לעמודה.
- revision id של Alembic ארוך מ-32 chars → migration נכשל ב-deploy טרי (ברירת מחדל `VARCHAR(32)` ב-`alembic_version`).
- פרויקטי MySQL: `ADD COLUMN IF NOT EXISTS` לא קיים (PG-only).
- חסר CREATE TABLE ל-migration של fresh-deploy שמתחיל ב-ALTER.

### כלל לזיהוי
1. כל constraint/index ב-migration → שקף אותו ב-`__table_args__`.
2. `DROP COLUMN` ב-PR שמוסיף attribute למודל (או משאיר הפניה קיימת) → דווח.
3. revision id ≤ 30 chars.
4. פרויקטי MySQL: אסור `ADD COLUMN IF NOT EXISTS` דרך grep; החלף ב-`try/except` או migration one-shot.
5. migrations הם additive כשהקוד הישן עדיין משתמש בעמודה.

### Commits אמיתיים
- EmailFlow `40f855d`, `a3a3134`, `cea815d`, `f143e1c`, `3f43d91`.
- routine `80c1fc4`, `7a4e879`, `230e0c1`.
- Noa `2c8263a` (וריאציה של אורך עמודה).
- Shipment-bot `b16b99f` (וריאציה של טיפוס עמודה).

---

## דפוס 6 — `LIKE` wildcard injection בקלט משתמש (CRITICAL K8)

```python
session.execute(select(Config).where(Config.key.like(f"{user_prefix}%")))  # ❌
```
prefix של משתמש `"test_key"` תופס `"test_key_foo"` וגם `"testXkey_foo"`. prefix של `"%"` תופס הכל.

### תיקון
- SQLAlchemy: `Config.key.startswith(user_prefix, autoescape=True)`.
- Raw SQL: ברח מ-`_`, `%`, ומתו ה-escape בקלט, ואז `LIKE :p ESCAPE '\\'`.
- או השתמש ב-`=` מדויק אם חיפוש prefix לא נדרש.

### Commits אמיתיים
- Facebook-Leads-New `2f45eca`.

---

## דפוס 7 — `ANY(:ids)` / `IN` עם אי-התאמת טיפוס

```python
session.execute(select(Lead).where(Lead.id == any_(string_ids)))  # ❌ אם Lead.id הוא UUID
```

Postgres לא יבצע cast מרומז ממערך מחרוזות למערך UUID.

### תיקון
המר ל-UUIDs לפני העברה, או cast ב-SQL: `cast(Lead.id, String) == any_(string_ids)`.

### Commits אמיתיים
- Noa `244286d`.

---

## דפוס 8 — SQLAlchemy `postgresql_ops` בשימוש שגוי ככיוון מיון

```python
class Lead(Base):
  __table_args__ = (
    Index("ix_lead_created", "created_at", postgresql_ops={"created_at": "DESC"}),  # ❌
  )
```

`postgresql_ops` הוא למחלקות אופרטור (`text_pattern_ops`, `varchar_pattern_ops`), לא כיוון מיון.

### תיקון
```python
from sqlalchemy import desc
Index("ix_lead_created_desc", desc("created_at"))
```

### Commits אמיתיים
- Noa `98e8d18`.

---

## דפוס 9 — פעולות מחרוזת של Python על Column expressions

```python
q = select(Lead).where(Lead.email.strip() == "x@example.com")  # ❌
```

`.strip()` רץ על metadata של אובייקט Column (no-op ב-SQL), לא ב-query.

### תיקון
```python
from sqlalchemy import func
q = select(Lead).where(func.trim(Lead.email) == "x@example.com")
```

### Commits אמיתיים
- EmailFlow `dfdf975`.

---

## דפוס 10 — בדיקת truthy מול `IS NULL` בעמודות מחרוזת

```python
if lead.notes:  # רווח לבן "  " הוא truthy ב-Python
  process(lead.notes)
```

אם flow העריכה מנרמל input ריק ל-`NULL`, שתי הייצוגים נסחפים. השתמש בנרמול מפורש:
```python
notes = (lead.notes or "").strip()
if notes:
  process(notes)
```

### Commits אמיתיים
- Noa `7444dd9`.

---

## Footnote — DBs אחרים

- **MySQL:** אין `ADD COLUMN IF NOT EXISTS`. CHECK constraints לא נאכפים לפני 8.0.16. `utf8` אינו UTF-8 אמיתי (השתמש ב-`utf8mb4`). פרודקשן דורש SSL config מפורש (routine `230e0c1`).
- **MongoDB:** aggregation pipeline בלי `{allowDiskUse: true}` פוגע ב-100MB RAM limit על `$sort` (CodeBot `4824ad9`). תמיד העבר את זה לכל pipeline לא טריוויאלי.

---

## הפניות צולבות

- **CORE U4** — Postgres edge cases (הקובץ הזה הוא ה-deep-dive)
- **CORE U6** — Migration drift (מקופל פנימה כאן)
- **R2** — דפדוף עם tiebreaker (מקופל פנימה כאן)
- **CRITICAL K8** — LIKE injection
- **`bugbot-rules/postgres-null-cas.md`**, **`pagination-tiebreaker.md`**, **`migration-model-drift.md`**, **`like-wildcard-injection.md`**
