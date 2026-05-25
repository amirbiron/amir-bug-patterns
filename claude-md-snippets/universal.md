# Universal patterns (paste into CLAUDE.md — applies to every project)

1. **Async race / TOCTOU.** Read-then-write needs a UNIQUE constraint, advisory lock, or CAS. `INSERT` locally **before** any irreversible external call. Every `async def` called in a boolean context (`if foo():`) must have `await`. CAS on nullable column: branch `is None` → use `IS NULL`.

2. **React state sync.** Local `useState(props.X)` is stale when `props.X` changes — use `key={id}`, `useEffect([X], () => setState(X))`, or derived state. All hooks before any early return. `useCallback`/`useMemo` deps must include every prop/state in the body. `setState` after `await` checks a cancellation flag.

3. **External input validation.** Before `.get()` / `.append()` / `.strip()` / iteration on external data: `isinstance(...)` guard. Numbers: `isfinite()` + range. Regex on external text: raw strings + word boundaries; prefer `json.JSONDecoder().raw_decode()` over regex. SDK calls: catch base class (`anthropic.APIError`), order subclass-before-superclass. Startup SDK init: try/except + format validation — degrade the feature, never crash the boot.

4. **SQL/Postgres edges.** `col = NULL` is NULL, not TRUE — branch to `IS NULL`. `VARCHAR(N)` ≥ longest enum value (CI test). Telegram / external IDs: `BigInteger`. Every `ORDER BY` paired with `LIMIT`/`OFFSET` needs `, id` tiebreaker. `LIKE` with user input: `.startswith(value, autoescape=True)` or escape `_`/`%`.

5. **Linked-field atomicity.** Status changes update ALL coupled fields (`status` + `last_outbound_at` + `last_activity_type` + close-related-task + activity-log) in one transaction. External call: write local row with `UNIQUE` first; or write audit log with `metadata.applied=false` on failure. Token pairs (access + refresh) stored/updated together.

6. **Migration drift.** Every `Index`/`CheckConstraint`/`UniqueConstraint` in migration must mirror in model `__table_args__`. Alembic revision id ≤ 30 chars. MySQL projects: no `ADD COLUMN IF NOT EXISTS`. `DROP COLUMN` is a separate migration after code stops using the field.

See `BY-STACK/*.md` for code examples and `bugbot-rules/*.md` for standalone rule prompts.
