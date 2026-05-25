# CORE PATTERNS

Universal bug patterns — these appear in **all three** source documents (Noa_Leads, EmailFlow, and the 8-projects set) across different stacks, projects, and timeframes. They reflect personal habits and reasoning gaps, not project quirks. **Apply these to every new project regardless of stack.**

For each pattern: real commits cited, a generic detection rule, false positives, and recommended enforcement mode.

---

## U1. Race conditions / async TOCTOU

**Frequency:** 3/3 sources, ~15 instances
**Projects:** Noa_Leads, EmailFlow, Shipment-bot, Facebook-Leads-New, Markdown-Academy, routine
**Severity:** HIGH

### What it looks like
Concurrent code paths read shared state, branch on it, and then write — without atomicity. Manifests as:
- Duplicates from parallel webhooks / queue workers / cron + beat scheduler.
- Missing `await` making coroutines always truthy.
- Lock check performed *outside* the lock it's supposed to gate.
- Stale cursors / CAS using `=` instead of `IS NULL` on nullable columns.

### Pattern variants
Same root cause, different presentations. Both are fixed by `UNIQUE` constraint + transaction lock (or CAS), but naming the specific variant helps when debugging:

- **(a) DB row not created before external call** — code calls `await client.X()` (Gmail draft, SMS send, payment, webhook emit) *before* inserting the local "intent" row with a `UNIQUE` constraint. At-least-once delivery (Pub/Sub, retries, parallel workers) creates orphans on the external side.
- **(b) Check-then-act gap between read and write** — code does `SELECT ... WHERE status='pending'`, branches, then does `UPDATE ... WHERE id=:id`. Two runners both pass the read, both run the update, both perform the action.
- **(c) Cursor / CAS column not advanced atomically** — webhook reads `sync_token`, calls external API, writes back `next_sync_token` in a separate statement. Two webhooks race on the cursor; both apply the same deltas.
- **(d) Missing `await` on async predicate** — async function called in a boolean context (`if foo():`); coroutine is always truthy, so the gate never blocks.

When debugging, identify the variant first — the fix is the same family (CAS / `UNIQUE` / lock), but the right placement differs.

### Real examples
- **Noa (`33af59e`):** Two parallel Google Calendar webhooks read the same `sync_token`, applied deltas → duplicate Activity rows. Fix: optimistic lock + CAS (`WHERE history_id = expected_old`).
- **Noa (`cf99698`):** CAS on `WHERE history_id = expected_old` didn't handle `NULL` in Postgres → cursor stuck forever.
- **EmailFlow (`f847a44`):** Nine parallel Pub/Sub workers each created a Gmail draft before one committed → 9 orphaned drafts. Fix: INSERT locally with `UNIQUE` *before* the Gmail call.
- **Shipment-bot (`457eea1`):** `SELECT ... WHERE status='PENDING'` then `UPDATE`; beat scheduler and `send_message.delay()` both picked the row → OTP sent twice. Fix: atomic `UPDATE ... WHERE status='PENDING' RETURNING id`, check rowcount.
- **Shipment-bot (`f1e0fbb`):** `_is_ip_blocked()` became async, caller didn't add `await` → coroutine always truthy → every webhook returned 429.
- **Facebook-Leads-New (`5823724`):** `_check_daily_limit()` ran outside the `scan_lock` → two concurrent calls both passed, both ran scans.
- **Markdown-Academy (`7c955f1`):** Server startup called seed multiple times in parallel without guard → lessons created twice.

### Detection rule (paste into CLAUDE.md / bugbot)
Flag any one of:
1. `await session.commit()` followed by `await client.X()` (external irreversible call) without a preceding INSERT with `UNIQUE` constraint or row lock.
2. `SELECT` / ORM `.scalar()` returning state, then branch, then `UPDATE` on the same row without `WHERE` on the read value (no CAS).
3. `async def` function called without `await` and used in a boolean context (`if foo():`).
4. Lock-protected critical section where a precondition is checked *before* the lock acquisition.
5. CAS / cursor compared with `=` when the value can be `NULL` (Postgres: `col = NULL` is `NULL`, not `TRUE` — must branch on `IS NULL`).

