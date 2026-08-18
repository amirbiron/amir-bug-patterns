# דפוסים קריטיים (CRITICAL)

דפוסי באגים בחומרה גבוהה — **תמיד החל, ללא קשר ל-stack או לתדירות במסמכי המקור.** חומרה אבטחתית, אובדן נתונים, פרטיות, פיננסי, או זמינות קטסטרופלית.

חלק מהם הופיעו רק במסמך מקור אחד (סריקת 8-הפרויקטים, שבה עבודת אבטחה נסקרה באופן שיטתי). **החומרה שלהם מצדיקה הצבה בדרג העליון גם כשהתדירות צרה**. כל אחד מתויג עם בסיס הראיות שלו.

---

## K1. השתלטות על חשבון OAuth דרך flow של signup

**מקור:** 8-Projects C1 (routine — commit `8a39df6`)
**חומרה:** CRITICAL — השתלטות מלאה על חשבון

### איך זה נראה
flow של signup מאפשר קביעת סיסמה לחשבון שכבר קיים דרך OAuth, ודורש רק את כתובת ה-email כקלט. תוקף שיודע את ה-email של משתמש OAuth יכול:
1. לשלוח signup עם ה-email הזה + סיסמה חדשה.
2. להתחבר עם email/password מאז ואילך, ולעקוף את OAuth.

### כלל לזיהוי
לכל endpoint של "set password" / "register" / "link account" שמקבל email:
1. אם חשבון קיים תחת ה-email דרך OAuth (או כל ספק זהות אחר), **דחה** את קביעת הסיסמה אלא אם הבקשה מאומתת כאותו משתמש או כוללת קישור one-time מאומת שנשלח ל-email שמקושר ל-OAuth.
2. ידיעת ה-email לבדה אף פעם לא מספיקה להעברת privilege.

### ראה גם
- `bugbot-rules/auth-before-irreversible-action.md`
- `bugbot-rules/privilege-escalation-unverified.md`

---

## K2. עקיפת rate limiter דרך זיוף X-Forwarded-For

**מקור:** 8-Projects C2 (Shipment-bot `11e7379`, routine `06ca796` — שני פרויקטים)
**חומרה:** CRITICAL — בקרת אבטחה נעקפת

### איך זה נראה
ה-rate limiter קורא `X-Forwarded-For` (או `X-Real-IP`) ישירות מהבקשה בלי לוודא שה-peer המיידי הוא proxy אמין. התוקף מזייף את ה-header → כל בקשה נראית מגיעה מ-IP שונה → אין הגבלה.

### כלל לזיהוי
בכל מקום שהקוד משתמש ב-`request.headers["x-forwarded-for"]` או שווה ערך להחלטות security / rate-limit / abuse:
1. ה-framework חייב להיות מוגדר עם רשימה מפורשת של proxies אמינים (Starlette `ProxyHeadersMiddleware` עם `trusted_hosts`; Express `app.set('trust proxy', <list>)`; Flask `ProxyFix(... trusted_hops=N)`).
2. **לעולם** אל תסמוך על כל ה-chain של `X-Forwarded-For`; סמוך רק על הסגמנטים מימין השווים למספר ה-hops שמוגדר.
3. אם אין proxy מקדים, השתמש ב-`request.client.host` / `req.socket.remoteAddress` בלבד.

### ראה גם
- `BY-STACK/webhooks.md` — סעיף על זהות הקורא
- `bugbot-rules/rate-limit-xff-spoofing.md`

---

## K3. הסלמת הרשאות — auto-admin לפי email לא מאומת

**מקור:** 8-Projects C10 (Markdown-Academy — commit `4623bdb`)
**חומרה:** CRITICAL — תפקיד admin ניתן לתוקף

### איך זה נראה
ב-registration, הקוד בודק אם ה-email שסופק שווה ל-email של "owner / admin" שמוגדר. אם כן, המשתמש החדש מקבל תפקיד admin — **לפני** שה-email אומת. תוקף שיודע את ה-email של ה-owner יוצר חשבון, לעולם לא מאשר email, והוא admin.

