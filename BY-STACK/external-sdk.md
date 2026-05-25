# BY-STACK: SDKs חיצוניים (Anthropic, Google, Stripe, OAuth, push notifications)

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...
- ✅ קריאות SDK של Anthropic / OpenAI / LLM אחר
- ✅ APIs של Google (Calendar, Gmail, OAuth, Sheets, FCM, web-push)
- ✅ SDKs של Stripe, Twilio, Telegram, Slack, Meta
- ✅ ניתוח של תגובות API, payloads של webhook, או JSON שנוצר על ידי AI
- ✅ אתחול SDK בזמן startup עם env vars / keys
- ⏭ דלג אם: לפרויקט אין אינטגרציות צד שלישי

> Cross-link: **CORE U3** (ולידציה של external input) הוא הכלל הכללי; הקובץ הזה מכסה מופעים ספציפיים ל-SDK. **R4** (שלמות exception של SDK) חי כאן לעומק.

---

## מודל מנטלי

כל SDK חיצוני הוא שני גבולות:
1. **קריאה יוצאת** — הקוד שלך → SDK → רשת. יכול להיכשל עם היררכיית exceptions של ה-SDK, שגיאות רשת, או timeout.
2. **נתונים נכנסים** — SDK → הקוד שלך. יכול להחזיר צורות שונות ב-test/sandbox/prod, יכול לכלול nulls/שדות חסרים, ו-type hints של ה-SDK הם שאפתניים.

קוד הגנתי בשני הגבולות הוא מחיר הכניסה.

---

## דפוס 1 — תפיסת base צר מדי ב-`except` (R4)

```python
try:
  result = await anthropic.messages.create(...)
except RateLimitError:
  await asyncio.sleep(BACKOFF); retry
except _RETRYABLE_ERRORS:
  retry
# ❌ subtypes של APIError (NotFound, BadRequest, Auth) עוברים בלי טיפול
```

### תיקון
תפוס את ה-base class של ה-SDK, ואז עדן:
```python
try:
  result = await anthropic.messages.create(...)
except RateLimitError:
  retry
except APIError as e:
  if e.status_code == 400: handle_bad_request(e)
  else: raise
```

סדר את בלוקי ה-`except` subclass-לפני-superclass.

### Commits אמיתיים
- Noa `c128115` — שלמות exception של Anthropic SDK.
- Noa `95dcce6` — fallback בלע `RateLimitError` כ-`AIError` גנרי.

---

## דפוס 2 — `CancelledError` לא נתפס על ידי `Exception` (Python ≥ 3.8)

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for r in results:
  if isinstance(r, Exception):  # ❌ מפספס CancelledError
    handle_error(r)
  else:
    count_success += 1  # ❌ tasks מבוטלים נספרים כהצלחה
```

`asyncio.CancelledError` יורש מ-`BaseException` (לא `Exception`) מאז Python 3.8.

### תיקון
```python
for r in results:
  if isinstance(r, BaseException):
    handle_error(r)