### False positives
- Read-only external calls (status fetch, analytics fire-and-forget) — no reserve needed.
- Single-process script with no concurrent runners — race theoretical.
- Write uses `INSERT ... ON CONFLICT` or `UNIQUE` already catches duplicates.
- Read happens inside `SELECT FOR UPDATE` block.

### Recommended mode
**Strict** for webhook handlers, queue/Celery tasks, cron jobs, payment / messaging / OTP flows.
**Warning** for internal admin tools and single-runner scripts.

### See also
- `BY-STACK/webhooks.md` — Pub/Sub at-least-once, signature, idempotency
- `BY-STACK/async-orm.md` — SQLAlchemy CAS, advisory locks
- `BY-STACK/cron-jobs.md` — cron + beat-scheduler races
- `bugbot-rules/race-toctou.md` — standalone prompt

---

## U2. React state sync / stale closure

**Frequency:** 3/3 sources, ~6 instances
**Projects:** Noa_Leads (React frontend), EmailFlow (React frontend), routine, Web
**Severity:** MEDIUM (UX-breaking; data-corruption when status sent to backend)

### What it looks like
Local `useState` initialized from a prop that changes is not re-synced; or a callback captures a stale variable; or hooks are called after an early return, violating Rules of Hooks.

### Real examples
- **Noa (`3fc0ec6`):** `useEffect` dep on an object reference re-triggered and overwrote user edits.
- **Noa (`b360c66`):** Async `renderTemplate` without checking a cancelled flag → stale preview overwrote the UI.
- **EmailFlow (`e968135`):** `useState` after early `return` → hook count varied → React crash.
- **EmailFlow (`02f633a`):** Missing `key={conversationId}` on `ReplyBox` → state carried over to a different conversation.
- **EmailFlow (`d84daca` + `3987818`):** Status dropdown synced only on `leadId`; list refetch updated DB status but dropdown stuck on old value → save sent wrong `expected_status` → pipeline reverted.
- **routine (`259c2a3`):** `activeChildId` missing from `useCallback` deps → after switching child, action affected the previous child.
- **Web (`2e5c480`):** After email verification only `token` updated in `localStorage`; `refreshToken` stayed stale → reauth broke.

### Detection rule
Flag any one of:
1. `const [s, setS] = useState(props.X)` where `props.X` can change, AND no `useEffect([props.X])` resync AND no `key={...}` on the component.
2. `useState` / `useEffect` / `useCallback` / `useMemo` called after `if (...) return null;` or any conditional return.
3. `useCallback` / `useMemo` whose body references a prop or state variable not in the dependency array.
4. Partial state update of a multi-field value (e.g., update `token` without `refreshToken`).
5. `setState` after `await` without a cancellation-flag check.

### False positives
- Local-only state (modal open/closed, theme toggle) — not tied to external data.
- Uncontrolled inputs with `defaultValue` — intentional.
- Component receives prop once at mount (e.g., `user.id`) — no sync needed.
- Dep array intentionally excludes an unstable identity (TanStack mutation object) — comment should explain.

### Recommended mode
**Warning** (strict mode generates high noise for legitimate local-only state).

### See also
- `BY-STACK/react-frontend.md` — deep-dive with three resync patterns
- `bugbot-rules/react-stale-state-on-prop.md`

---

## U3. External input / boundary validation

**Frequency:** 3/3 sources, ~12 instances
**Projects:** Noa_Leads, EmailFlow, Shipment-bot, Facebook-Leads-New, routine
**Severity:** MEDIUM (crashes on real traffic) / HIGH (when paired with SQL or eval)

### What it looks like
Code assumes external input (API responses, webhook payloads, AI output, environment variables) has the expected shape — no `isinstance` guard, no NaN/Inf check, regex over-matches, SDK exception subclass not caught.