### כלל לזיהוי
כל נתיב קוד שמעניק תפקיד מוגבר (admin / staff / owner / super_user) חייב:
1. להיות נגיש **רק אחרי** email verification (verification token תקף, `email_verified_at` מסומן).
2. או להיות gated על ידי פעולה out-of-band של admin קיים (קישור invite + token).
3. לעולם לא לסמוך על `request.body.email == OWNER_EMAIL` בזמן registration.

### ראה גם
- `bugbot-rules/privilege-escalation-unverified.md`

---

## K4. XSS דרך `innerHTML` עם display name של משתמש

**מקור:** 8-Projects C9 (Facebook-Leads-New — commit `6a6ec51`)
**חומרה:** CRITICAL — DOM XSS בפאנל admin

### איך זה נראה
`renderBlockedUsers` (או כל פאנל admin/פנימי) השתמש ב-`element.innerHTML = '<div>' + user.name + '</div>'` עם שם שמקורו במערכת חיצונית (Facebook display name). משתמש עם שם `<script>alert(1)</script>` מריץ script בקונטקסט של ה-admin.

### כלל לזיהוי
1. `.innerHTML = ` / `dangerouslySetInnerHTML` / `v-html` עם מחרוזת שכוללת ערך כלשהו ממקור חיצוני (תגובת API, שורת DB, URL param, `localStorage`) → דווח.
2. ברירת מחדל: `textContent` / text nodes ב-JSX של React.
3. אם HTML באמת נדרש, הערך חייב לעבור דרך `DOMPurify` (או שווה ערך) באותה שורה של ההשמה.
4. "Admin only" אינה הגנה — admins הם בדיוק היעדים של XSS.

### ראה גם
- `BY-STACK/react-frontend.md` — סעיף DOM
- `bugbot-rules/xss-innerhtml.md`

---

## K5. פאנל admin חשוף לרשת בלי auth

**מקור:** 8-Projects C11 (Amazon-bot — commits `85776b5`, `c27c769`)
**חומרה:** CRITICAL — RCE / שליטת admin לכל מי שברשת

### איך זה נראה
שרת Flask / FastAPI / Express שמאזין ב-`0.0.0.0` ("listen on all interfaces") בלי token gate, בלי בדיקת `Authorization` header, בלי IP allowlist. כל מי שמגיע ל-port יכול להשתמש בפאנל.

### כלל לזיהוי
לכל עליית שרת HTTP:
1. אם נקשר ל-`0.0.0.0` / `::` / "all interfaces" → דרוש או (a) middleware של אימות שדוחה בקשות לא מאומתות *לפני* שכל route רץ, או (b) firewall / ingress שחוסם גישה חיצונית.
2. אם אף אחד לא מוגדר → קשר ל-`127.0.0.1` / `localhost` בלבד.
3. ברירת מחדל: localhost ב-dev; דרוש env var מפורש לקישור פומבי.

### ראה גם
- `bugbot-rules/network-exposed-without-auth.md`

---

## K6. password hash / secret נדלף ב-response או error message

**מקור:** 8-Projects C6 (routine `06ca796`), C24 (Shipment-bot `59a5e3c`)
**חומרה:** CRITICAL — חשיפת חומר סודי

### איך זה נראה
- middleware של `ctx.user` חשף את שורת ה-ORM המלאה כולל שדה `passwordHash`. כל endpoint שעושה serialization למשתמש (profile, comments author, mentions) דלף hashes.
- `InsufficientCreditError.to_dict()` כלל את `self.message = "Insufficient credit for courier {id}"` — UUID פנימי של courier נחשף ב-response של ה-API.

### כלל לזיהוי
1. Serialization של משתמש / actor חייב לעבור דרך DTO / Pydantic response model מפורש שמפרט רק את השדות המותרים. ORM row → JSON אסור בגבולות API.
2. שמות שדות אסורים בכל מקום ב-response של API: `password`, `passwordHash`, `password_hash`, `salt`, `refresh_token`, `access_token`, `api_key`, `secret`, `private_key`.
3. מחלקות exception שעלולות להיזרק בגבולות API לא יכולות לכלול IDs פנימיים / hostnames / סיבות heuristic ב-message הפומבי שלהן. דפוס: `class XError(AppException): public_message: str  # safe;  detail: dict  # server-only`.

