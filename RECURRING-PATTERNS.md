# דפוסים חוזרים (RECURRING)

דפוסים שהופיעו ב**שני מסמכי מקור מתוך שלושה** — סיגנל חזק, אבל בסיס הראיות צר יותר מ-CORE. החל אם הפרויקט שלך תואם ל-stack. כל ערך מציין את הפרויקטים הספציפיים, כדי שתוכל לשפוט אם הדפוס סביר להיות רלוונטי.

> **הערה על PII leakage:** הוא מסווג כ-RECURRING לפי תדירות (EmailFlow + 8-Projects), אבל החומרה מקדמת אותו ל-`CRITICAL-PATTERNS.md` K7. הכלל המלא חי שם; ראה גם הסעיף בסוף לקרוס-רפרנס.

---

## R1. lifecycle של AsyncSession ב-SQLAlchemy

**תדירות:** 2/3 מקורות (EmailFlow + 8-Projects/Shipment-bot)
**חומרה:** MEDIUM — קריסות `MissingGreenlet`, שחיתות נתונים שקטה

### איך זה נראה
SQLAlchemy async (`AsyncSession`, `async_sessionmaker`) יש לו כללי lifecycle שתופסים מפתחים לא מוכנים:
- attributes של אובייקט ORM שניגשים אליהם *אחרי* `await session.rollback()` זורקים `MissingGreenlet`.
- `AsyncSession` אחד שמשותף בין tasks concurrent דרך `asyncio.gather` → race / שחיתות (sessions לא בטוחים ל-thread או ל-task).
- אחרי `await session.commit()` בלולאה, גישה מחדש לאותה שורת ORM מחזירה attributes ישנים (commit מרענן רק את ה-PK; דורש `await session.refresh(row)` מפורש).
- `joinedload` + `with_for_update` אינם תואמים (SQLAlchemy זורק).
- `Engine` singleton שמקושר ל-event loop אחד נכשל ב-Celery task השני (שמקבל loop חדש).

### דוגמאות אמיתיות
- **EmailFlow (`0fdd247`):** `MissingGreenlet` בגישה ל-attribute של ORM אחרי rollback.
- **EmailFlow (`018b166`):** `asyncio.gather` משתף session בין tasks → שחיתות.
- **EmailFlow (`0e6dc85`):** embedding job ניגש ל-attributes ישנים אחרי commit בתוך לולאה.
- **Shipment-bot (`85d7a8e`):** לולאה על `expiring` deliveries אחרי `db.commit()` — `MissingGreenlet`.
- **Shipment-bot (`0f30963`):** Celery singleton engine קשור ל-event loop ישן → task שני תמיד נכשל.
- **Shipment-bot (`4352bac`):** `joinedload` + `with_for_update` זרק.

### כלל לזיהוי
1. לעולם אל תעביר את אותו `AsyncSession` ל-tasks concurrent מרובים דרך `asyncio.gather` / `asyncio.create_task` — כל task פותח את שלו עם `async with sessionmaker() as session:`.
2. אחרי `await session.rollback()` (מפורש או מ-exception): אל תיגש ל-attributes של ORM. חלץ `.id` / primitives **לפני** rollback, או `session.expunge(obj)` כדי לנתק.
3. אחרי `await session.commit()` בתוך לולאה, קרא ל-`await session.refresh(row)` לפני גישה מחדש ל-attributes.
4. `joinedload` עם locking → השתמש ב-`contains_eager` במקום.
5. Celery tasks: צור engine חדש בתוך ה-task (או השתמש ב-connection pool שמתחדש ל-loop הנוכחי).

### False positives
- SQLAlchemy סינכרוני (`sessionmaker` רגיל) — כללים שונים לחלוטין.
- session ב-FastAPI scope של dependency per-request — בטוח כל עוד אין `gather`.

### מצב מומלץ
**strict** לקוד שעושה `await session.commit()` בתוך לולאה או משתמש ב-`asyncio.gather`.

### ראה גם
- `BY-STACK/async-orm.md` — כיסוי מלא עם קוד

---

## R2. דפדוף בלי tiebreaker משני

**תדירות:** 2/3 מקורות (EmailFlow + 8-Projects/Shipment-bot)
**חומרה:** MEDIUM — דפדוף מדלג/מכפיל שורות, ranking לא דטרמיניסטי

### איך זה נראה
`ORDER BY ts.desc()` (או `score.desc()`) ואחריו `LIMIT` / `OFFSET` או cursor pagination. שורות עם אותו ערך ראשי מקבלות סדר לא מוגדר ב-Postgres → בין דפים, ה-ties מתערבבים מחדש → שורה יכולה להופיע פעמיים או להידלג.

### דוגמאות אמיתיות
- **EmailFlow (`d84daca`):** `Lead.order_by(updated_at.desc())` בלבד → leads עם אותו timestamp קיבלו סדר אקראי → דפדוף בלולאה.
- **EmailFlow (`3987818`):** CAS query דרש tuple `(timestamp, created_at)` כדי להתאים ל-selector.
- **EmailFlow (`a0c4603`):** Drafter ranking בלי tiebreaker משני → ranking לא דטרמיניסטי.
- **Shipment-bot (`c0c1b74`):** Audit log מדפדף לפי timestamp בלבד → שורות התערבבו בין דפים.