### Real examples
- **Noa (`c128115`):** `_complete` caught only `RateLimitError` + `_RETRYABLE`; other `anthropic.APIError` subtypes (NotFound, BadRequest, Auth) propagated uncaught.
- **Noa (`95dcce6`):** Domain blacklist used exact-match on email host → `mail.mailchimp.com` not blocked.
- **Noa (`f27adc1`):** Greedy regex `\{.*\}` on AI JSON response broke on trailing `}` in prose.
- **Noa (`7001892`):** `LeadDraft.service_category` as `StrEnum` rejected unknown value → loss of full_name + phone on that one field.
- **EmailFlow (`6b7dbeb`):** `headers["list-unsubscribe"].strip()` crashed when value was non-str (corrupt MIME).
- **EmailFlow (`46d05f7`):** `parsed_json.get(...)` crashed because `parsed_json` was a list, not dict.
- **EmailFlow (`55b4328`):** `parse_webhook` received `messages: None` instead of list.
- **EmailFlow (`e432866`):** `setTimeout(fn, delay)` with NaN value → React crash.
- **Shipment-bot (`97bf0bc`):** `AmountValidator` didn't check NaN/Inf; `NaN < 0` is `False`, `NaN > max` is `False` → NaN entered wallet as amount.
- **Facebook-Leads-New (`fadc0dc`):** `\b` in triple-quoted Python string is backspace, not word boundary → regex didn't fire.
- **routine (`e5c26ad` / `2571c91`):** Malformed VAPID keys / missing `mailto:` prefix → uncaught exception in `setVapidDetails` → server crash on startup.

### Detection rule
Before every `.get()`, `.append()`, `.strip()`, `[key]`, or iteration on an external value, require:
1. `isinstance(obj, dict)` if expecting dict.
2. `isinstance(items, list)` if expecting list.
3. `isinstance(value, str)` before `.strip() / .lower() / .split()`.
4. For numbers: `isinstance(n, (int, float))` + `math.isfinite(n)` + range check.
5. For regex on external text: use raw strings (`r"..."`) and word boundaries; prefer `json.JSONDecoder().raw_decode()` over regex for embedded JSON.
6. For SDK calls: catch the SDK's base class (`anthropic.APIError`, `googleapiclient.errors.HttpError`), order `except` blocks subclass-before-superclass.
7. For startup-time config (VAPID keys, env vars, OAuth secrets): wrap initialization in try/except + validate format on boot.

### False positives
- Internal data freshly created by our code (Pydantic-validated FastAPI input is already isinstance-checked).
- `logger.debug` paths that won't run in production.
- Narrow `except` for intentional propagation (e.g., `AppException` reaching FastAPI).

### Recommended mode
**Warning** for 2 weeks on existing code, then **strict** for new code at module boundaries.

### See also
- `BY-STACK/external-sdk.md`
- `bugbot-rules/external-input-isinstance.md`
- `bugbot-rules/sdk-error-completeness.md`

---

## U4. SQL / Postgres edge cases

**Frequency:** 3/3 sources, ~8 instances
**Projects:** Noa_Leads, EmailFlow, Shipment-bot, Facebook-Leads-New, routine
**Severity:** MEDIUM–HIGH

### What it looks like
Postgres / SQLAlchemy / generic-SQL semantics surprise the developer:
- `col = NULL` returns `NULL`, not `TRUE`.
- `VARCHAR(N)` too small for a new enum string value → INSERT fails in prod, not in dev SQLite.
- `Integer` column too small for IDs from external systems (Telegram, Stripe).
- `ORDER BY` on a non-unique column has unspecified order for ties → pagination skips/duplicates.
- `LIKE` matches `_` and `%` as wildcards in user-supplied prefixes.
- SQLAlchemy `postgresql_ops` misused as sort direction.
- `ANY(:ids)` with string array on UUID column fails without cast.

