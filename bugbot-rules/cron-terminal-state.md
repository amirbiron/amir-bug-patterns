# cron-terminal-state

Detect scheduled / cron jobs whose main query filter can never become False after successful processing — leading to infinite reprocessing, duplicate side-effects, and API quota burn.

## Flag when ALL apply

1. Code is a periodic / scheduled task (Celery beat task, APScheduler job, cron-invoked script, `setInterval` server-side handler, Render cron entry).
2. The task runs a query (`SELECT ... WHERE ...`) and acts on each row (`UPDATE`, `INSERT`, external call).
3. The `WHERE` clause uses one of these incomplete-signal heuristics:
   - `column IS NULL` where terminal states (spam, rejected, abandoned) also have NULL for that column.
   - `attempts < MAX_ATTEMPTS` where exhausted rows (`attempts == MAX_ATTEMPTS`) stay in the same status forever.
   - `status IN (...)` without verifying the action actually moves the row out of the filter set.
4. The action does NOT write a column that guarantees exit from the filter set.

## Required exit conditions

Every cron query must filter on a column that the action **explicitly writes** on success:
- `processing_status = 'pending'` → after success, action sets `'done'`.
- `done_at IS NULL` → after success, action sets `done_at = now()`.
- `attempts < MAX` AND when `attempts == MAX`, transition to terminal state (`status='failed'`).

## Related: filter scope errors

Also flag in the same review pass:
- Filter applied AFTER an "override / force-send" check (blocked users should always be filtered first).
- Filter too narrow that excludes legitimate cases (e.g., `channel='whatsapp'` filter missing email-pref leads).

## False positives

- Reporting cron (logs only, no DB writes / external calls) — looping is fine.
- One-shot startup tasks (not periodic).

## Severity

HIGH — infinite loops drain compute, API quota, and produce duplicate notifications / messages to end users.