### ראה גם
- `bugbot-rules/secret-in-error-response.md`
- K13 — הקצה השני: סוד שדולף לערוצים פנימיים (לוגים/Sentry) דרך מחרוזת נגזרת

---

## K7. PII בלוגים וב-API responses

**מקור:** EmailFlow P5 (מסמך בעברית) + 8-Projects C6, C24, C57 — **RECURRING לפי תדירות, CRITICAL לפי חומרה**
**חומרה:** CRITICAL — פרטיות / GDPR / compliance

### איך זה נראה
- `logger.info("sending email to %s", user.email)` — email הוא PII; שורד ב-log aggregator לנצח.
- `HTTPException(detail=str(exc))` — מחרוזת exception פנימית עם stack trace דולפת ללקוח.
- `summary: "heuristic: esp:mailchimp.com"` ב-response של API — חושף לוגיקה פנימית של classification.
- הודעות שגיאה באנגלית עם stack traces שמוצגות למשתמשי קצה (במקום הודעה מתורגמת גנרית).

### כלל לזיהוי
בכל קריאת `logger.*()` וב-`HTTPException` `detail` / body של response:

**אסור בלוגים (או ב-response של API):**
- `email`, `phone`, `from_email`, `to_email`, שדות כתובת, שדות שם.
- תוכן body של email / chat / messages.
- OAuth tokens גולמיים, `refresh_token`, `access_token`, API keys.

**אסור ב-response של API בלבד (לוגים בסדר אם יש בקרת גישה ללוגים):**
- סיבות heuristic להחלטה (`'esp:mailchimp.com'`, `'spam_score=0.8'`).
- UUIDs פנימיים של DB של tenants / users אחרים.
- Stack traces, שמות מחלקות exception, הודעות framework.
- שברי SQL.

**החלפות:**
- PII → רק *domain* של email, או hash לא הפיך, או user_id משלך.
- לוגיקה פנימית → הודעת שגיאה מתורגמת גנרית.
- IDs פנימיים → רק IDs של המשאבים של המשתמש *הנוכחי*.

### ראה גם
- `RECURRING-PATTERNS.md` מציין שזה הדפוס היחיד מ-RECURRING שגם קודם ל-CRITICAL.
- `bugbot-rules/pii-in-logs.md`

---

## K8. LIKE wildcard injection ב-prefix של משתמש

**מקור:** 8-Projects C12 (Facebook-Leads-New — commit `2f45eca`)
**חומרה:** CRITICAL — מניפולציה של query / חשיפת נתונים

### איך זה נראה
`get_config_by_prefix(prefix)` הריץ `WHERE key LIKE :prefix || '%'`. SQL `LIKE` מתייחס ל-`_` כ-"כל תו יחיד" ול-`%` כ-"כל רצף". prefix מהמשתמש כמו `test_key` תפס גם `test_key_foo` וגם `testXkey_foo` — ו-prefix של `%` היה תופס הכל.

### כלל לזיהוי
לכל סעיף `LIKE` שנבנה מקלט משתמש:
1. ברח מ-`_` ומ-`%` (ומתו ה-escape עצמו) בקלט: `prefix.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')` ושימוש ב-`LIKE :p ESCAPE '\\'`.
2. או שכתב להתאמה מדויקת (`=`) אם חיפוש prefix לא באמת נדרש.
3. SQLAlchemy: השתמש ב-`column.startswith(value, autoescape=True)` במקום `LIKE` ידני.

### ראה גם
- `BY-STACK/postgres.md`
- `bugbot-rules/like-wildcard-injection.md`

---

## K9. credential auth נשלח לפני storage (OTP / link / token)

**מקור:** 8-Projects C4 (Shipment-bot — commits `552f0f7`, `155aa81`)
**חומרה:** HIGH — חוסר עקביות ב-lifecycle של auth, אפשרות לעקיפה דרך נתיב אימות חלופי