### Real examples
- **Noa (`cf99698`):** CAS `WHERE col = NULL` doesn't match NULL — needs `IS NULL` branch.
- **Noa (`2c8263a`):** `VARCHAR(20)` too small for new `StrEnum` value → INSERT failed.
- **Noa (`98e8d18`):** `postgresql_ops={"col": "DESC"}` is wrong (it's for operator classes); use `desc("col")`.
- **Noa (`244286d`):** `ANY(:ids)` with string array on UUID column failed without cast.
- **EmailFlow (`d84daca`):** `Lead.order_by(updated_at.desc())` only — leads with same timestamp got random order → pagination cycles.
- **EmailFlow (`dfdf975`):** `.strip()` on a Column expression didn't execute in SQL; needed `func.trim(...)`.
- **Shipment-bot (`b16b99f`):** `entity_id` as `Integer`; Telegram IDs exceed 2³¹ → INSERT failed.
- **Shipment-bot (`c0c1b74`):** Audit log pagination sorted only by timestamp → entries reordered between pages.
- **Facebook-Leads-New (`2f45eca`):** `LIKE 'test_key%'` matched `testXkey` because `_` is a wildcard.

### Detection rule
1. In CAS / `UPDATE ... WHERE col = :val` where `col` is nullable: branch on `is None` → use `col.is_(None)`.
2. Any `String(N)` / `VARCHAR(N)` column populated from an enum: enforce `N >= max(len(v) for v in EnumClass)` (CI check or test).
3. Telegram / external IDs → `BigInteger` (`BIGINT`).
4. Every `ORDER BY` that's followed by `LIMIT`/`OFFSET` or cursor pagination must have a secondary tiebreaker, typically the primary key (`.id`).
5. Every `LIKE` with user-supplied prefix must escape `_` and `%`, or use exact / `=`.
6. Python string ops (`.strip()`, `.lower()`) on `Column` expressions → use `func.trim()`, `func.lower()`.

### False positives
- Aggregations (`GROUP BY` + `SUM`) — pagination tiebreaker not needed.
- Single-row `.first()` on `UNIQUE` column.
- ORM updates via `session.merge` — not raw SQL.

### Recommended mode
**Strict** for nullability, `LIKE` escaping, and column-size checks.
**Warning** for missing pagination tiebreakers in non-paginated queries.

### See also
- `BY-STACK/postgres.md` — full SQL/Alembic/pagination coverage
- `bugbot-rules/postgres-null-cas.md`, `pagination-tiebreaker.md`, `like-wildcard-injection.md`

---

## U5. Partial atomic updates / linked-field drift

**Frequency:** 3/3 sources, ~10 instances
**Projects:** Noa_Leads, EmailFlow, Shipment-bot, routine, Web
**Severity:** HIGH (silent data corruption + downstream consumers depend on the cascade)

### What it looks like
A logical operation requires updating N coupled fields atomically. The code updates `N-1` and forgets the rest. The "missed" field is later read by cron, dashboard, or another flow → silent inconsistency.

### Real examples
- **Noa (`bd2b105`):** Chip set `PROPOSAL_SENT` and bypassed the `ProposalSentConfirmModal` flow.
- **Noa (`75b430a`):** Chip set `PROPOSAL_SENT` without writing `proposal_sent_at` → `check_stuck_proposals` broke.
- **Noa (`df530f3`):** `apply_chip` updated status but forgot `last_outbound_at` + `last_activity_type`.
- **Noa (`4cc5a09`):** `apply_chip` didn't close old tasks in `AUTO_CLOSE_TASK_TYPES` + no dedup.
- **Noa (`04cb101`):** `_apply_reschedule` `rowcount=0` left booking without activity log → cron treated it as never happened.
- **EmailFlow (`f847a44`):** Pub/Sub draft created externally before local DB commit → orphans on partial failure.
- **EmailFlow (`75c0a47`):** Audit row written before `client.send_draft()` — if send failed, compliance trail lied.
- **routine (`01c61ac`):** `handleMorningTimeChange` sent only `hour`, not `enabled` flag; concurrent requests overwrote each other.
- **Web (`2e5c480`):** Only `token` updated in `localStorage`; `refreshToken` stayed from signup → reauth broke.

### Detection rule
For any function that updates an entity's status / "phase" / lifecycle column, verify the **canonical sibling list** is also updated in the same transaction. Project-specific examples:
- Status change → `last_outbound_at`, `last_activity_type`, `proposal_sent_at`, close `AUTO_CLOSE_TASK_TYPES`, log activity, invalidate cache.
- External call → either `INSERT` locally first with `UNIQUE` *before* the call, or write the audit log with `metadata.applied=false` on failure.
- Token refresh → both `access` and `refresh` tokens in one atomic write (`localStorage.setItem` is per-key; use one JSON blob or both writes in a transaction).
- Partial form submit → either send full object or use server-side merge with explicit field mask.

### False positives
- Migrations / backfill scripts (one-shot, not transactional touchpoints).
- Read-only paths.
- Single-field updates that are genuinely independent (e.g., `last_viewed_at` not tied to anything).

### Recommended mode
**Strict** within `apply_chip` / `mark_*_sent` / state-machine entry points.
**Warning** elsewhere.

### See also
- `BY-STACK/state-machine.md` — touchpoint completeness checklist
- `BY-STACK/webhooks.md` — reserve-then-fill pattern
- `bugbot-rules/linked-field-atomicity.md`

---

## U6. Migration / schema drift

**Frequency:** 3/3 sources, ~6 instances
**Projects:** Noa_Leads, EmailFlow, Shipment-bot, Markdown-Academy, routine
**Severity:** MEDIUM (breaks fresh deploys; survives in CI if tests use migrated DB only)

### What it looks like
Schema changes live in two places: Alembic / Knex migration AND SQLAlchemy / ORM model `__table_args__`. The two drift; fresh DB (test, dev, prod-from-scratch) ends up with a different schema than the production DB after incremental migrations.

### Real examples
- **Noa (`2c8263a`):** Migration added new enum value but column `VARCHAR(20)` too short.
- **EmailFlow (`40f855d`):** FTS index in migration only, not in model `__table_args__` → fresh DB build missing index.
- **EmailFlow (`a3a3134`):** Alembic revision id longer than `VARCHAR(32)` of `alembic_version.version_num` → migration failed on fresh Render deploy.
- **EmailFlow (`f143e1c`):** Migration has `DROP COLUMN` but code still uses it.
- **EmailFlow (`3f43d91`):** `CHECK` constraint sorted differently in migration vs. model.
- **routine (`80c1fc4`):** Migration used `ADD COLUMN IF NOT EXISTS` — not supported in MySQL.
- **routine (`7a4e879`):** Migration ran `ALTER TABLE` on non-existent table in first deploy.
- **routine (`230e0c1`):** Duplicate migration file + missing SSL config.
- **Shipment-bot (`b16b99f`):** Schema column type mismatch (`Integer` too small for Telegram IDs).

### Detection rule
1. Every `Index(...)`, `CheckConstraint(...)`, `UniqueConstraint(...)` in a migration must appear identically in the model's `__table_args__`.
2. `DROP COLUMN` in a PR that still has references to that column elsewhere → flag.
3. Alembic revision id length ≤ 32.
4. MySQL projects: no `IF NOT EXISTS` on `ADD COLUMN` (PG-only syntax); no `ADD COLUMN IF NOT EXISTS`.
5. `String(N)` / `VARCHAR(N)` columns populated from an enum → CI test asserts `N >= max(len(value) for value in Enum)`.
6. Migrations are additive when old code still uses the column — destructive change goes in a *separate* later migration after the code is removed.

### False positives
- Data-only migrations (backfill, fixup) — no schema change.
- Test fixtures with `extend_existing=True`.

### Recommended mode
**Strict** for migration ↔ model parity.
**Warning** for revision id length and MySQL syntax (caught by CI run anyway).

### See also
- `BY-STACK/postgres.md` — full migration coverage
- `bugbot-rules/migration-model-drift.md`
