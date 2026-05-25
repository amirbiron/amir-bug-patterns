# BY-STACK: Async ORM (SQLAlchemy AsyncSession)

## Relevance — copy this file if your project has...
- ✅ SQLAlchemy `AsyncSession` / `async_sessionmaker` / `create_async_engine`
- ✅ FastAPI or aiohttp with async DB writes
- ✅ Celery / RQ tasks using async SQLAlchemy
- ✅ Code that does `await session.commit()` inside a loop
- ✅ Code that uses `asyncio.gather` with DB operations
- ⏭ Skip if: sync SQLAlchemy only, or non-Python ORMs (Prisma, Knex, etc. — different rules)

---

## Pattern 1 — `MissingGreenlet` after rollback (R1)

**Severity:** MEDIUM — crashes; sometimes silent data corruption

### What it looks like
```python
try:
  await session.execute(...)
  await session.commit()
except SomeError:
  await session.rollback()
  logger.error("failed for lead %s", lead.email)  # ❌ MissingGreenlet
```
After `rollback()`, all ORM objects in the session are expired. Accessing `lead.email` triggers a lazy load — but we're outside a greenlet context now.

### Fix
Extract primitives before any operation that can rollback:
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

Or expunge explicitly: `session.expunge(lead)` to detach (`lead.email` keeps working as a primitive).

### Real commits
- EmailFlow `0fdd247`.
- Shipment-bot `85d7a8e` — loop over `expiring` deliveries after `db.commit()` triggered `MissingGreenlet` re-reading attrs.

---

## Pattern 2 — Sharing an AsyncSession across `asyncio.gather`

```python
async def process_all(session, items):
  await asyncio.gather(*[process(session, item) for item in items])  # ❌
```
`AsyncSession` is not task-safe. Concurrent tasks corrupt the session's internal state.

### Fix
Each task opens its own session:
```python
async def process_all(sessionmaker, items):
  async def one(item):
    async with sessionmaker() as session:
      await process(session, item)
  await asyncio.gather(*[one(item) for item in items])
```

### Real commits
- EmailFlow `018b166`.

---

## Pattern 3 — Stale attributes after in-loop commit

```python
for row in await session.execute(...):
  await session.commit()  # commits any pending changes
  process(row.related_field)  # ❌ may be stale (commit refreshes only PK)
```

### Fix
```python
for row in ...:
  await session.refresh(row)  # explicit refresh after commit
  process(row.related_field)
```

Or batch commits outside the loop.

### Real commits
- EmailFlow `0e6dc85` — embedding job accessed stale attrs after in-loop commit.

---

## Pattern 4 — Singleton engine bound to event loop in Celery

```python
# module-level
engine = create_async_engine(...)
SessionLocal = async_sessionmaker(engine, ...)

@app.task
async def my_task():
  async with SessionLocal() as session:  # ❌ engine bound to previous loop → second task fails
    ...
```

Celery creates a fresh event loop per task. Engines created at import time bind to whatever loop existed then.

### Fix
Lazy-create per task, or use `engine.dispose()` between tasks, or use a sync engine in Celery and async only at the API layer.
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

### Real commits
- Shipment-bot `0f30963`.

---

## Pattern 5 — `joinedload` + `with_for_update` incompatibility

```python
q = select(Lead).options(joinedload(Lead.booking)).with_for_update()  # ❌
```

SQLAlchemy raises (the eager load join can't be locked cleanly).

### Fix
```python
q = select(Lead).options(contains_eager(Lead.booking)).join(Booking).with_for_update()
```

### Real commits
- Shipment-bot `4352bac`.

---

## Pattern 6 — Python string ops on Column expressions

```python
q = select(Lead).where(Lead.email.strip() == "x@example.com")  # ❌
# .strip() runs on the Column object metadata, not in SQL — query semantics break
```

### Fix
```python
from sqlalchemy import func
q = select(Lead).where(func.trim(Lead.email) == "x@example.com")
```

### Real commits
- EmailFlow `dfdf975`.

---

## Pattern 7 — CAS on nullable column (CORE U1 + U4)

```python
result = await session.execute(
  update(Subscription)
    .where(Subscription.id == sid, Subscription.history_id == expected_old)  # ❌ doesn't match NULL
    .values(history_id=new_id)
)
```
If `expected_old` is `None` and the row has `history_id IS NULL`, `col = NULL` evaluates to `NULL` (not `TRUE`) → rowcount = 0 → cursor stuck forever.

### Fix
```python
if expected_old is None:
  where_clause = Subscription.history_id.is_(None)
else:
  where_clause = Subscription.history_id == expected_old

result = await session.execute(
  update(Subscription).where(Subscription.id == sid, where_clause).values(history_id=new_id)
)
```

### Real commits
- Noa `cf99698`.

---

## Pattern 8 — `ANY(:ids)` with type mismatch

```python
q = select(Lead).where(Lead.id == any_(string_array))  # ❌ if Lead.id is UUID
```

Postgres won't implicitly cast string array to UUID.

### Fix
Cast on either side:
```python
q = select(Lead).where(cast(Lead.id, String) == any_(string_array))
# or: pass uuid.UUID objects in string_array
```

### Real commits
- Noa `244286d`.

---

## Pattern 9 — Audit log on UPDATE failure (links to CORE U5)

When a CAS `UPDATE` returns `rowcount=0`, the side-effect didn't happen. But downstream consumers (cron, dashboards) infer state from the activity log. If you only log on success, they think the event never occurred → they take action (create task, send reminder) under the wrong assumption.

### Rule
For any UPDATE that can fail due to CAS / race / filter rejection:
```python
result = await session.execute(update(...).where(...))
if result.rowcount == 0:
  await log_activity(type=..., metadata={"applied": False, "reason": "race_or_stale"})
else:
  await log_activity(type=..., metadata={"applied": True})
```

### Real commits
- Noa `04cb101` — `_apply_reschedule` rowcount=0 left booking without activity → cron treated as never-happened.
- Noa `0aff4a1` — webhook returned changes=[] without persisting new sync_token → infinite loop.

---

## Cross-references

- **CORE U1** — Race conditions in async code (this file covers ORM-side specifics)
- **CORE U4** — Postgres NULL semantics in CAS
- **CORE U5** — Linked-field atomicity (the audit-log-on-failure pattern)
- **R1** — SQLAlchemy async session lifecycle (this file is the deep-dive)
- **`bugbot-rules/race-toctou.md`**, **`postgres-null-cas.md`**, **`linked-field-atomicity.md`**
