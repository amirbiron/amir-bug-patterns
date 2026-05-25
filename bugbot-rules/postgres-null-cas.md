# postgres-null-cas

Detect Postgres CAS / `UPDATE ... WHERE col = :value` patterns that silently fail on `NULL` because `col = NULL` evaluates to `NULL` (not `TRUE`).

## Flag when ALL apply

1. An `UPDATE` (or `DELETE`) statement uses a `WHERE` clause that includes `col = :param` (CAS / optimistic-lock pattern).
2. `col` is nullable in the schema (or could be NULL based on the model definition / migrations).
3. The application code can pass `None` / `null` for `:param`.
4. There is no branching `if value is None: where = col.is_(None)` / `IS NULL` fallback.

## SQLAlchemy-specific patterns

- `update(M).where(M.col == :value)` — flag.
- Fix: `M.col.is_(None) if value is None else M.col == value`.

## Other Postgres NULL gotchas in scope

- `NOT IN (NULL, ...)` returns NULL (treated as FALSE) — exclude NULL via `WHERE col IS NOT NULL AND col NOT IN (...)`.
- `WHERE col = ANY(:array)` doesn't match NULL elements of the array.

## False positives

- Column is `NOT NULL` in schema and migrations.
- ORM `session.merge(...)` operations (not raw CAS).
- The CAS branch is intentional (e.g., "only update when previously set" — should be documented).

## Severity

HIGH — CAS stuck in a loop, cursor never advances, infinite retries.
