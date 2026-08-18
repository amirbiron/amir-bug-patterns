# דפוסים קריטיים (להעתקה ל-CLAUDE.md — security/privacy/data-loss, חל תמיד)

1. **OAuth password takeover.** endpoints של "set password" / "register" / "link account" שמקבלים email חייבים לדחות את הבקשה אם חשבון קיים דרך OAuth, אלא אם מאומת כאותו משתמש או הוכח דרך קישור one-time מאומת שנשלח ל-email.

2. **XFF spoofing ב-rate limiter.** לעולם אל תקרא `X-Forwarded-For` ישירות להחלטות security. הגדר middleware של trusted-proxy (`ProxyHeadersMiddleware`, `app.set('trust proxy', N)`) — ואז קרא `request.client.host`.

3. **Auto-admin לפי email לא מאומת.** הענקת תפקיד admin / staff / owner קורית רק אחרי email verification, או דרך קישור invite + token מ-admin קיים. לעולם אל תסמוך על `request.body.email == OWNER_EMAIL`.

4. **XSS via innerHTML.** ברירת מחדל ל-`textContent` / טקסט ב-JSX. `innerHTML` / `dangerouslySetInnerHTML` / `v-html` עם ערכים ממקור חיצוני דורש `DOMPurify` (או שווה ערך) באותה שורה של ההשמה. "Admin only" אינה הגנה.

5. **פאנל admin חשוף לרשת.** שרת שנקשר ל-`0.0.0.0` דורש middleware של אימות *לפני* שכל route רץ, או firewall. אחרת קשור `127.0.0.1`.

6. **Secret ב-response.** Serialization של משתמש עובר דרך DTO / response model מפורש. שמות שדות אסורים בכל מקום ב-response של API: `password`, `passwordHash`, `salt`, `refresh_token`, `access_token`, `api_key`, `secret`. הודעות exception בגבולות API לא יכולות לכלול IDs פנימיים / סיבות heuristic.

7. **PII בלוגים.** אסור ב-`logger.*` וב-`HTTPException.detail`: `email`, `phone`, `from_email`, `to_email`, שמות, body של הודעות, tokens, API keys. החלף ב-domain של email בלבד, hash, או user_id משלך. הודעת שגיאה מתורגמת גנרית לפרטים שמופיעים למשתמש.

8. **LIKE wildcard injection.** prefix של משתמש ב-`LIKE` חייב לברוח מ-`_` ו-`%`, או להשתמש ב-`.startswith(value, autoescape=True)`, או `=` מדויק.

9. **שליחת credential לפני storage.** התמד ב-OTP / token / link (Redis SET / DB INSERT) *לפני* השליחה. אם ההתמדה נכשלת, אל תשלח. אין נתיב fallback "דלג על verification" בכשל storage — fail closed.

10. **500 ≠ "invalid credentials".** טיפול בשגיאת login מסתעף: 401/403 → "Invalid credentials"; 5xx → "Service unavailable, try again"; 429 → "Too many attempts". לעולם אל תאחד 5xx ל-auth error.

11. **כשל בערך החזרה ≠ חריגה.** לפני עטיפת קריאה ב-try/except — בדוק את מסלול הכשל של הפונקציה: זורקת, או מחזירה `None`/`False`/`0`? אם לפי החוזה שלה falsy מסמן כשל — חובה `if not result:` לפני כל דיווח הצלחה (`0` שמשמעו "אין מה למחוק" אינו כשל). אסור `saved = True` קבוע אחרי קריאה, ואסור ✅ למשתמש בלי תנאי על הערך. בפונקציה חדשה: ערוץ כשל אחד (עדיף זריקה), מתועד ב-docstring.

12. **שאילתה רב-דיירית בלי tenant scope.** SELECT/UPDATE/DELETE בטבלה עם `tenant_id` — predicate על ה-tenant המאומת, כולל get-by-id, exports, aggregations. INSERT/UPSERT — ה-tenant נגזר מה-context המאומת, לא מערך של הלקוח; conflict key כולל tenant. Context של tenant: fail-closed — בלי default; נתיב בלי context זורק. מפתחות cache/session כוללים tenant. בדיקת בידוד (שני tenants סינתטיים, מסד בדיקה בלבד) היא חובה. חריגים מוצהרים: טבלאות גלובליות באמת ונתיבי admin מבוקרים.

ראה `CRITICAL-PATTERNS.md` להגיון מלא וכללי זיהוי.