### כלל לזיהוי
כל `order_by(...)` / raw `ORDER BY` שאחריו `LIMIT` / `OFFSET` / cursor pagination חייב לכלול **לפחות שתי expressions**:
1. השדה הסמנטי (`created_at.desc()`, `score.desc()`).
2. המפתח הראשי כ-tiebreaker (`Model.id.desc()` או `.asc()`).

ל-CAS עם סמנטיקה של "latest", ה-tiebreaker חייב להתאים בין ה-selector ל-verifier.

### False positives
- Queries בלי `LIMIT` — סדר פחות קריטי.
- אגרגציות (`GROUP BY` + `SUM`).
- queries של שורה יחידה (`.first()`, `.scalar_one_or_none()`) על עמודה ייחודית.

### מצב מומלץ
**warning** (strict מוסיף `.id` לכל query, כולל אגרגציות, ומייצר רעש).

### ראה גם
- `BY-STACK/postgres.md`
- `bugbot-rules/pagination-tiebreaker.md`

---

## R3. quirks של Browser API / DOM

**תדירות:** 2/3 מקורות (Noa + 8-Projects)
**חומרה:** MEDIUM — UX שבור, מדי פעם אובדן נתונים

### איך זה נראה
ל-APIs של הדפדפן יש סמנטיקה לא מובנת מאליה שתופסת מפתחים שקוראים אותן כאילו היו APIs של Node:
- `window.open("mailto:...")` מחזיר `null` ב-Chrome (handoff של protocol מערכת, **לא** popup blocker). קוד שמפרש `null` כ-"חסום" מבטל את הפעולה הלגיטימית.
- `navigator.clipboard.writeText(...)` דורש HTTPS; זורק על HTTP. בלי try/catch → שגיאת console + כשל UX שקט.
- Tooltip / dropdown נסגר מיד על click כי ה-click מבעבע ל-parent שמחליף state.
- CSS reset גלובלי (`* { margin: 0; padding: 0 }`) יש לו specificity גבוה יותר ממחלקות utility של Tailwind כמו `space-y-6`.
- דליפת `URL.createObjectURL` — blob URL לעולם לא משוחרר, מצטבר לכל render.
- `setTimeout(fn, delay)` עם `delay = NaN` — שגיאת React / delay אינסופי.

### דוגמאות אמיתיות
- **Noa (`f635304`):** `window.open("mailto:...")` החזיר `null` ב-Chrome; popup-blocker guard ביטל flow של `mark_sent`.
- **Noa (`f4769bf`):** כפתור `BOOKED` הוצג אחרי `slot_start + 30min` במקום `slot_end` — שובר מפגשים קצרים.
- **Markdown-Academy (`b97d3f5`):** כפתור Copy קרא ל-`navigator.clipboard.writeText` בלי try/catch; נשבר ב-HTTP.
- **Markdown-Academy (`315154e`):** Tooltip נסגר על click כי parent תפס propagation; נדרש `stopPropagation()`.
- **Web (`c586691`):** CSS reset גלובלי `* { margin: 0; padding: 0 }` דרס utilities של Tailwind.
- **Web (`f5cbaf9`):** Blob URL של תמונת profile לא משוחרר על unmount.

### כלל לזיהוי
1. `window.open(url, ...)` ואחריו `if (!win)` שמבטל flow → דווח אם `url` מתחיל ב-`mailto:`, `tel:`, `sms:`, `file:`. ל-protocols מערכת, השתמש ב-`<a>` עם `.click()`.
2. `navigator.clipboard.*` בלי try/catch → דווח.
3. `URL.createObjectURL` בלי `URL.revokeObjectURL` מתאים ב-cleanup של `useEffect` / `componentWillUnmount` / `addEventListener('unload', ...)`.
4. `setTimeout(fn, delay)` / `setInterval(fn, delay)` / `new Date(value)` בלי הגנת `isFinite(delay)` ל-delay/value ממקור חיצוני.
5. `* { margin: 0; padding: 0 }` גלובלי בפרויקט שמשתמש ב-framework utility CSS (Tailwind, UnoCSS) → דווח.

### מצב מומלץ
**warning** — רוב הבאגים הם UX, לא אובדן נתונים.

### ראה גם
- `BY-STACK/browser-handoff.md`
- `bugbot-rules/window-open-protocol-handoff.md`

---

## R4. שלמות exception של External SDK

**תדירות:** 2/3 מקורות (Noa + 8-Projects)
**חומרה:** MEDIUM — בליעה שקטה / קריסת startup

### איך זה נראה
SDKs זורקים היררכיות exception רחבות, ו-subclasses של `BaseException` (`asyncio.CancelledError`) לא יושבים תחת `Exception`. הקוד תופס base צר מדי, נותן ל-subclasses לפרוץ, או בולע הכל דרך `Exception` ומונה לא נכון.

