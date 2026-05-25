# Async SQLAlchemy patterns (paste into CLAUDE.md)

1. **One AsyncSession per task.** Never pass the same session to multiple coroutines via `asyncio.gather` / `asyncio.create_task` — sessions are not task-safe. Each task opens its own:
   ```python
   async with sessionmaker() as session: ...
   ```

2. **No ORM attribute access after `await session.rollback()`.** Extract primitives (`.id`, `.email`) **before** the try-block, or `session.expunge(obj)` to detach.

3. **`await session.commit()` inside a loop → `await session.refresh(row)` before re-reading attributes.** Commit refreshes only the PK by default.

4. **Celery + async engine:** module-level engine binds to import-time loop → second task fails. Lazy-create per task, or call `engine.dispose()` between tasks.

5. **`joinedload` + `with_for_update` is incompatible** → use `contains_eager` + explicit join.

6. **Python string ops on `Column` expressions are silent no-ops** in SQL. Use `func.trim(col)`, `func.lower(col)`.

7. **CAS on nullable column needs `IS NULL` branch.** `WHERE col = NULL` evaluates to `NULL`, not `TRUE`. In SQLAlchemy: `col.is_(None)` when value is `None`.

8. **On `UPDATE` `rowcount=0` (CAS rejection), still log activity with `metadata.applied=false`.** Downstream cron / dashboards depend on the log to know events happened.

See `BY-STACK/async-orm.md` for code examples.
