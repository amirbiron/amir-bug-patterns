# RECURRING PATTERNS

Patterns that appear in **two of three** source documents — strong signal, but evidence base is narrower than CORE. Apply if your project matches the stack. Each entry lists the specific projects, so you can judge whether the pattern is likely to apply.

> **Note on PII leakage:** It qualifies as RECURRING by frequency (EmailFlow + 8-Projects), but its severity promotes it to `CRITICAL-PATTERNS.md` K7. The full rule lives there; see also section here for cross-reference.

---

## R1. SQLAlchemy async session lifecycle

**Frequency:** 2/3 sources (EmailFlow + 8-Projects/Shipment-bot)
**Severity:** MEDIUM — `MissingGreenlet` crashes, silent data corruption

### What it looks like
Async SQLAlchemy (`AsyncSession`, `async_sessionmaker`) has lifecycle rules that catch developers off guard:
- ORM object attributes accessed *after* `await session.rollback()` raise `MissingGreenlet`.
- One `AsyncSession` shared between concurrent tasks via `asyncio.gather` → race / corruption (sessions are not thread- or task-safe).
- After `await session.commit()` in a loop, re-accessing the same ORM row returns stale attributes (commit refreshes only the PK; needs explicit `await session.refresh(row)`).
- `joinedload` + `with_for_update` is incompatible (SQLAlchemy raises).
- A singleton `Engine` bound to one event loop fails on the second Celery task (which gets a new loop).

### Real examples
- **EmailFlow (`0fdd247`):** `MissingGreenlet` accessing ORM attribute after session rollback.
- **EmailFlow (`018b166`):** `asyncio.gather` sharing session across tasks → corruption.
- **EmailFlow (`0e6dc85`):** Embedding job accessed stale attributes after in-loop commit.
- **Shipment-bot (`85d7a8e`):** Loop over `expiring` deliveries after `db.commit()` — `MissingGreenlet`.
- **Shipment-bot (`0f30963`):** Celery singleton engine tied to old event loop → second task always failed.
- **Shipment-bot (`4352bac`):** `joinedload` + `with_for_update` raised.

### Detection rule
1. Never pass the same `AsyncSession` to multiple concurrent tasks via `asyncio.gather` / `asyncio.create_task` — each task opens its own via `async with sessionmaker() as session:`.
2. After `await session.rollback()` (explicit or from exception): do not access ORM attributes. Extract `.id` / primitives **before** rollback, or `session.expunge(obj)` to detach.
3. After `await session.commit()` inside a loop, call `await session.refresh(row)` before re-accessing attributes.
4. `joinedload` with locking → use `contains_eager` instead.
5. Celery tasks: create a fresh engine inside the task (or use a connection pool that re-binds to the current loop).

### False positives
- Sync SQLAlchemy (regular `sessionmaker`) — different rules entirely.
- FastAPI dependency-scoped session per-request — safe as long as no `gather`.

### Recommended mode
**Strict** for code that does `await session.commit()` inside a loop or uses `asyncio.gather`.

### See also
- `BY-STACK/async-orm.md` — full coverage with code

---

## R2. Pagination without secondary tiebreaker

**Frequency:** 2/3 sources (EmailFlow + 8-Projects/Shipment-bot)
**Severity:** MEDIUM — pagination skips/duplicates rows, ranking non-deterministic

### What it looks like
`ORDER BY ts.desc()` (or `score.desc()`) followed by `LIMIT` / `OFFSET` or cursor pagination. Rows with the same primary value get **unspecified** order in Postgres → between pages, ties reshuffle → a row can appear twice or be skipped.

### Real examples
- **EmailFlow (`d84daca`):** `Lead.order_by(updated_at.desc())` only → leads with same timestamp got random order → pagination cycles.
- **EmailFlow (`3987818`):** CAS query needed `(timestamp, created_at)` tuple to match the selector.
- **EmailFlow (`a0c4603`):** Drafter ranking without secondary key → non-deterministic ranking.
- **Shipment-bot (`c0c1b74`):** Audit log paginated on timestamp only → entries reordered between pages.

