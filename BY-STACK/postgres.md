# BY-STACK: Postgres (SQL, migrations, pagination, indexes)

## Relevance — copy this file if your project has...
- ✅ PostgreSQL (the bulk of this file is PG-specific)
- ✅ Any SQL DB with `LIKE` queries on user input (K8 applies broadly)
- ✅ Alembic migrations (Pattern 5 — model drift)
- ✅ MySQL — read Pattern 5 (MySQL doesn't support `ADD COLUMN IF NOT EXISTS`)
- ✅ Pagination via `LIMIT` / `OFFSET` or cursor
- ⏭ Skip if: NoSQL only (MongoDB has different gotchas — see Pattern 8 footnote)

> Cross-link: **CRITICAL K8** (LIKE wildcard injection) and **CORE U4** + **U6** are the underlying patterns. This file folds in **R2** (pagination tiebreaker).

---

## Pattern 1 — NULL semantics in CAS (CORE U4)

```sql
UPDATE subscription SET history_id = :new WHERE id = :id AND history_id = :expected_old;
```
If `history_id` is `NULL` in the row and `:expected_old` is `NULL`, the `=` comparison evaluates to `NULL`, treated as `FALSE` → no row matched → CAS appears to fail → cursor stuck forever.

### Fix
Branch in application code:
```python
if expected_old is None:
  where = Subscription.history_id.is_(None)
else:
  where = Subscription.history_id == expected_old
```

### Real commits
- Noa `cf99698`.

---

## Pattern 2 — `VARCHAR(N)` too small for enum value (CORE U4)

```python
class Source(StrEnum):
  WHATSAPP = "whatsapp"
  EMAIL_PROVIDER = "email_provider"  # 14 chars

class Lead(Base):
  source = Column(String(10), ...)  # ❌ "email_provider" > 10
```
Develops fine on SQLite (no length enforcement), fails in Postgres production INSERT.

### Detection rule
- CI test: for every `String(N)` column populated from an enum, assert `N >= max(len(v) for v in EnumClass)`.
- Or use `Enum(EnumClass)` directly (creates a PG enum type or text column with check constraint).

### Real commits
- Noa `2c8263a`.

---

## Pattern 3 — Integer column too small for external IDs

```python
class Message(Base):
  telegram_user_id = Column(Integer, ...)  # ❌ 2^31 isn't enough
```

Telegram, Discord, Stripe, GitHub IDs can exceed 2³¹.

### Fix
Use `BigInteger` (`BIGINT`).

### Real commits
- Shipment-bot `b16b99f`.

---

## Pattern 4 — `ORDER BY` without secondary tiebreaker (R2)

```python
q = (
  select(Lead)
    .order_by(Lead.updated_at.desc())  # ❌
    .limit(20).offset(40)
)
```
Two leads with identical `updated_at` get unspecified order. Pagination across pages can skip or duplicate one of them.

### Fix
```python
q = (
  select(Lead)
    .order_by(Lead.updated_at.desc(), Lead.id.desc())
    .limit(20).offset(40)
)
```

For CAS with "latest" semantics, the selector and the verifier must use the same tuple.

### Real commits
- EmailFlow `d84daca`, `3987818`, `a0c4603`.
- Shipment-bot `c0c1b74`.

---

## Pattern 5 — Migration ↔ model drift (CORE U6)

**Severity:** MEDIUM (fresh DB builds — test, dev, prod-from-scratch — diverge from migrated prod).

### Common failures
- `op.create_index(...)` in migration but not in model's `__table_args__`. Fresh DB has no index.
- `CheckConstraint("a > b")` in migration but `CheckConstraint("b < a")` (logically same) in model. Postgres normalizes both forms but the names differ → autogenerate sees a "missing" constraint.
- `DROP COLUMN` in migration but code still references the column.
- Alembic revision id longer than 32 chars → migration fails on fresh deploy (default `VARCHAR(32)` in `alembic_version`).
- MySQL projects: `ADD COLUMN IF NOT EXISTS` doesn't exist (PG-only).
- Missing CREATE TABLE for a fresh-deploy migration that starts with ALTER.

### Detection rule
1. Every constraint/index in a migration → mirror it in `__table_args__`.
2. `DROP COLUMN` in same PR that adds the model attribute (or leaves an existing reference) → flag.
3. Revision id ≤ 30 chars.
4. MySQL projects: ban `ADD COLUMN IF NOT EXISTS` via grep; replace with `try/except` check or a one-shot migration.
5. Migrations are additive when old code still uses the column.

### Real commits
- EmailFlow `40f855d`, `a3a3134`, `cea815d`, `f143e1c`, `3f43d91`.
- routine `80c1fc4`, `7a4e879`, `230e0c1`.
- Noa `2c8263a` (column-length variant).
- Shipment-bot `b16b99f` (column-type variant).

---

## Pattern 6 — `LIKE` wildcard injection on user input (CRITICAL K8)

```python
session.execute(select(Config).where(Config.key.like(f"{user_prefix}%")))  # ❌
```
User prefix `"test_key"` matches `"test_key_foo"` AND `"testXkey_foo"`. Prefix `"%"` matches everything.

### Fix
- SQLAlchemy: `Config.key.startswith(user_prefix, autoescape=True)`.
- Raw SQL: escape `_`, `%`, and the escape char in the input, then `LIKE :p ESCAPE '\\'`.
- Or use exact `=` if prefix-search isn't required.

### Real commits
- Facebook-Leads-New `2f45eca`.

---

## Pattern 7 — `ANY(:ids)` / `IN` with type mismatch

```python
session.execute(select(Lead).where(Lead.id == any_(string_ids)))  # ❌ if Lead.id is UUID
```

Postgres won't implicitly cast a string array to a UUID array.

### Fix
Convert to UUIDs before passing, or cast in SQL: `cast(Lead.id, String) == any_(string_ids)`.

### Real commits
- Noa `244286d`.

---

## Pattern 8 — SQLAlchemy `postgresql_ops` misused as sort direction

```python
class Lead(Base):
  __table_args__ = (
    Index("ix_lead_created", "created_at", postgresql_ops={"created_at": "DESC"}),  # ❌
  )
```

`postgresql_ops` is for operator classes (`text_pattern_ops`, `varchar_pattern_ops`), not sort direction.

### Fix
```python
from sqlalchemy import desc
Index("ix_lead_created_desc", desc("created_at"))
```

### Real commits
- Noa `98e8d18`.

---

## Pattern 9 — Python string ops on `Column` expressions

```python
q = select(Lead).where(Lead.email.strip() == "x@example.com")  # ❌
```

`.strip()` runs on the Column object's metadata (no-op in SQL), not in the query.

### Fix
```python
from sqlalchemy import func
q = select(Lead).where(func.trim(Lead.email) == "x@example.com")
```

### Real commits
- EmailFlow `dfdf975`.

---

## Pattern 10 — Truthy check vs `IS NULL` on string columns

```python
if lead.notes:  # whitespace "  " is truthy in Python
  process(lead.notes)
```

If the edit flow normalizes blank input to `NULL`, the two representations drift. Use explicit normalization:
```python
notes = (lead.notes or "").strip()
if notes:
  process(notes)
```

### Real commits
- Noa `7444dd9`.

---

## Footnote — Other DBs

- **MySQL:** No `ADD COLUMN IF NOT EXISTS`. CHECK constraints aren't enforced before 8.0.16. `utf8` is not real UTF-8 (use `utf8mb4`). Production needs explicit SSL config (routine `230e0c1`).
- **MongoDB:** Aggregation pipeline without `{allowDiskUse: true}` hits a 100MB RAM limit on `$sort` (CodeBot `4824ad9`). Always pass it for any non-trivial pipeline.

---

## Cross-references

- **CORE U4** — Postgres edge cases (this file is the deep-dive)
- **CORE U6** — Migration drift (folded in here)
- **R2** — Pagination tiebreaker (folded in here)
- **CRITICAL K8** — LIKE injection
- **`bugbot-rules/postgres-null-cas.md`**, **`pagination-tiebreaker.md`**, **`migration-model-drift.md`**, **`like-wildcard-injection.md`**
