# דפוסי Webhooks (להעתקה ל-CLAUDE.md)

1. **Reserve לפני fill.** INSERT ל-DB מקומי עם UNIQUE constraint או idempotency key לפני כל קריאה חיצונית בלתי הפיכה (Gmail draft, SMS, payment). כפילות מזוהה בהתנגשות על ה-idempotency key עצמו — ב-Postgres `INSERT ... ON CONFLICT (key) DO NOTHING RETURNING id`, ובמסד אחר הפעולה האטומית המקבילה של insert-if-absent — ושורה ריקה היא duplicate: החזר 200. לא כל `IntegrityError` הוא כפילות — FK, ‏CHECK ו-NOT NULL הם כשל, ו-200 עליהם מאשר webhook שנזרק. לעולם אל תעשה `commit()` של הרזרבציה אחרי `await client.X()`. ה-fill: אחרי הקריאה — לעדכן את השורה השמורה (מזהה חיצוני, `status='created'`); בכשל — `status='failed'` ו-raise, לא להשאיר `reserved`.

2. **CAS על cursors משותפים.** כששני webhooks יכולים לקרוא את אותו `sync_token` / `history_id` / cursor, הקדם אותו דרך `UPDATE ... WHERE id=:id AND token=:expected RETURNING ...`. הסתעפות `IS NULL` לערכים nullable. ה-CAS רץ לפני החלת ה-deltas ובאותה טרנזקציה; `rowcount == 0` — webhook אחר הקדים: לא מחילים את ה-deltas שחושבו מהסמן הישן, אלא קוראים מחדש את הסמן השמור ומסנכרנים ממנו שוב (מספר ניסיונות מוגבל) — ה-deltas שלו עשויים לכסות פחות משלנו, וויתור משאיר שינויים שלא הוחלו.

3. **התמד ב-cursor בכל קריאה, גם ריקה.** אם הספק מחזיר `changes=[]` עם `next_sync_token`, כתוב את ה-token. אחרת לולאה אינסופית.

4. **אימות signature לפני כל processing.** השתמש ב-verifier של הספק (`stripe.Webhook.construct_event`, Meta HMAC-SHA256, GitHub `X-Hub-Signature-256`). השווה עם `hmac.compare_digest`, לעולם לא `==`. קרא bytes גולמיים, לא טקסט שעבר encoding מחדש. האימות חל גם על משלוח חוזר מהספק. replay פנימי של אירוע שכבר אומת ונשמר עובר דרך הרשאה משלו ולא דרך החתימה המקורית — ב-Stripe היא נדחית אחרי 300 שניות (`tolerance` של `construct_event`).

5. **trusted proxy להחלטות מבוססות-IP.** הגדר `ProxyHeadersMiddleware` / `app.set('trust proxy', N)` עם רשימת proxies מפורשת, או hop count רק כשכל בקשה עוברת בדיוק אותו מספר proxies מהימנים (K2). ואז קרא `request.client.host` (ב-Express — `req.ip`). לעולם אל תקרא `X-Forwarded-For` ישירות.

6. **רכוש slot של rate-limit אחרי בדיקת תקפות עבודה.** spam / not-business לא צריכים לצרוך slots שמורים לעבודה אמיתית.

7. **אין נתיב fallback "דלג על verification" בכשל storage.** אם Redis SET / DB INSERT של OTP נכשל, אל תשלח את ה-SMS. fail closed.

8. **race של beat scheduler + `.delay()`:** atomic `UPDATE ... WHERE status='pending' RETURNING id`, בדוק rowcount לפני שליחה.

ראה `BY-STACK/webhooks.md` ו-`CRITICAL-PATTERNS.md` K2 / K9 בריפו amir-bug-patterns.
