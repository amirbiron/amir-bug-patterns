# postgres-null-cas

זהה דפוסי CAS / `UPDATE ... WHERE col = :value` ב-Postgres שנכשלים בשקט על `NULL` כי `col = NULL` מוערך כ-`NULL` (לא `TRUE`).

## דווח כשמתקיימים כל הבאים

1. statement של `UPDATE` (או `DELETE`) משתמש בסעיף `WHERE` שכולל `col = :param` (דפוס CAS / optimistic-lock).
2. `col` הוא nullable ב-schema (או יכול להיות NULL לפי הגדרת ה-model / migrations).
3. קוד האפליקציה יכול להעביר `None` / `null` ל-`:param`.
4. אין הסתעפות `if value is None: where = col.is_(None)` / fallback של `IS NULL`.

## דפוסים ספציפיים ל-SQLAlchemy

- `update(M).where(M.col == :value)` — דווח.
- תיקון: `M.col.is_(None) if value is None else M.col == value`.

## Gotchas אחרים של Postgres NULL ב-scope

- `NOT IN (NULL, ...)` מחזיר NULL (מטופל כ-FALSE) — הוצא NULL דרך `WHERE col IS NOT NULL AND col NOT IN (...)`.
- `WHERE col = ANY(:array)` לא תופס אלמנטים של NULL במערך.

## False positives

- העמודה היא `NOT NULL` ב-schema וב-migrations.
- פעולות ORM `session.merge(...)` (לא CAS גולמי).
- ה-CAS branch הוא מכוון (למשל "עדכן רק כשהוגדר קודם" — צריך להיות מתועד).

## חומרה

HIGH — CAS תקוע בלולאה, cursor לעולם לא מתקדם, retries אינסופיים.
