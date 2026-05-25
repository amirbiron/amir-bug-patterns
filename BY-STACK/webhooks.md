# BY-STACK: Webhooks ("מישהו קורא אליי")

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...
- ✅ webhooks נכנסים משירותים חיצוניים (Google Calendar, Gmail, Meta, Stripe, Twilio, Telegram)
- ✅ Consumers של Pub/Sub / SQS / Kafka (at-least-once delivery)
- ✅ לוגיקת rate-limit נכנסת שקוראת `X-Forwarded-For` או דומה
- ✅ deltas / sync tokens / cursors שמתקדמים בכל קריאה
- ⏭ דלג אם: מערכת outbound-only, בלי HTTP נכנס

> Cross-link: **CRITICAL K2 (עקיפת rate-limiter דרך XFF)** הוא חובת קריאה. **CORE U1** (race conditions) ו-**U5** (partial atomic updates) הם העקרונות הבסיסיים.

---

## מודל מנטלי

webhook handler הוא פונקציה שרצה **concurrent עם invocations שרירותיים אחרים של עצמה**. כל הנחה שמחזיקה ב-script של תהליך יחיד שגויה כאן:
- אותו body של בקשה יכול להגיע 9 פעמים.
- שתי בקשות יכולות להתחרות על אותה שורה.
- ה-signature header יכול להיות מזויף.
- ה-IP header יכול להיות מזויף.
- מערכת ה-delivery יכולה לספק לא בסדר.

עצב כל webhook handler סביב: **זהה את ה-caller, dedupe את ה-request, התמד ב-intent לפני side effects, הקדם את ה-cursor בכל קריאה (גם ריקה)**.

---

## דפוס 1 — Reserve-then-fill (EmailFlow P1, הוכלל ב-CORE U1)

**חומרה:** HIGH — state חיצוני יתום, השפעה פיננסית / compliance

### איך זה נראה
```python
@app.post("/pubsub/gmail")
async def handle_gmail(req: Request):
  # parse
  msg = parse_pubsub(req)
  # פעולה חיצונית קודם
  draft = await gmail.drafts.create(body=msg.body)  # ❌
  # ואז commit מקומי
  session.add(Draft(gmail_id=draft.id, ...))
  await session.commit()
```

Pub/Sub מספק at-least-once. תשעה workers מקבילים כל אחד קורא ל-`gmail.drafts.create` לפני שאחד מהם עושה commit לשורה מקומית → 9 Gmail drafts יתומים.

### תיקון
```python
@app.post("/pubsub/gmail")
async def handle_gmail(req: Request):
  msg = parse_pubsub(req)
  # 1. רזרבציה מקומית עם UNIQUE constraint
  try:
    draft_row = Draft(idempotency_key=msg.message_id, status="reserved")
    session.add(draft_row)
    await session.commit()
  except IntegrityError:
    return Response(status_code=200)  # duplicate, ignore

  # 2. ואז קריאה חיצונית
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

### Commits אמיתיים
- EmailFlow `f847a44`, `401f179`, `cc7e81a`, `75c0a47`, `0fdd247`.

---

## דפוס 2 — race של webhook מקבילי על cursor משותף (Noa P3)

**חומרה:** HIGH — שורות activity כפולות, sync שבור

### איך זה נראה
```python
async def handle_calendar_webhook(channel_id):
  sub = await session.get(Subscription, channel_id)
  changes = await google_api.events.list(sync_token=sub.sync_token)
  for change in changes.items:
    await apply_change(change)
  sub.sync_token = changes.next_sync_token  # ❌ webhook אחר בדיוק עשה את זה
  await session.commit()
```

שני webhooks מגיעים כמעט בו זמנית, שניהם קוראים את אותו `sync_token`, שניהם קוראים ל-`google_api.events.list(...)`, שניהם מחילים את אותם deltas → activities כפולות. שניהם כותבים את אותו `next_sync_token`, אבל ה-deltas שהם החילו עשויים להיות שונים.

### תיקון — CAS על ה-cursor
```python
async def handle_calendar_webhook(channel_id):
  sub = await session.get(Subscription, channel_id)
  old_token = sub.sync_token
  changes = await google_api.events.list(sync_token=old_token)

  # CAS update — להתקדם רק אם ה-cursor לא זז
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
    # webhook אחר הקדים אותנו — ה-deltas שלו כבר מוחלים; אל תחיל מחדש את שלנו
    return
  for change in changes.items:
    await apply_change(change)
  await session.commit()
