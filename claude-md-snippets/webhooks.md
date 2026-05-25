# דפוסי Webhooks (להעתקה ל-CLAUDE.md)

1. **Reserve לפני fill.** INSERT ל-DB מקומי עם UNIQUE constraint או idempotency key לפני כל קריאה חיצונית בלתי הפיכה (Gmail draft, SMS, payment). על `IntegrityError`, החזר 200 (duplicate, ignore). לעולם אל תעשה `commit()` אחרי `await client.X()`.

2. **CAS על cursors משותפים.** כששני webhooks יכולים לקרוא את אותו `sync_token` / `history_id` / cursor, הקדם אותו דרך `UPDATE ... WHERE id=:id AND token=:expected RETURNING ...`. הסתעפות `IS NULL` לערכים nullable.

3. **התמד ב-cursor בכל קריאה, גם ריקה.** אם הספק מחזיר `changes=[]` עם `next_sync_token`, כתוב את ה-token. אחרת לולאה אינסופית.

4. **אימות signature לפני כל processing.** השתמש ב-verifier של הספק (`stripe.Webhook.construct_event`, Meta HMAC-SHA256, GitHub `X-Hub-Signature-256`). השווה עם `hmac.compare_digest`, לעולם לא `==`. קרא bytes גולמיים, לא טקסט שעבר encoding מחדש.

5. **trusted proxy להחלטות מבוססות-IP.** הגדר `ProxyHeadersMiddleware` / `app.set('trust proxy', N)` עם hop count מפורש. ואז קרא `request.client.host`. לעולם אל תקרא `X-Forwarded-For` ישירות.

6. **רכוש slot של rate-limit אחרי בדיקת תקפות עבודה.** spam / not-business לא צריכים לצרוך slots שמורים לעבודה אמיתית.

7. **אין נתיב fallback "דלג על verification" בכשל storage.** אם Redis SET / DB INSERT של OTP נכשל, אל תשלח את ה-SMS. fail closed.

8. **race של beat scheduler + `.delay()`:** atomic `UPDATE ... WHERE status='pending' RETURNING id`, בדוק rowcount לפני שליחה.

ראה `BY-STACK/webhooks.md` ו-`CRITICAL-PATTERNS.md` K2 / K9.
