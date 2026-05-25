# migration-model-drift

Detect schema-versioning drift between migration files and ORM model `__table_args__`. Fresh DB builds (test, dev, prod-from-scratch) end up with a different schema than production after incremental migrations.

## Flag when ANY apply

1. `op.create_index(...)` / `op.create_check_constraint(...)` / `op.create_unique_constraint(...)` in a migration without a matching `Index(...)` / `CheckConstraint(...)` / `UniqueConstraint(...)` in the corresponding model's `__table_args__`.

2. `op.drop_column(...)` in a migration in the same PR where the model still declares the column or other code still references it. (DROP must be in a SEPARATE later migration after code is fully removed.)

3. Alembic revision id (filename or `revision` variable) longer than 30 characters. Default `alembic_version.version_num` is `VARCHAR(32)`; fresh deploy fails.

4. `ADD COLUMN IF NOT EXISTS` in a MySQL migration (PG-only syntax).

5. Migration `ALTER TABLE` on a table that doesn't exist yet in any previous migration's `CREATE TABLE` (fresh-deploy failure).

6. `String(N)` / `VARCHAR(N)` column populated from an enum where `N < max(len(value) for value in Enum)`.

7. `Integer` column for external IDs (Telegram, Discord, Stripe customer IDs) that can exceed 2³¹ — should be `BigInteger`.

## False positives

- Data-only migrations (backfill, fixup) with no schema change.
- Test fixtures with `extend_existing=True`.
- Manually-managed indexes (rare; should be documented).

## Severity

MEDIUM — fresh DB builds (CI, dev, new prod) diverge from migrated prod; constraint / index missing on fresh deploys.