### Detection rule
Every `order_by(...)` / raw `ORDER BY` followed by `LIMIT` / `OFFSET` / cursor pagination must include **at least two expressions**:
1. The semantic field (`created_at.desc()`, `score.desc()`).
2. The primary key as tiebreaker (`Model.id.desc()` or `.asc()`).

For CAS with "latest" semantics, the tiebreaker must match between the selector and the verifier.

### False positives
- Queries without `LIMIT` — order less critical.
- Aggregations (`GROUP BY` + `SUM`).
- Single-row queries (`.first()`, `.scalar_one_or_none()`) on a `UNIQUE` column.

### Recommended mode
**Warning** (strict mode adds `.id` to every query, including aggregations, generating noise).

### See also
- `BY-STACK/postgres.md`
- `bugbot-rules/pagination-tiebreaker.md`

---

## R3. Browser API / DOM quirks

**Frequency:** 2/3 sources (Noa + 8-Projects)
**Severity:** MEDIUM — UX broken, occasional data-loss

### What it looks like
Browser APIs have non-obvious semantics that catch developers reading them as if they were Node APIs:
- `window.open("mailto:...")` returns `null` in Chrome (system protocol handoff, **not** a popup blocker). Code interpreting `null` as "blocked" cancels the legitimate operation.
- `navigator.clipboard.writeText(...)` requires HTTPS; throws on HTTP. No try/catch → console error + silent UX failure.
- Tooltip / dropdown closes immediately on click because the click bubbles up to a parent that toggles state.
- Global CSS reset (`* { margin: 0; padding: 0 }`) has higher specificity than Tailwind utility classes like `space-y-6`.
- `URL.createObjectURL` leak — blob URL never revoked, accumulates per render.
- `setTimeout(fn, delay)` with `delay = NaN` — React error / infinite delay.

### Real examples
- **Noa (`f635304`):** `window.open("mailto:...")` returned `null` in Chrome; popup-blocker guard cancelled `mark_sent` flow.
- **Noa (`f4769bf`):** `BOOKED` button shown after `slot_start + 30min` instead of `slot_end` — broke short meetings.
- **Markdown-Academy (`b97d3f5`):** Copy button called `navigator.clipboard.writeText` without try/catch; broke on HTTP.
- **Markdown-Academy (`315154e`):** Tooltip closed on click because parent caught propagation; needed `stopPropagation()`.
- **Web (`c586691`):** Global CSS reset `* { margin: 0; padding: 0 }` overrode Tailwind utilities.
- **Web (`f5cbaf9`):** Profile picture blob URL not revoked on unmount.

### Detection rule
1. `window.open(url, ...)` followed by `if (!win)` cancel-flow → flag if `url` starts with `mailto:`, `tel:`, `sms:`, `file:`. For system protocols, use an `<a>` tag with `.click()` instead.
2. `navigator.clipboard.*` without try/catch → flag.
3. `URL.createObjectURL` without a matching `URL.revokeObjectURL` in the `useEffect` cleanup / `componentWillUnmount` / `addEventListener('unload', ...)`.
4. `setTimeout(fn, delay)` / `setInterval(fn, delay)` / `new Date(value)` without `isFinite(delay)` guard for externally-sourced delay/value.
5. Global `* { margin: 0; padding: 0 }` in a project using a utility CSS framework (Tailwind, UnoCSS) → flag.

### Recommended mode
**Warning** — most are UX bugs, not data-loss.

### See also
- `BY-STACK/browser-handoff.md`
- `bugbot-rules/window-open-protocol-handoff.md`

---

## R4. External SDK error completeness

**Frequency:** 2/3 sources (Noa + 8-Projects)
**Severity:** MEDIUM — silent swallow / production crash on init

### What it looks like
SDKs throw broad exception hierarchies, and `BaseException` subclasses (`asyncio.CancelledError`) don't sit under `Exception`. Code catches too narrow a base, lets some subclasses propagate, or swallows everything via `Exception` and miscounts.

