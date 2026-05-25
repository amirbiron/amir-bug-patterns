# Cron-job patterns (paste into CLAUDE.md)

1. **Every cron query needs an explicit terminal-state column.** Filter on `processing_status='done'` / `archived_at IS NOT NULL` / `done_at` — never on heuristics like `lead_id IS NULL` (terminal states like `spam`/`not_business` also have NULL), `attempts < MAX` (exhausted rows stay pending), or `status IN (...)` without checking what the action writes.

2. **When `attempts == MAX`, transition the row to a terminal state** (`status='failed'`, `processing_status='exhausted'`). Don't leave it `pending`.

3. **Action-vs-filter symmetry:** when the action succeeds, identify which `WHERE` condition becomes False. If the answer is "none guaranteed", add a column the action writes.

4. **Filter order: deny first, then business logic, then overrides.** Blocked / spam / fraud filters run BEFORE any `force_send` / `whitelist_override` check.

5. **Beat scheduler + ad-hoc dispatcher race:** atomic CAS update `UPDATE ... WHERE status='pending' RETURNING id`, check rowcount.

6. **Celery + async engine:** module-level engine binds to import-time loop → second task fails. Lazy-create per task, or `engine.dispose()` between.

7. **Sync calls in async cron block the event loop.** Wrap with `asyncio.to_thread(fn)` / `loop.run_in_executor`.

8. **Time edges:** validate hours 0-23 (not "24:00"); `max(timedelta(0), now - last_seen)` for clock-skew safety.

9. **In-memory dedup state has no eviction → memory leak.** Use TTL / LRU or Redis with `EXPIRE`.

10. **Single-source-of-truth state lives in DB, not module-level globals.** Cross-process imports diverge.

See `BY-STACK/cron-jobs.md` for code examples.
