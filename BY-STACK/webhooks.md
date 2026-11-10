# BY-STACK: Webhooks ("מישהו קורא אליי")

## רלוונטיות — הקובץ הזה חל אם בפרויקט יש...
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
TOPIC = "gmail"  # ה-topic של Pub/Sub: message_id ייחודי רק בתוכו, ולכן הוא חלק מהמפתח

@app.post("/pubsub/gmail")
async def handle_gmail(req: Request):
  msg = parse_pubsub(req)
  key = f"{TOPIC}:{msg.message_id}"
  # 1. רזרבציה מקומית — כפילות מזוהה בהתנגשות על ה-idempotency key בלבד
  #    (insert מ-sqlalchemy.dialects.postgresql)
  draft_id = (await session.execute(
    insert(Draft).values(idempotency_key=key, status="reserved", reserved_at=func.now())
      .on_conflict_do_nothing(index_elements=["idempotency_key"])
      .returning(Draft.id)
  )).scalar_one_or_none()  # FK / CHECK / NOT NULL עדיין זורקים
  if draft_id is None:
    # המפתח כבר קיים — וזה לא אומר שהעבודה נעשתה. בודקים את מצב השורה לפני שמאשרים.
    # failed (כשל ודאי): תפיסה מחדש בעדכון אטומי — רק מסירה אחת זוכה
    draft_id = (await session.execute(
      update(Draft).where(Draft.idempotency_key == key, Draft.status == "failed")
        .values(status="reserved", reserved_at=func.now()).returning(Draft.id)
    )).scalar_one_or_none()
    if draft_id is None:
      status = (await session.execute(
        select(Draft.status).where(Draft.idempotency_key == key)
      )).scalar_one()
      await session.commit()
      if status == "created":
        return Response(status_code=200)  # הושלם — כפילות אמיתית
      return Response(status_code=503)    # reserved / unknown: לא 2xx, כדי שהספק ימסור שוב
  await session.commit()  # הרזרבציה נשמרת לפני הקריאה החיצונית

  # 2. הקריאה החיצונית — לבדה ב-try, כדי שהמצב ישקף רק את התוצאה שלה
  try:
    gmail_draft = await gmail.drafts.create(body=msg.body)
  except Exception as exc:
    # ProviderRejected — החריגה של הלקוח שלך לדחייה מפורשת (4xx): הספק לא ביצע, כשל ודאי.
    # כל השאר — timeout, חיבור שנותק, תשובה לא קריאה — לא ידוע אם ה-draft נוצר
    outcome = "failed" if isinstance(exc, ProviderRejected) else "unknown"
    await session.execute(update(Draft).where(Draft.id == draft_id).values(status=outcome))
    await session.commit()
    raise  # 5xx לספק — הוא ימסור שוב, והמסירה הבאה תפעל לפי המצב

  # 3. fill
  await session.execute(
    update(Draft).where(Draft.id == draft_id).values(gmail_id=gmail_draft.id, status="created")
  )
  await session.commit()
  return Response(status_code=200)
```

לא תופסים `IntegrityError` גורף כ"כפילות": הוא נזרק גם על FK, ‏CHECK ו-NOT NULL, ו-200 עליהם מאשר לספק webhook שנזרק. ‏`ON CONFLICT (idempotency_key) DO NOTHING RETURNING id` מחזיר שורה ריקה רק על התנגשות במפתח הזה, וכל שגיאה אחרת עולה (נמדד ב-SQLAlchemy 2.1.8 עם asyncpg מול Postgres 16, נובמבר 2026). העמודה `idempotency_key` היא UNIQUE ו-NOT NULL: בלי אינדקס ייחודי תואם Postgres דוחה את ה-INSERT עצמו (`there is no unique or exclusion constraint matching the ON CONFLICT specification` — נמדד), ו-NULL אינו מתנגש עם NULL — מפתח חסר היה עובר כרשומה חדשה. 

**מפתח שכבר קיים אינו אומר שהעבודה נעשתה.** מסירה חוזרת מגיעה בדיוק אחרי כשל, ולכן 200 אוטומטי על התנגשות זורק את האירוע: השורה נשארת `failed`, ‏`unknown` או `reserved`, הספק מקבל אישור, ומסירה נוספת לא תגיע. לכן בהתנגשות בודקים את מצב השורה. `created` — הושלם, 200. `failed` — כשל ודאי: תופסים מחדש בעדכון אטומי שמחזיר אותה ל-`reserved` (`UPDATE ... SET status='reserved' WHERE status='failed'`), ורק המסירה שהעדכון שלה תפס שורה מבצעת שוב. `reserved` — מסירה אחרת באמצע הטיפול: תשובה שאינה 2xx, והספק ימסור שוב. `unknown` — לא ידוע אם הספק ביצע: גם כאן לא 2xx, ובלי ביצוע חוזר עיוור. השורה מחכה לבירור מול הספק — חיפוש הפעולה לפי מזהה שלנו, או קריאה חוזרת עם אותו מפתח idempotency כשהספק תומך בזה — ורק הבירור מעביר אותה ל-`created` או ל-`failed`.

**הבירור הוא ג'וב נפרד, והוא חלק מהתיקון.** ה-handler רק מסמן ומחזיר 503; בלי הג'וב, שורה `unknown` — או `reserved` של תהליך שמת אחרי הרזרבציה, או של fill שנכשל — תחזיר 503 לכל מסירה חוזרת עד שהספק יתייאש, בלי התראה. לכן הרזרבציה והתפיסה מחדש כותבות `reserved_at`, והג'וב בוחר לפיו גם `reserved` שנשאר מעבר לזמן הטיפול המרבי במסירה אחת — לא ידוע אם הספק ביצע, בדיוק כמו ב-`unknown`:

```sql
SELECT id FROM drafts
 WHERE status = 'unknown'
    OR (status = 'reserved' AND reserved_at < now() - interval '5 minutes');
