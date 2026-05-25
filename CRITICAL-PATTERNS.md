# CRITICAL PATTERNS

High-severity bug patterns — **always apply, regardless of stack or frequency in source documents.** Security, data-loss, privacy, financial, or catastrophic-availability impact.

Several of these appeared in only one source document (the 8-projects scan, where security work was systematically reviewed). Their **severity warrants top-tier placement even though frequency is narrow**. Each is tagged with its evidence base.

---

## K1. OAuth password takeover via signup flow

**Source:** 8-Projects C1 (routine — commit `8a39df6`)
**Severity:** CRITICAL — full account takeover

### What it looks like
Signup flow allows setting a password for an account that already exists via OAuth, requiring only the email address as input. Attacker who knows an OAuth user's email can:
1. Submit signup with that email + a new password.
2. Login with email/password from then on, bypassing OAuth.

### Detection rule
For any "set password" / "register" / "link account" endpoint that accepts an email:
1. If an account exists under that email via OAuth (or any other identity provider), **reject** the password-setting unless the request is authenticated as that user OR includes a verified one-time link sent to the OAuth-bound email.
2. Email knowledge alone is never sufficient for privilege transfer.

### See also
- `bugbot-rules/auth-before-irreversible-action.md`
- `bugbot-rules/privilege-escalation-unverified.md`

---

## K2. Rate limiter bypass via X-Forwarded-For spoofing

**Source:** 8-Projects C2 (Shipment-bot `11e7379`, routine `06ca796` — two projects)
**Severity:** CRITICAL — security control bypassed

### What it looks like
Rate limiter reads `X-Forwarded-For` (or `X-Real-IP`) directly from the request without validating that the immediate peer is a trusted proxy. Attacker spoofs the header → each request appears to come from a different IP → unlimited requests.

### Detection rule
Anywhere the code uses `request.headers["x-forwarded-for"]` or equivalent for security / rate-limit / abuse decisions:
1. The framework must be configured with an explicit trusted-proxy list (Starlette `ProxyHeadersMiddleware` with `trusted_hosts`; Express `app.set('trust proxy', <list>)`; Flask `ProxyFix(... trusted_hops=N)`).
2. **Never** trust the entire `X-Forwarded-For` chain; trust only the rightmost segments equal to the configured hop count.
3. If no proxy is in front, use `request.client.host` / `req.socket.remoteAddress` only.

### See also
- `BY-STACK/webhooks.md` — section on caller identity
- `bugbot-rules/rate-limit-xff-spoofing.md`

---

## K3. Privilege escalation — auto-admin by unverified email

**Source:** 8-Projects C10 (Markdown-Academy — commit `4623bdb`)
**Severity:** CRITICAL — admin role granted to attacker

### What it looks like
On registration, the code checks whether the supplied email equals a configured "owner / admin" email. If it does, the new user is granted admin role — **before** the email has been verified. Attacker who knows the owner's email creates an account, never confirms email, and is admin.

### Detection rule
Any code path that grants elevated role (admin / staff / owner / super_user) must:
1. Be reachable **only after** email verification (verification token validated, `email_verified_at` set).
2. Or be gated by an out-of-band action by an existing admin (invite link + token).
3. Never trust `request.body.email == OWNER_EMAIL` at registration time.

### See also
- `bugbot-rules/privilege-escalation-unverified.md`

---

## K4. XSS via `innerHTML` with user-supplied display name

**Source:** 8-Projects C9 (Facebook-Leads-New — commit `6a6ec51`)
**Severity:** CRITICAL — DOM XSS in admin panel

### What it looks like
`renderBlockedUsers` (or any admin/internal panel) used `element.innerHTML = '<div>' + user.name + '</div>'` with a name sourced from an external system (Facebook display name). A user named `<script>alert(1)</script>` executes script in the admin's browser context.

### Detection rule
1. `.innerHTML = ` / `dangerouslySetInnerHTML` / `v-html` with a string that includes any externally-sourced value (API response, DB row, URL param, `localStorage`) → flag.
2. Default to `textContent` / React JSX text nodes.
3. If HTML is genuinely required, the value must pass through `DOMPurify` (or equivalent) immediately before assignment, in the same line as the assignment.
4. "Admin only" is not a defense — admins are the targets of XSS.

### See also
- `BY-STACK/react-frontend.md` — DOM section
- `bugbot-rules/xss-innerhtml.md`

---

## K5. Network-exposed admin panel without auth

**Source:** 8-Projects C11 (Amazon-bot — commits `85776b5`, `c27c769`)
**Severity:** CRITICAL — RCE / admin control to anyone on the network

### What it looks like
Flask / FastAPI / Express server bound to `0.0.0.0` ("listen on all interfaces") with no token gate, no `Authorization` header check, no IP allowlist. Anyone reaching the port can use the panel.

### Detection rule
Any HTTP server startup:
1. If bound to `0.0.0.0` / `::` / "all interfaces" → require either (a) an authentication middleware that rejects unauthenticated requests *before* any route runs, or (b) a firewall / ingress that gates access externally.
2. If neither is configured → bind to `127.0.0.1` / `localhost` only.
3. Default to localhost during development; require an explicit env var to bind publicly.

### See also
- `bugbot-rules/network-exposed-without-auth.md`

---

## K6. Password hash / secret leaked in response or error message

**Source:** 8-Projects C6 (routine `06ca796`), C24 (Shipment-bot `59a5e3c`)
**Severity:** CRITICAL — secret material exposure

### What it looks like
- `ctx.user` middleware exposed the full ORM row including `passwordHash` field. Any endpoint serializing the user (profile, comments author, mentions) leaked hashes.
- `InsufficientCreditError.to_dict()` included `self.message = "Insufficient credit for courier {id}"` — internal courier UUID exposed in API response.

