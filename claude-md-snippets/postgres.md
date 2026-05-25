# Postgres / SQL patterns (paste into CLAUDE.md)

1. **`col = NULL` is NULL, not TRUE.** CAS / `UPDATE WHERE col=:val` doesn't match `NULL` rows. Branch in app code: `col.is_(None)` when value is `None`.

2. **`VARCHAR(N)` ≥ max enum value length** — verified by CI test. SQLite (dev) doesn't enforce length, Postgres does.

3. **External IDs need `BigInteger`.** Telegram, Discord, Stripe, GitHub IDs exceed 2³¹.

4. **Every `ORDER BY` paired with `LIMIT` / `OFFSET` / cursor needs a tiebreaker** — usually `Model.id.desc()` after the semantic field. Otherwise pagination duplicates / skips rows with identical primary values.

5. **`LIKE` on user input:** `column.startswith(value, autoescape=True)` (SQLAlchemy) or escape `_` and `%` manually + `LIKE :p ESCAPE '\'`. Or use `=`.

6. **`ANY(:ids)` / `IN` type cast:** Postgres won't implicitly cast string array to UUID. Convert in Python or `cast(col, String) == any_(...)`.

7. **Python string ops (`.strip()`, `.lower()`) on `Column` are no-ops in SQL.** Use `func.trim(col)`, `func.lower(col)`.

8. **Truthy on DB strings:** whitespace `"  "` is truthy in Python but blank in edit flow. Use `(val or "").strip()` before checks.

9. **Migrations:** every `Index` / `CheckConstraint` / `UniqueConstraint` in migration MUST mirror in model `__table_args__`. Alembic revision id ≤ 30 chars. MySQL has no `ADD COLUMN IF NOT EXISTS`. `DROP COLUMN` goes in a separate migration after code stops referencing the column.

10. **`postgresql_ops` is for operator classes, NOT sort direction.** Use `desc("col")` for indexed-descending.

See `BY-STACK/postgres.md`.