```

המרווח ארוך מה-timeout מול הספק, אחרת הג'וב תופס מסירה שעוד בטיפול. ושורה שהג'וב לא הצליח לברר מדווחת לאדם — היא לא נשארת בתור בשקט.

**`failed` מסומן רק על דחייה מפורשת של הספק, וכל חריגה אחרת היא `unknown`.** תשובה שאבדה — timeout, חיבור שנותק אחרי השליחה — אינה כשל ודאי: ייתכן שהספק יצר את ה-draft. ומכיוון ש-`failed` פירושו "מותר לבצע שוב", ‏`except Exception` שמוביל אליו היה הופך כל timeout ל-draft כפול (`RECURRING-PATTERNS.md` R10). מאותה סיבה הקריאה החיצונית יושבת לבדה ב-`try`: כשל ב-fill אחרי שהספק כבר ביצע אינו `failed`.

נמדד ב-SQLAlchemy 2.1.8 עם asyncpg מול Postgres 16, נובמבר 2026. אחרי דחייה, המסירה החוזרת ביצעה שוב והסתיימה ב-`created`. אחרי timeout ואחרי קריסה שאחרי הרזרבציה היא קיבלה 503, בלי קריאה נוספת לספק. תשע מסירות מקבילות — על מפתח חדש, ועל שורה `failed` — הסתיימו בקריאה אחת לספק. שאילתת הג'וב החזירה את שורת ה-timeout מיד, ואת השורה שקרסה רק אחרי שעבר המרווח. ובריצת בקרה על הצורה הקודמת, עם 200 אוטומטי על התנגשות: אחרי דחייה ואחרי timeout המסירה החוזרת קיבלה 200, והשורה נשארה `failed` / `unknown`.

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

### תיקון — CAS על ה-cursor, וסנכרון מחדש כשהוא נכשל
```python
async def handle_calendar_webhook(channel_id):
  for _ in range(MAX_CAS_ATTEMPTS):
    old_token = (await session.execute(
      select(Subscription.sync_token).where(Subscription.id == channel_id)
    )).scalar_one()  # קריאה טרייה מהמסד, לא מה-identity map
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
    if result.rowcount == 1:
      # apply_change רץ על אותה session ובלי commit משלו: ה-CAS וכל השינויים נשמרים יחד, או אף אחד
      for change in changes.items:
        await apply_change(change)
      await session.commit()
      return
    # webhook אחר הקדים. ה-deltas שלנו חושבו מסמן ישן, וה-deltas שלו עשויים לכסות פחות
    # משלנו — לכן לא מוותרים: קוראים את הסמן החדש ומסנכרנים ממנו שוב.
    await session.rollback()
  raise CursorContention(channel_id)
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
- Express: `app.set('trust proxy', <hop-count or array>)` — hop count רק כשכל בקשה עוברת בדיוק אותו מספר proxies מהימנים, וכל אחד מהם מוסיף לכותרת את הכתובת שראה (CRITICAL K2); כתובת הלקוח היא `req.ip`.
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
- שכחת אימות במשלוח חוזר מהספק. ‏replay פנימי של אירוע שכבר אומת ונשמר — מאחורי הרשאה משלו, לא על החתימה המקורית: ב-Stripe ‏`construct_event` דוחה חתימה ישנה מ-`tolerance`, 300 שניות כברירת מחדל.

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

### ראה גם
- `bugbot-rules/body-read-outside-cheap-reject.md` — אותו עיקרון (**השער לפני ההוצאה**) בחתימה אחרת: שכבה שקוראת גוף בקשה שהותקנה מחוץ לשכבה שדוחה מהכותרות. שם הבדיקה הזולה היא הכותרות; כאן דווקא הבדיקה היא היקרה (סיווג ב-LLM), ולכן אלה שני דפוסים ולא אחד.

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