```

### Commits אמיתיים
- Noa `33af59e` — שני webhooks מקבילים של Google Calendar → activities כפולות.
- Noa `cf99698` — CAS נשבר על ערך התחלתי `NULL` (Postgres `col = NULL` הוא NULL).

---

## דפוס 3 — תגובת webhook ריקה לא מקדמת cursor (Noa P9)

**חומרה:** HIGH — לולאה אינסופית, מצריכת מכסת API

### איך זה נראה
```python
async def handle(req):
  changes = await google.list(sync_token=sub.sync_token)
  if not changes.items:
    return  # ❌ next_sync_token מעולם לא נשמר, ה-webhook הבא קורא אותו cursor
  ...
```

### תיקון
גם על changes ריקים, התמד ב-`next_sync_token` אם ה-API מספק אחד.

### Commits אמיתיים
- Noa `0aff4a1`.

---

## דפוס 4 — rate limiter סומך על IP header שניתן לזיוף (CRITICAL K2)

```python
ip = request.headers["x-forwarded-for"].split(",")[0]  # ❌
if rate_limiter.is_blocked(ip): return 429
```

התוקף קובע `X-Forwarded-For: 1.2.3.4` → לכל בקשה יש "IP" שונה → rate limit לעולם לא נורה.

### תיקון
הגדר middleware של trusted-proxy ברמת ה-framework:
- FastAPI / Starlette: `app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="<comma-separated-proxy-ips>")`.
- Express: `app.set('trust proxy', <hop-count or array>)`.
- Flask: `ProxyFix(app, x_for=N)`.

ואז קרא את `request.client.host` (כבר תוקן על ידי ה-middleware).

### Commits אמיתיים
- Shipment-bot `11e7379`, routine `06ca796`.

---

## דפוס 5 — אימות signature של webhook חסר או שגוי

כל webhook נכנס מספק חיצוני חייב לוודא signature **לפני כל processing**:
- Stripe: `stripe.Webhook.construct_event(payload, sig_header, webhook_secret)`.
- Meta: HMAC-SHA256 על ה-body, השוואה עם `X-Hub-Signature-256`.
- GitHub: HMAC-SHA1 / SHA256 על ה-body, השוואה עם `X-Hub-Signature-256`.

טעויות נפוצות:
- קריאת ה-body כטקסט ו-encoding מחדש — שובר signature. השתמש ב-bytes גולמיים.
- השוואה עם `==` (timing attack). השתמש ב-`hmac.compare_digest`.
- שכחת אימות ב-endpoints של retry / replay.

(לא צוטט commit ספציפי — baseline הגנתי. הוסף לכל webhook מיום ראשון.)

---

## דפוס 6 — רכישת slot של rate-limit לפני אימות שהעבודה אמיתית

```python
limiter.acquire(channel)
result = await classify(message)
if not result.is_business:
  return  # ❌ slot בוזבז על spam
```

אם ה-limit הוא cap גלובלי על עבודה אמיתית, רכוש **אחרי** בדיקת תקפות העבודה:
```python
if not (await classify(message)).is_business:
  return
limiter.acquire(channel)
```

### Commits אמיתיים
- EmailFlow `401f179`, `cc7e81a`.

---

## דפוס 7 — race של beat scheduler + `delay()` (CORE U1 specialization)

beat (cron) trigger ו-`.delay()` של queue dispatcher יכולים שניהם לבחור את אותה שורה מסומנת `PENDING`. שניהם שולחים את ההודעה.

### תיקון
CAS update atomic:
```sql
UPDATE messages SET status='PROCESSING' WHERE id=:id AND status='PENDING' RETURNING id;
```
בדוק rowcount לפני שליחה.

### Commits אמיתיים
- Shipment-bot `457eea1`.

---

## הפניות צולבות

- **CORE U1** — race conditions (תיאוריה כללית)
- **CORE U5** — atomicity של linked-field (reserve-then-fill הוא מקרה פרטי)
- **CRITICAL K2** — XFF spoofing
- **CRITICAL K9** — שליחת credential לפני storage
- **BY-STACK/async-orm.md** — תבניות CAS
- **BY-STACK/cron-jobs.md** — race של beat-scheduler