### Real examples
- **Noa (`c128115`):** `_complete` caught `RateLimitError` + `_RETRYABLE`; other `anthropic.APIError` subtypes (`NotFound`, `BadRequest`, `Auth`) propagated uncaught.
- **Noa (`95dcce6`):** Fallback caught `RateLimitError` as generic `AIError` → caller didn't mark `pending_classification`.
- **Noa (`95b82e5`):** OAuth scope drift treated as fatal; needed `OAUTHLIB_RELAX_TOKEN_SCOPE=1`.
- **Shipment-bot (`e0f4d59`):** `isinstance(r, Exception)` didn't catch `CancelledError` (subclass of `BaseException`) → cancelled tasks counted as success.
- **routine (`2571c91` / `e5c26ad`):** Malformed VAPID keys → uncaught exception in `setVapidDetails` → server crashed on startup.

### Detection rule
1. For every external SDK call, the `except` should catch the SDK's documented base class (`anthropic.APIError`, `googleapiclient.errors.HttpError`, `stripe.error.StripeError`).
2. Order `except` blocks subclass-before-superclass (`RateLimitError` before `APIError`).
3. For async-task collection results (`asyncio.gather(return_exceptions=True)`): check `isinstance(r, BaseException)`, not `Exception` (CancelledError is not Exception in 3.8+).
4. Startup-time SDK init (VAPID keys, OAuth client, Stripe key) must be wrapped in try/except + format validation; failures degrade the relevant feature, not crash the whole server.
5. Document and respect SDK env flags (`OAUTHLIB_RELAX_TOKEN_SCOPE`, `STRIPE_API_VERSION`, etc.).

### Recommended mode
**Strict** at all SDK boundaries.

### See also
- `BY-STACK/external-sdk.md`
- `bugbot-rules/sdk-error-completeness.md`

---

## R5. Filter scope errors

**Frequency:** 2/3 sources (Noa + 8-Projects/Facebook-Leads-New)
**Severity:** MEDIUM — empty UI / cron infinite loop / blocked user still gets leads

### What it looks like
A filter (DB `WHERE`, regex, JS `.filter()`) is either too narrow (excludes legitimate cases) or applied in the wrong order (later filters override earlier ones).

### Real examples
- **Noa (`f635304`):** Manual list filtered to WhatsApp only; email-preferring lead saw empty list.
- **Noa (`d526948`):** `channel + audience` filter together blocked valid templates.
- **Noa (`95dcce6`):** Domain blacklist exact-match missed subdomains (`mail.mailchimp.com`).
- **Noa (`c608a85`):** Cron retry filter on `lead_id IS NULL` caught spam/not_business rows that would never be assigned → infinite loop.
- **Noa (`2b978aa`):** Cron filter `count < MAX` excluded rows stuck at `count==MAX` → stuck pending forever.
- **Facebook-Leads-New (`24ad356`):** Blocked-publisher filter ran *after* `force_send` check → blocked publisher with `force_send` keyword still sent leads.

### Detection rule
For every filter (`WHERE`, regex, `.filter()`):
1. **Completeness:** does it cover all expected input variants? (channel filters missing email-pref; regex on emails missing RFC 2822 display name; domain blacklist with exact match instead of `endswith` for subdomains).
2. **Terminal states for cron:** include explicit "done" columns (`processing_status`, `archived_at`), not "IS NULL" heuristics that catch terminal states which will never get filled.
3. **Filter order:** security / block / deny filters run *first*, before any "force send / always include" overrides.

### Recommended mode
**Strict** for cron filters that gate row reprocessing.
**Warning** for UI filters (false positives common — sometimes scope reduction is the feature).

### See also
- `BY-STACK/cron-jobs.md` — terminal-state pattern
- `bugbot-rules/filter-too-narrow.md`

---

## See also (cross-tier)

- **K7 / PII in logs** — frequency-wise RECURRING (EmailFlow P5 + 8-Projects C6/C24/C57), but severity-wise CRITICAL. Full rule in `CRITICAL-PATTERNS.md`.