### איך זה נראה
סדר הפעולות:
1. ייצור OTP.
2. שליחה דרך SMS / email (בלתי הפיך).
3. שמירה ב-Redis / DB.

אם שלב 3 נכשל (Redis למטה, שגיאה זמנית), למשתמש יש קוד אמיתי ביד אבל אף verifier לא יוכל להתאים אותו. גרוע מכך, אם יש נתיב fallback "דלג על OTP" שמופעל על "Redis miss", התוקף שיכול לגרום ל-Redis להיות flaky מקבל עקיפה.

### כלל לזיהוי
כל flow של "ייצור + שליחה של credential" חייב:
1. להתמיד (Redis SET / DB INSERT עם TTL) **לפני** השליחה החיצונית.
2. אם ההתמדה נכשלת, לא לשלוח.
3. אין נתיב "fallback" שממשיך כשאחסון verification לא בר השגה — fail closed.

הכללה: כל triplet של "reserve / dispatch / store" שהפעולה החיצונית בו בלתי הפיכה — ראה CORE U1 (reserve-then-fill).

### ראה גם
- `CORE-PATTERNS.md` U1
- `BY-STACK/webhooks.md`
- `bugbot-rules/auth-before-irreversible-action.md`

---

## K10. 500 גנרי מוצג כ-"invalid credentials"

**מקור:** 8-Projects C57 (Web — commit `5196657`)
**חומרה:** HIGH — security UX + סיוע לאיתור משתמשים + מסתיר outages אמיתיים

### איך זה נראה
Handler של login:
```js
catch (err) {
  if (err.status === 500) showError("Invalid username or password");
  if (err.status === 401) showError("Invalid username or password");
}
```
כל כשל DB, רעש רשת, או באג ב-backend מופיע כ-"wrong password". שלוש תוצאות:
1. Outage אמיתי בלתי נראה ל-ops (משתמשים אומרים "הסיסמה שלי לא עובדת").
2. עוזר לתוקפים שמחפשים enumeration של חשבונות (כל email נראה "שגוי").
3. משתמשים נועלים את עצמם מחוץ לחשבונות אמיתיים בניסיון "לאפס" סיסמאות שכן עובדות.

### כלל לזיהוי
טיפול בשגיאות login / auth חייב להסתעף:
- `401 / 403` → "Invalid credentials" (גנרי, לא דולף אם ה-email קיים).
- `5xx` → "Service temporarily unavailable. Please try again in a moment." + התראה למוניטורינג.
- `429` → "Too many attempts. Try again in N minutes."

לעולם אל תאחד `5xx` ל-"invalid credentials".

### ראה גם
- `bugbot-rules/auth-before-irreversible-action.md` (סעיף auth UX)

---

## K11. כשל שמדווח בערך החזרה נבלע — הצלחה מדומה למשתמש

