# BY-STACK: External SDKs (Anthropic, Google, Stripe, OAuth, push notifications)

## Relevance — copy this file if your project has...
- ✅ Anthropic / OpenAI / other LLM SDK calls
- ✅ Google APIs (Calendar, Gmail, OAuth, Sheets, FCM, web-push)
- ✅ Stripe, Twilio, Telegram, Slack, Meta SDKs
- ✅ Parsing API responses, webhook payloads, or AI-generated JSON
- ✅ Startup-time SDK initialization with env vars / keys
- ⏭ Skip if: project has no third-party integrations

> Cross-link: **CORE U3** (external input validation) is the general rule; this file covers SDK-specific manifestations. **R4** (SDK error completeness) lives here in depth.

---

## Mental model

Every external SDK is two boundaries:
1. **Outgoing call** — your code → SDK → network. Can fail with the SDK's exception hierarchy, network errors, or timeout.
2. **Incoming data** — SDK → your code. Can return different shapes in test/sandbox/prod, may include nulls/missing fields, and the SDK's type hints are aspirational.

Defensive coding at both boundaries is the price of admission.

---

## Pattern 1 — Catching too-narrow exception base (R4)

```python
try:
  result = await anthropic.messages.create(...)
except RateLimitError:
  await asyncio.sleep(BACKOFF); retry
except _RETRYABLE_ERRORS:
  retry
# ❌ APIError subtypes (NotFound, BadRequest, Auth) propagate uncaught
```

### Fix
Catch the SDK's base class, then refine:
```python
try:
  result = await anthropic.messages.create(...)
except RateLimitError:
  retry
except APIError as e:
  if e.status_code == 400: handle_bad_request(e)
  else: raise
```

Order `except` blocks subclass-before-superclass.

### Real commits
- Noa `c128115` — Anthropic SDK error completeness.
- Noa `95dcce6` — fallback swallowed `RateLimitError` as generic `AIError`.

---

## Pattern 2 — `CancelledError` not caught by `Exception` (Python ≥ 3.8)

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for r in results:
  if isinstance(r, Exception):  # ❌ misses CancelledError
    handle_error(r)
  else:
    count_success += 1  # ❌ cancelled tasks counted as success
```

`asyncio.CancelledError` inherits from `BaseException` (not `Exception`) since Python 3.8.

### Fix
```python
for r in results:
  if isinstance(r, BaseException):
    handle_error(r)
```

### Real commits
- Shipment-bot `e0f4d59`.

---

## Pattern 3 — `isinstance(r, SendResult)` vs `r is True`

```python
if r is True: count_success += 1  # ❌ SendResult object, not bool
```

### Fix
Implement `__bool__` on the result class, or compare explicitly:
```python
if isinstance(r, SendResult) and r.ok: count_success += 1
```

### Real commits
- Shipment-bot `11e7379`.

---

## Pattern 4 — Startup-time SDK init crashes the server (R4)

```python
# at import time
webpush.set_vapid_details(
  subject=settings.VAPID_EMAIL,
  public_key=settings.VAPID_PUBLIC_KEY,
  private_key=settings.VAPID_PRIVATE_KEY,
)
```

If `VAPID_EMAIL` lacks the `mailto:` prefix, or keys are malformed, this throws on import → entire server crashes on boot. Same for OAuth client init, Stripe client init.

### Fix
Wrap in try/except + validate format:
```python
def init_push():
  try:
    if not settings.VAPID_EMAIL.startswith("mailto:"):
      vapid_email = f"mailto:{settings.VAPID_EMAIL}"
    else:
      vapid_email = settings.VAPID_EMAIL
    webpush.set_vapid_details(subject=vapid_email, public_key=..., private_key=...)
    return True
  except Exception:
    logger.exception("push notifications disabled — VAPID init failed")
    return False
```

Degrade the *feature*, not the whole server.

### Real commits
- routine `e5c26ad`, `2571c91`.

---

## Pattern 5 — Regex on AI / SDK JSON response (CORE U3)

```python
match = re.search(r"\{.*\}", ai_response, re.DOTALL)  # ❌ greedy; breaks on trailing prose
data = json.loads(match.group(0))
```

`\{.*\}` is greedy. Trailing `}` in prose (`"... and finally }"`) bleeds into the match. Nested objects, escape sequences also break.

### Fix
```python
decoder = json.JSONDecoder()
start = ai_response.find("{")
if start < 0: raise ValueError("no JSON")
data, _ = decoder.raw_decode(ai_response[start:])
```

### Real commits
- Noa `f27adc1`.

---

## Pattern 6 — isinstance guards on external responses (CORE U3)

```python
data = response.json()
items = data.get("messages", [])  # ❌ if data is a list, .get crashes
```

### Fix
```python
data = response.json()
if not isinstance(data, dict):
  raise ValueError(f"expected dict, got {type(data)}")
items = data.get("messages", [])
if not isinstance(items, list):
  raise ValueError("messages not a list")
```

### Real commits
- EmailFlow `6b7dbeb`, `46d05f7`, `55b4328`, `018b166`.

---

## Pattern 7 — SDK env / config flags ignored

Some SDKs require env-var flags to handle real-world edge cases:
- `OAUTHLIB_RELAX_TOKEN_SCOPE=1` — OAuth scope drift in Google libraries (Noa `95b82e5`).
- `OAUTHLIB_INSECURE_TRANSPORT=1` — only for local dev (HTTP callbacks).
- `STRIPE_API_VERSION` — pin to avoid silent breaking changes.
- `ANTHROPIC_LOG=debug` — verbose logs.

Document these in your project's settings and treat scope-drift / version-skew as expected operational events, not exceptions.

---

## Pattern 8 — Pydantic schema mismatch on external enum (links to state-machine.md Pattern 4)

```python
class LeadDraft(BaseModel):
  service_category: ServiceCategoryEnum  # strict; rejects unknown
```
AI returns `"unknown"` → Pydantic rejects → entire draft (including valid `full_name` and `phone`) is lost.

### Fix
For external-sourced enum values, accept `str | None` and validate idempotently in the caller. Reserve strict enums for internal-only fields.

### Real commits
- Noa `7001892`, `f6293e3`, `dc24922`.

---

## Pattern 9 — Walrus + truthy check on env var

```python
if override := os.environ.get("OVERRIDE_VALUE"):  # ❌ "" is falsy but valid override
  apply(override)
```

`""` is a meaningful value ("override to empty"), but the walrus treats it as `None`.

### Fix
```python
override = os.environ.get("OVERRIDE_VALUE")
if override is not None:
  apply(override.strip())
```

### Real commits
- Noa `236b072`.

---

## Cross-references

- **CORE U3** — boundary validation (general theory)
- **R4** — SDK error completeness (this file is the deep-dive)
- **BY-STACK/state-machine.md** — Pydantic schema mismatch
- **`bugbot-rules/external-input-isinstance.md`**, **`sdk-error-completeness.md`**