### דוגמאות אמיתיות
- **Noa (`c128115`):** `_complete` תפס `RateLimitError` + `_RETRYABLE`; subtypes אחרים של `anthropic.APIError` (`NotFound`, `BadRequest`, `Auth`) עברו בלי טיפול.
- **Noa (`95dcce6`):** Fallback תפס `RateLimitError` כ-`AIError` גנרי → ה-caller לא סימן `pending_classification`.
- **Noa (`95b82e5`):** OAuth scope drift טופל כקטלני; נדרש `OAUTHLIB_RELAX_TOKEN_SCOPE=1`.
- **Shipment-bot (`e0f4d59`):** `isinstance(r, Exception)` לא תפס `CancelledError` (subclass של `BaseException`) → tasks מבוטלים נספרו כהצלחה.
- **routine (`2571c91` / `e5c26ad`):** מפתחות VAPID פגומים → exception לא נתפס ב-`setVapidDetails` → השרת קרס בעלייה.

### כלל לזיהוי
1. לכל קריאת SDK חיצוני, ה-`except` צריך לתפוס את ה-base class המתועד של ה-SDK (`anthropic.APIError`, `googleapiclient.errors.HttpError`, `stripe.error.StripeError`).
2. סדר את בלוקי ה-`except` subclass-לפני-superclass (`RateLimitError` לפני `APIError`).
3. לתוצאות של collection של tasks async (`asyncio.gather(return_exceptions=True)`): בדוק `isinstance(r, BaseException)`, לא `Exception` (CancelledError אינו Exception ב-3.8+).
4. אתחול SDK בזמן startup (VAPID keys, OAuth client, Stripe key) חייב להיות עטוף ב-try/except + ולידציית פורמט; כשלים מורידים את הפיצ'ר הרלוונטי, לא קורסים את כל השרת.
5. תעד וכבד env flags של SDK (`OAUTHLIB_RELAX_TOKEN_SCOPE`, `STRIPE_API_VERSION`, וכו').

### מצב מומלץ
**strict** בכל גבולות ה-SDK.

### ראה גם
- `BY-STACK/external-sdk.md`
- `bugbot-rules/sdk-error-completeness.md`

---

## R5. שגיאות scope של filter

**תדירות:** 2/3 מקורות (Noa + 8-Projects/Facebook-Leads-New)
**חומרה:** MEDIUM — UI ריק / cron בלולאה אינסופית / משתמש חסום שעדיין מקבל leads

### איך זה נראה
filter (DB `WHERE`, regex, JS `.filter()`) או צר מדי (מוציא מקרים לגיטימיים) או מופעל בסדר שגוי (filters מאוחרים דורסים מוקדמים).

### דוגמאות אמיתיות
- **Noa (`f635304`):** רשימה ידנית סוננה ל-WhatsApp בלבד; lead שמעדיף email ראה רשימה ריקה.
- **Noa (`d526948`):** סינון `channel + audience` ביחד חסם templates תקפים.
- **Noa (`95dcce6`):** Domain blacklist עם exact-match פספס subdomains (`mail.mailchimp.com`).
- **Noa (`c608a85`):** סינון retry של cron על `lead_id IS NULL` תפס שורות spam/not_business שלעולם לא יקבלו lead_id → לולאה אינסופית.
- **Noa (`2b978aa`):** סינון cron `count < MAX` הוציא שורות תקועות ב-`count==MAX` → תקועות pending לנצח.
- **Facebook-Leads-New (`24ad356`):** סינון blocked-publisher רץ *אחרי* בדיקת `force_send` → blocked publisher עם מילת מפתח `force_send` עדיין שלח leads.

### כלל לזיהוי
לכל filter (`WHERE`, regex, `.filter()`):
1. **שלמות:** האם הוא מכסה את כל ה-input variants הצפויים? (סינון channel שמפספס lead שמעדיף email; regex על email שמפספס RFC 2822 display name; domain blacklist עם exact match במקום `endswith` ל-subdomains).
2. **States סופיים ל-cron:** כלול עמודות "done" מפורשות (`processing_status`, `archived_at`), לא heuristics של "IS NULL" שתופסות states סופיים שלעולם לא יתמלאו.
3. **סדר filter:** filters של security / block / deny רצים *קודם*, לפני כל override "force send / always include".

### מצב מומלץ
**strict** ל-filters של cron שמגדירים reprocessing של שורות.
**warning** ל-filters של UI (false positives שכיחים — לפעמים צמצום scope הוא הפיצ'ר).

### ראה גם
- `BY-STACK/cron-jobs.md` — דפוס terminal-state
- `bugbot-rules/filter-too-narrow.md`

---

## ראה גם (cross-tier)

- **K7 / PII בלוגים** — לפי תדירות זה RECURRING (EmailFlow P5 + 8-Projects C6/C24/C57), אבל לפי חומרה CRITICAL. הכלל המלא ב-`CRITICAL-PATTERNS.md`.