```

### Commits אמיתיים
- Shipment-bot `e0f4d59`.

---

## דפוס 3 — `isinstance(r, SendResult)` מול `r is True`

```python
if r is True: count_success += 1  # ❌ אובייקט SendResult, לא bool
```

### תיקון
ממש `__bool__` על מחלקת התוצאה, או השווה במפורש:
```python
if isinstance(r, SendResult) and r.ok: count_success += 1
```

### Commits אמיתיים
- Shipment-bot `11e7379`.

---

## דפוס 4 — אתחול SDK בזמן startup קורס את השרת (R4)

```python
# ב-import time
webpush.set_vapid_details(
  subject=settings.VAPID_EMAIL,
  public_key=settings.VAPID_PUBLIC_KEY,
  private_key=settings.VAPID_PRIVATE_KEY,
)
```

אם `VAPID_EMAIL` חסר prefix של `mailto:`, או keys פגומים, זה זורק ב-import → כל השרת קורס ב-boot. אותו דבר ל-OAuth client init, Stripe client init.

### תיקון
עטוף ב-try/except + ולידציית פורמט:
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

הורד את ה-*פיצ'ר*, לא את כל השרת.

### Commits אמיתיים
- routine `e5c26ad`, `2571c91`.

---

## דפוס 5 — regex על JSON של AI / SDK (CORE U3)

```python
match = re.search(r"\{.*\}", ai_response, re.DOTALL)  # ❌ חמדן; נשבר על prose
data = json.loads(match.group(0))
```

`\{.*\}` חמדן. `}` סוגר ב-prose (`"... and finally }"`) דולף לתוך ה-match. אובייקטים מקוננים, escape sequences גם שוברים.

### תיקון
```python
decoder = json.JSONDecoder()
start = ai_response.find("{")
if start < 0: raise ValueError("no JSON")
data, _ = decoder.raw_decode(ai_response[start:])
```

### Commits אמיתיים
- Noa `f27adc1`.

---

## דפוס 6 — isinstance guards על תגובות חיצוניות (CORE U3)

```python
data = response.json()
items = data.get("messages", [])  # ❌ אם data הוא רשימה, .get קורס
```

### תיקון
```python
data = response.json()
if not isinstance(data, dict):
  raise ValueError(f"expected dict, got {type(data)}")
items = data.get("messages", [])
if not isinstance(items, list):
  raise ValueError("messages not a list")
```

### Commits אמיתיים
- EmailFlow `6b7dbeb`, `46d05f7`, `55b4328`, `018b166`.

---

## דפוס 7 — env / config flags של SDK שלא כובדו

חלק מה-SDKs דורשים env-var flags כדי לטפל ב-edge cases של עולם אמיתי:
- `OAUTHLIB_RELAX_TOKEN_SCOPE=1` — סטיית scope של OAuth בספריות Google (Noa `95b82e5`).
- `OAUTHLIB_INSECURE_TRANSPORT=1` — רק ל-dev מקומי (HTTP callbacks).
- `STRIPE_API_VERSION` — pin כדי למנוע שינויי-שבירה שקטים.
- `ANTHROPIC_LOG=debug` — logs verbose.

תעד את אלה בהגדרות הפרויקט שלך והתייחס ל-scope-drift / version-skew כ-events תפעוליים צפויים, לא exceptions.

---

## דפוס 8 — אי-התאמת Pydantic schema על enum חיצוני (מקושר ל-state-machine.md דפוס 4)

```python
class LeadDraft(BaseModel):
  service_category: ServiceCategoryEnum  # strict; דוחה לא מוכר
```
AI מחזיר `"unknown"` → Pydantic דוחה → ה-draft כולו (כולל `full_name` ו-`phone` תקפים) הולך לאיבוד.

### תיקון
לערכי enum ממקור חיצוני, קבל `str | None` ועשה ולידציה idempotent ב-caller. שמור enums strict לשדות פנימיים בלבד.

### Commits אמיתיים
- Noa `7001892`, `f6293e3`, `dc24922`.

---

## דפוס 9 — Walrus + בדיקת truthy על env var

```python
if override := os.environ.get("OVERRIDE_VALUE"):  # ❌ "" הוא falsy אבל override תקף
  apply(override)
```

`""` הוא ערך משמעותי ("override ל-empty"), אבל ה-walrus מתייחס אליו כ-`None`.

### תיקון
```python
override = os.environ.get("OVERRIDE_VALUE")
if override is not None:
  apply(override.strip())
```

### Commits אמיתיים
- Noa `236b072`.

---

## הפניות צולבות

- **CORE U3** — ולידציה של boundary (תיאוריה כללית)
- **R4** — שלמות exception של SDK (הקובץ הזה הוא ה-deep-dive)
- **BY-STACK/state-machine.md** — אי-התאמת Pydantic schema
- **`bugbot-rules/external-input-isinstance.md`**, **`sdk-error-completeness.md`**
