# BY-STACK: Webhooks ("someone calls me")

## Relevance — copy this file if your project has...
- ✅ Incoming webhooks from external services (Google Calendar, Gmail, Meta, Stripe, Twilio, Telegram)
- ✅ Pub/Sub / SQS / Kafka consumers (at-least-once delivery)
- ✅ Inbound rate-limit logic that reads `X-Forwarded-For` or similar
- ✅ Long-running deltas / sync tokens / cursors that advance with each call
- ⏭ Skip if: outbound-only system, no inbound HTTP

> Cross-link: **CRITICAL K2 (rate-limiter bypass via XFF)** is required reading. **CORE U1** (race conditions) and **U5** (partial atomic updates) are the underlying principles.

---

## Mental model

A webhook handler is a function that runs **concurrently with arbitrary other invocations of itself**. Every assumption that holds in a single-process script is wrong here:
- Same request body can arrive 9 times.
- Two requests can race on the same row.
- The signature header can be forged.
- The IP header can be spoofed.
- The delivery system can deliver out of order.

Design every webhook handler around: **identify the caller, dedupe the request, persist intent before side effects, advance the cursor on every call (even empty)**.

---

## Pattern 1 — Reserve-then-fill (EmailFlow P1, generalized in CORE U1)

**Severity:** HIGH — orphaned external state, financial / compliance impact

### What it looks like
```python
@app.post("/pubsub/gmail")
async def handle_gmail(req: Request):
  # parse
  msg = parse_pubsub(req)
  # external action FIRST
  draft = await gmail.drafts.create(body=msg.body)  # ❌
  # then commit locally
  session.add(Draft(gmail_id=draft.id, ...))
  await session.commit()
```

Pub/Sub delivers at-least-once. Nine parallel workers each call `gmail.drafts.create` before any of them commits the local row → 9 orphaned Gmail drafts.

### Fix
```python
@app.post("/pubsub/gmail")
async def handle_gmail(req: Request):
  msg = parse_pubsub(req)
  # 1. Reserve locally with UNIQUE constraint
  try:
    draft_row = Draft(idempotency_key=msg.message_id, status="reserved")
    session.add(draft_row)
    await session.commit()
  except IntegrityError:
    return Response(status_code=200)  # duplicate, ignore

  # 2. Then make the external call
  try:
    gmail_draft = await gmail.drafts.create(body=msg.body)
    draft_row.gmail_id = gmail_draft.id
    draft_row.status = "created"
    await session.commit()
  except Exception:
    draft_row.status = "failed"
    await session.commit()
    raise
```

### Real commits
- EmailFlow `f847a44`, `401f179`, `cc7e81a`, `75c0a47`, `0fdd247`.

---

## Pattern 2 — Parallel webhook race on shared cursor (Noa P3)

**Severity:** HIGH — duplicate activity rows, broken sync

### What it looks like
```python
async def handle_calendar_webhook(channel_id):
  sub = await session.get(Subscription, channel_id)
  changes = await google_api.events.list(sync_token=sub.sync_token)
  for change in changes.items:
    await apply_change(change)
  sub.sync_token = changes.next_sync_token  # ❌ another webhook just did this
  await session.commit()
```

Two webhooks arrive nearly simultaneously, both read the same `sync_token`, both call `google_api.events.list(...)`, both apply the same deltas → duplicate activities. Both write the same `next_sync_token`, but the deltas they applied may differ.

### Fix — CAS on the cursor
```python
async def handle_calendar_webhook(channel_id):
  sub = await session.get(Subscription, channel_id)
  old_token = sub.sync_token
  changes = await google_api.events.list(sync_token=old_token)

  # CAS update — only advance if cursor hasn't moved
  if old_token is None:
    where_clause = Subscription.sync_token.is_(None)
  else:
    where_clause = Subscription.sync_token == old_token
  result = await session.execute(
    update(Subscription)
      .where(Subscription.id == channel_id, where_clause)
      .values(sync_token=changes.next_sync_token)
  )
  if result.rowcount == 0:
    # another webhook beat us — its deltas are already applied; don't re-apply ours
    return
  for change in changes.items:
    await apply_change(change)
  await session.commit()
```

### Real commits
- Noa `33af59e` — two parallel Google Calendar webhooks → duplicate activities.
- Noa `cf99698` — CAS broke on `NULL` initial value (Postgres `col = NULL` is NULL).

---

## Pattern 3 — Empty webhook response not advancing cursor (Noa P9)

**Severity:** HIGH — infinite loop, exhausts API quota

### What it looks like
```python
async def handle(req):
  changes = await google.list(sync_token=sub.sync_token)
  if not changes.items:
    return  # ❌ next_sync_token never persisted, next webhook reads same cursor
  ...
```

### Fix
Even on empty changes, persist `next_sync_token` if the API provides one.

### Real commits
- Noa `0aff4a1`.

---

## Pattern 4 — Rate limiter trusts spoofable IP header (CRITICAL K2)

```python
ip = request.headers["x-forwarded-for"].split(",")[0]  # ❌
if rate_limiter.is_blocked(ip): return 429
```

Attacker sets `X-Forwarded-For: 1.2.3.4` → every request has a different "IP" → rate limit never triggers.

### Fix
Configure trusted-proxy middleware at the framework level:
- FastAPI / Starlette: `app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="<comma-separated-proxy-ips>")`.
- Express: `app.set('trust proxy', <hop-count or array>)`.
- Flask: `ProxyFix(app, x_for=N)`.

Then read `request.client.host` (already corrected by the middleware).

### Real commits
- Shipment-bot `11e7379`, routine `06ca796`.

---

## Pattern 5 — Webhook signature verification missing or wrong

Every inbound webhook from an external provider must verify the signature **before any processing**:
- Stripe: `stripe.Webhook.construct_event(payload, sig_header, webhook_secret)`.
- Meta: HMAC-SHA256 over body, compare with `X-Hub-Signature-256`.
- GitHub: HMAC-SHA1 / SHA256 over body, compare with `X-Hub-Signature-256`.

Common errors:
- Reading the body as text and re-encoding — breaks signature. Use raw bytes.
- Comparing with `==` (timing attack). Use `hmac.compare_digest`.
- Forgetting to verify on retry / replay endpoints.

(No specific commit cited — defensive baseline. Add to every webhook from day one.)

---

## Pattern 6 — Acquiring a rate-limit slot before verifying work is real

```python
limiter.acquire(channel)
result = await classify(message)
if not result.is_business:
  return  # ❌ slot wasted on spam
```

If the limit is a global cap on real work, acquire **after** the work-validity check:
```python
if not (await classify(message)).is_business:
  return
limiter.acquire(channel)
```

### Real commits
- EmailFlow `401f179`, `cc7e81a`.

---

## Pattern 7 — Beat scheduler + `delay()` race (CORE U1 specialization)

A beat (cron) trigger and a `.delay()` queue dispatcher can both pick the same row marked `PENDING`. Both send the message.

### Fix
Atomic CAS update:
```sql
UPDATE messages SET status='PROCESSING' WHERE id=:id AND status='PENDING' RETURNING id;
```
Check rowcount before sending.

### Real commits
- Shipment-bot `457eea1`.

---

## Cross-references

- **CORE U1** — race conditions (general theory)
- **CORE U5** — linked-field atomicity (reserve-then-fill is a special case)
- **CRITICAL K2** — XFF spoofing
- **CRITICAL K9** — credential dispatch before storage
- **BY-STACK/async-orm.md** — CAS templates
- **BY-STACK/cron-jobs.md** — beat-scheduler race
