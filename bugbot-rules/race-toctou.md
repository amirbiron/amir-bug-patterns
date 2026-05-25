# race-toctou

Detect Time-Of-Check-Time-Of-Use patterns in concurrent / async code that risk duplicates, stale state, or missed updates.

## Flag when ANY of these apply

1. A read of a row's status / state column (`SELECT`, ORM `.get()`, `.scalar()`), followed by a conditional branch, followed by an `UPDATE` or external call on the same row — without a `WHERE` clause referencing the read value (no CAS), without `SELECT FOR UPDATE`, and without a `UNIQUE` / `ON CONFLICT` constraint.

2. An `async def` function called without `await` and used in a boolean context (`if foo():`) — coroutines are truthy, so the check always passes.

3. A precondition / validity check that runs BEFORE the lock that's supposed to protect the resource.

4. `commit()` / DB write that runs AFTER an irreversible external call (HTTP POST, email/SMS send, payment API) — no UNIQUE row inserted as "reservation" before the external call.

5. CAS / cursor update comparing a nullable column with `=` (in Postgres: `col = NULL` evaluates to NULL, not TRUE — must use `IS NULL` branch).

## False positives

- Single-process, single-threaded script with no concurrent runners.
- Read happens inside `SELECT FOR UPDATE`.
- Write uses `INSERT ... ON CONFLICT DO NOTHING` / `ON CONFLICT DO UPDATE`.
- Read-only external call (status fetch, fire-and-forget analytics).
- Tests with mocks.

## Severity

HIGH — duplicate side effects, financial / compliance impact, infinite loops.