### Detection rule
1. User / actor serialization MUST go through an explicit DTO / Pydantic response model that lists only the allowed fields. ORM row → JSON is forbidden at API surfaces.
2. Forbidden field names anywhere in API response: `password`, `passwordHash`, `password_hash`, `salt`, `refresh_token`, `access_token`, `api_key`, `secret`, `private_key`.
3. Exception classes that may be raised at API surfaces must not include internal IDs / hostnames / heuristic reasons in their public message. Pattern: `class XError(AppException): public_message: str  # safe;  detail: dict  # server-only`.

### See also
- `bugbot-rules/secret-in-error-response.md`

---

## K7. PII in logs and API responses

**Source:** EmailFlow P5 (Hebrew doc) + 8-Projects C6, C24, C57 — **RECURRING by frequency, CRITICAL by severity**
**Severity:** CRITICAL — privacy / GDPR / compliance

### What it looks like
- `logger.info("sending email to %s", user.email)` — email is PII; survives in log aggregator forever.
- `HTTPException(detail=str(exc))` — internal exception string with stack trace leaks to client.
- `summary: "heuristic: esp:mailchimp.com"` in API response — exposes internal classification logic.
- English error messages with stack traces shown to end users (instead of generic translated message).

### Detection rule
In every `logger.*()` call and `HTTPException` `detail` / response body:

**Forbidden in logs (or API response):**
- `email`, `phone`, `from_email`, `to_email`, address fields, name fields.
- Body content of email / chat / messages.
- Raw OAuth tokens, `refresh_token`, `access_token`, API keys.

**Forbidden in API response only (logs OK if behind log access controls):**
- Heuristic decision reasons (`'esp:mailchimp.com'`, `'spam_score=0.8'`).
- Internal DB UUIDs of other tenants / users.
- Stack traces, exception class names, framework error messages.
- SQL fragments.

**Replacements:**
- PII → email *domain* only, or non-reversible hash, or own user_id.
- Internal logic → generic localized error.
- Internal IDs → only IDs of the *current* user's own resources.

### See also
- `RECURRING-PATTERNS.md` notes this as the only RECURRING pattern also promoted to CRITICAL.
- `bugbot-rules/pii-in-logs.md`

---

## K8. LIKE wildcard injection in user-supplied prefix

**Source:** 8-Projects C12 (Facebook-Leads-New — commit `2f45eca`)
**Severity:** CRITICAL — query manipulation / data exposure

### What it looks like
`get_config_by_prefix(prefix)` ran `WHERE key LIKE :prefix || '%'`. SQL `LIKE` treats `_` as "any single char" and `%` as "any sequence". A user-supplied prefix like `test_key` matched both `test_key_foo` and `testXkey_foo` — and a prefix of `%` would match everything.

### Detection rule
Any `LIKE` clause built from user input:
1. Escape `_` and `%` (and the escape char itself) in the input: `prefix.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')` and use `LIKE :p ESCAPE '\\'`.
2. Or rewrite to exact match (`=`) if prefix-search isn't actually required.
3. SQLAlchemy: use `column.startswith(value, autoescape=True)` instead of manual `LIKE`.

### See also
- `BY-STACK/postgres.md`
- `bugbot-rules/like-wildcard-injection.md`

---

## K9. Auth credential dispatched before storage (OTP / link / token)

**Source:** 8-Projects C4 (Shipment-bot — commits `552f0f7`, `155aa81`)
**Severity:** HIGH — auth lifecycle inconsistency, possible bypass via alternate verification path

### What it looks like
Order of operations:
1. Generate OTP.
2. Send via SMS / email (irreversible).
3. Store in Redis / DB.

If step 3 fails (Redis down, transient error), the user has a real code in hand but no verifier ever can match it. Worse, if there's a fallback "skip OTP" path that triggers on "Redis miss", the attacker who can cause Redis flakes gains a bypass.

### Detection rule
Every "credential generation + dispatch" flow must:
1. Persist (Redis SET / DB INSERT with TTL) **before** the external send.
2. If persist fails, do NOT send.
3. No "fallback" path that proceeds when verification storage is unreachable — fail closed.

Generalization: any "reserve / dispatch / store" triplet where the external action is irreversible — see CORE U1 (reserve-then-fill).

### See also
- `CORE-PATTERNS.md` U1
- `BY-STACK/webhooks.md`
- `bugbot-rules/auth-before-irreversible-action.md`

---

## K10. Generic 500 displayed as "invalid credentials"

**Source:** 8-Projects C57 (Web — commit `5196657`)
**Severity:** HIGH — security UX + user-enumeration aid + obscures real outages

### What it looks like
Login handler:
```js
catch (err) {
  if (err.status === 500) showError("Invalid username or password");
  if (err.status === 401) showError("Invalid username or password");
}
```
Any DB failure, network blip, or backend bug surfaces as "wrong password". Three consequences:
1. Real outage is invisible to ops (users say "my password isn't working").
2. Aids account-enumeration attackers (every email looks "wrong").
3. Users lock themselves out of real accounts trying to "reset" passwords that work.

### Detection rule
Login / auth error handling must branch:
- `401 / 403` → "Invalid credentials" (generic, doesn't leak whether email exists).
- `5xx` → "Service temporarily unavailable. Please try again in a moment." + alert to monitoring.
- `429` → "Too many attempts. Try again in N minutes."

Never collapse `5xx` into "invalid credentials".

### See also
- `bugbot-rules/auth-before-irreversible-action.md` (auth UX section)