**מקור:** CodeBot P1 (PR #3232, PR #3172, ומופע cache invalidation) — 3 מופעים באותו ריפו
**חומרה:** HIGH — אובדן נתונים שקט: המשתמש מקבל אישור על פעולה שלא קרתה

### איך זה נראה
פונקציה מסמנת כשל בערך החזרה — `None`, `False`, `0`, `[]`, rowcount — ולא
בזריקת חריגה. הקורא עוטף אותה ב-`try/except`, מניח ש"לא נזרקה חריגה" פירושו
הצלחה, ומדווח ✅:

```python
try:
    saved = await asyncio.to_thread(backup_manager.save_backup_bytes, raw, metadata)
    saved = True                     # save_backup_bytes מחזיר None בכשל — לא זורק
except Exception:
    await notify_failure()           # לא ירוץ לעולם
# המשתמש רואה "✅ נשמר גיבוי" על גיבוי שלא נשמר
```

הנזק הקשה הוא לא הכשל עצמו אלא **האישור השקרי**: משתמש שסומך על גיבוי
שאינו קיים, קאש שמוגש כמעודכן אחרי invalidation שמחק 0 מפתחות, "נשלח"
שלא נשלח. ה-try/except המיותר מחמיר — הוא משדר לקורא הבא "הכשל מטופל".

### כלל לזיהוי
לכל קריאה שעטופה ב-try/except או שאחריה דיווח הצלחה:
1. בדוק את מסלול הכשל של הפונקציה הנקראת — זורקת או מחזירה falsy? (הקובע
   הוא החוזה של הפונקציה, לא הערך: `0` מ-invalidation שאמור למחוק הוא
   כשל, `0` ממחיקה אופורטוניסטית הוא תקין.)
2. אם מחזירה falsy בכשל: חובה `if not result:` אחרי הקריאה, לפני כל דיווח הצלחה.
3. דגל אדום: השמת דגל הצלחה קבוע (`saved = True`) מיד אחרי הקריאה.
4. בכתיבת פונקציה חדשה: בחר ערוץ כשל אחד — עדיף זריקה — ותעד אותו ב-docstring.

### False positives
- פונקציות raise-on-error מתועדות — שם try/except הוא הערוץ הנכון.
- fire-and-forget מוצהר (מטריקות, לוגים) שכשל שקט מקובל בו.

### מצב מומלץ
**strict** בכל נתיב שמסתיים בהודעת הצלחה למשתמש או בכתיבת נתונים.

### ראה גם
- `bugbot-rules/return-value-failure-unchecked.md`
- `bugbot-rules/sdk-error-completeness.md` §3 — קרוב המשפחה בעולם ה-SDK: כשלים שחוזרים כערכים מ-`gather(return_exceptions=True)`
- `CORE-PATTERNS.md` U1 — בדיקת rowcount אחרי CAS היא מופע של אותו עקרון

---

## K12. שאילתה רב-דיירית בלי tenant scope — דליפה בין לקוחות

**מקור:** EmailFlow (3 מופעי auth/tenant isolation, HIGH — נספח "מחוץ ל-Top 7"); הקשר חי: ai-business-bot (ContextVar של tenant עם `default=None`)
**חומרה:** CRITICAL — דליפת נתונים בין לקוחות: הלקוח של דנה רואה את הלידים של יוסי

### איך זה נראה
במערכת רב-דיירית, שאילתה אחת ששכחה `WHERE tenant_id = :current` מספיקה כדי שנתוני לקוח אחד יגיעו ללקוח אחר. הדליפה שקטה לגמרי — אין חריגה, אין לוג, התשובה "תקינה" רק עם נתונים של מישהו אחר. שלושת המסלולים הקלאסיים:

1. **get-by-id בלי scope.** `SELECT ... WHERE id = :id` — ה-id הגיע מהלקוח, וכל מי שמנחש/מונה ids קורא שורות של דיירים אחרים (IDOR).
2. **נתיב משני שנשכח.** ה-list הראשי מסונן, אבל ה-export / החיפוש / ה-aggregation / ה-webhook handler — לא. הבידוד חזק בדיוק כמו השאילתה הכי חלשה.
3. **Context של tenant עם fallback שקט.** `ContextVar("tenant", default=None)` או `default=DEFAULT_TENANT` — נתיב ששכח לקבוע context לא נכשל, הוא רץ על הדייר הלא נכון. גרוע מדליפה: כתיבה לדייר הלא נכון.

### כלל לזיהוי
1. חוזה לפי סוג הפעולה, בטבלה עם עמודת `tenant_id`/`account_id`/`org_id`: **SELECT / UPDATE / DELETE** — predicate על ה-tenant המאומת בכל שאילתה, כולל get-by-id, exports, aggregations, חיפוש ומחיקות. **INSERT / UPSERT** — אין WHERE שיציל אותך: ה-`tenant_id` הנכתב נגזר מה-context המאומת של הבקשה, לעולם לא מערך שהגיע מהלקוח; וב-UPSERT מפתח ה-conflict כולל את ה-tenant, אחרת דייר אחד דורס שורה של אחר.
2. עדיף אכיפה מרכזית על משמעת נקודתית: scoped session / query builder שמזריק את הסינון, RLS ב-Postgres, או repository שמקבל tenant כפרמטר חובה.
3. Context של tenant: **fail-closed** — בלי default; נתיב בלי context זורק, לא נופל בשקט לברירת מחדל. דגל `TENANCY_STRICT` כבוי בפרודקשן = הדפוס הזה בהמתנה.
4. מפתחות cache, session, וקבצים זמניים כוללים את ה-tenant — אחרת ה-cache מגיש נתוני דייר אחד לאחר.
5. בדיקת בידוד היא בדיקת חובה: שני tenants **סינתטיים** על מסד בדיקה זמני, פעולה זהה, ואימות ששום תשובה לא מכילה נתונים של השני. שלב ה-T2 — הרצה עם ההגנה כבויה כדי לוודא שהבדיקה נופלת — רץ **רק** ב-local או ב-CI על המסד הזמני; לעולם לא בפרודקשן, ב-staging, או בכל סביבה עם נתונים משותפים.

### False positives
- טבלאות גלובליות באמת (קונפיג מערכת, קטלוג ציבורי) — מסומנות ככאלה במפורש.
- קוד admin שמוצהר ומאובטח ככזה (עם audit log), שסורק את כל הדיירים בכוונה.

### מצב מומלץ
**strict** על כל טבלה עם עמודת tenant. אין warning-period לדפוס הזה — הדליפה הראשונה היא כבר אירוע אבטחה.

### ראה גם
- `bugbot-rules/tenant-row-scoping.md`
- `CORE-PATTERNS.md` U5 — עדכון חלקי (הכתיבה מסוננת, הלוג לא)
- `bugbot-rules/privilege-escalation-unverified.md` — הקצה השני: מי בכלל מקבל להיות באיזה tenant

---

## K13. סוד רוכב על מחרוזת נגזרת — דליפה ללוגים ול-Sentry דרך הודעות שגיאה

**מקור:** CodeBot Pattern 5 (PR #3234, אוגוסט 2026)
**חומרה:** CRITICAL — חשיפת credential בערוצי תצפית, בלי שאף שורה "רושמת סוד" במפורש

### איך זה נראה
- URL של Telegram Bot API (`.../bot<TOKEN>/method`) הוצמד להודעת חריגה
  (`msg += f" url={url}"`) ולשדה `e.url`. כל כשל רשת נשא את הטוקן המלא
  ללוגים, ל-traceback ולאירועי Sentry.
- הניקוי שהיה קיים נכשל-פתוח: סריקה לפי שמות שדות שמפספסת את גוף
  החריגה, `except: pass` שמחזיר את הערך הגולמי, וניקוי עמוק שמחזיר את
  המקור בטיפוס לא מוכר.

### כלל לזיהוי
1. כל f-string שמרכיב URL/פקודה/DSN עם סוד (`f"...{token}..."`) — לעקוב
   לאן הערך זורם. אם הוא מגיע להודעת חריגה, ללוג או לשדה על אובייקט
   חריגה — חובה לנקות **בנקודת ההרכבה או בהשמה**, לא אצל הצרכנים.
2. מנגנון ניקוי (redaction) חייב להיכשל-סגור: כשל המרה מחזיר placeholder;
   כשל ב-before_send מפיל את האירוע; טיפוס לא מוכר לא חוזר גולמי אם
   הייצוג הטקסטואלי שלו נושא סוד.
3. סריקה לפי שמות שדות (`if "token" in key`) אינה ניקוי — גוף חריגה,
   breadcrumbs ו-repr של אובייקטים לא עוברים דרכה. סורקים את המבנה כולו.

### מצב מומלץ
נקודת ניקוי מרכזית אחת; החריגה מנקה את שדותיה בהשמה; רשימת דפוסים אחת
ללוגים (הודעה + traceback); before_send נכשל-סגור עם אזהרה.

### ראה גם
- `bugbot-rules/secret-in-derived-text.md`
- K6 — הקצה השני: סוד שדולף **ללקוח** ב-response; כאן הדליפה פנימית
- `docs/source-projects/codebot-patterns.md` Pattern 5
