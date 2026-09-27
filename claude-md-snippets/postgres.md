# דפוסי Postgres / SQL (להעתקה ל-CLAUDE.md)

1. **`col = NULL` הוא NULL, לא TRUE.** CAS / `UPDATE WHERE col=:val` לא תופס שורות `NULL`. הסתעפות בקוד אפליקציה: `col.is_(None)` כשהערך הוא `None`.

2. **`VARCHAR(N)` ≥ אורך ערך ה-enum המקסימלי** — מאומת על ידי טסט CI. SQLite (dev) לא אוכף אורך, Postgres כן.

3. **IDs חיצוניים צריכים `BigInteger`.** Telegram, Discord, Stripe, GitHub IDs חורגים מ-2³¹.

4. **כל `ORDER BY` משולב עם `LIMIT` / `OFFSET` / cursor צריך tiebreaker** — בדרך כלל `Model.id.desc()` אחרי השדה הסמנטי. אחרת דפדוף מכפיל / מדלג על שורות עם ערכים ראשיים זהים.

5. **`LIKE` על קלט משתמש:** `column.startswith(value, autoescape=True)` (SQLAlchemy) או escape ל-`_` ו-`%` ידנית + `LIKE :p ESCAPE '\'`. או השתמש ב-`=`.

6. **`ANY(:ids)` / `IN` cast של טיפוס:** Postgres לא יבצע cast מרומז ממערך מחרוזות ל-UUID. המר ב-Python או `cast(col, String) == any_(...)`.

7. **פעולות מחרוזת של Python (`.strip()`, `.lower()`) על `Column` הן no-ops ב-SQL.** השתמש ב-`func.trim(col)`, `func.lower(col)`.

8. **Truthy על מחרוזות DB:** רווח לבן `"  "` הוא truthy ב-Python אבל ריק ב-flow של עריכה. השתמש ב-`(val or "").strip()` לפני בדיקות.

9. **Migrations:** כל `Index` / `CheckConstraint` / `UniqueConstraint` ב-migration חייב לשקף ב-`__table_args__` של המודל. revision id של Alembic ≤ 30 chars. ל-MySQL אין `ADD COLUMN IF NOT EXISTS`. `DROP COLUMN` הולך ב-migration נפרד אחרי שהקוד הפסיק להתייחס לעמודה.

10. **`postgresql_ops` הוא למחלקות אופרטור, לא כיוון מיון.** השתמש ב-`desc("col")` ל-index יורד.

11. **עמודה שהורפתה ל-nullable — ספור את הקוראים.** `op.alter_column(..., nullable=True)` או `Mapped[X]` שהופך ל-`Mapped[X | None]` על עמודה קיימת: `grep` על שם העמודה בכל הריפו (כולל `jobs/` ו-SQL גולמי), ולכל קורא — לאן ה-`None` הולך (פרמטר `X`, עמודת `NOT NULL` בטבלה אחרת, מפתח במילון, סכמה עם שדה חובה). צרכני רקע ראשונים, וטיפול ב-`None` במסלול הקיים ולא בענף נפרד.

ראה `BY-STACK/postgres.md`.
