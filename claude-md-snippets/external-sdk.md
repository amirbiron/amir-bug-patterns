# דפוסי External SDK (להעתקה ל-CLAUDE.md)

1. **תפוס את ה-base class של ה-SDK, עדן בפנים.** `except anthropic.APIError` (לא רק `RateLimitError`); בלוקי `except` של subclasses מסודרים subclass-לפני-superclass.

2. **בדיקות תוצאה של `asyncio.gather(return_exceptions=True)` משתמשות ב-`isinstance(r, BaseException)`**, לא `Exception` (CancelledError הוא BaseException, לא Exception מאז Python 3.8).

3. **אתחול SDK בזמן startup עטוף ב-try/except + ולידציית פורמט.** מפתחות VAPID פגומים / חסר prefix של `mailto:` / OAuth secret פגום חייבים להוריד את הפיצ'ר, לא לקרוס את ה-boot.

4. **isinstance guards על כל תגובה חיצונית.** לפני `.get()`, `.append()`, `.strip()`, iteration על נתונים מ-`response.json()` / body של webhook / output של AI: `isinstance(obj, dict/list/str)`. מספרים: `isfinite()` + טווח.

5. **regex על JSON של AI/SDK:** raw strings (`r"..."`), word boundaries (`\b`). עדיף `json.JSONDecoder().raw_decode(s[s.find("{"):])` על `\{.*\}` חמדן (נשבר על prose).

6. **enums של Pydantic ממקורות חיצוניים:** השתמש ב-`str | None` עם ולידציה idempotent, לא `StrEnum` strict — דחייה strict זורקת את כל ה-payload (כולל שדות אחים תקפים).

7. **env flags של SDK:** תעד וכבד (למשל `OAUTHLIB_RELAX_TOKEN_SCOPE=1` לסטיית scope של Google, `STRIPE_API_VERSION` ל-pin).

8. **Walrus + truthy על env vars:** `if override := os.environ.get("X"):` מתייחס ל-`""` כ-falsy. השתמש ב-`if override is not None:` ו-`.strip()`.

9. **ממש `__bool__` על אובייקטי תוצאה** (או בדוק `isinstance(r, SendResult) and r.ok` — לעולם לא `r is True`).

ראה `BY-STACK/external-sdk.md`.
