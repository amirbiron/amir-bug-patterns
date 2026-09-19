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

10. **קריאה שנראית כמו אימות אינה בהכרח שולחת בקשה.** יש SDKs ומתודות שמתועדים כמחזירים אובייקט עצל — למשל `Github.get_user()`, שמחזיר `AuthenticatedUser` עם `completed=False`, וה-`GET /user` יוצא רק בגישה לשדה. אישורים פסולים "מתחברים" בהצלחה וה-`except` לא רץ. העדף קריאה שמאלצת את הבקשה (ב-PyGithub: `get_user(lazy=False)` — שים לב לכיוון, היעדר הדגל הוא המצב העצל). אם נוגעים בשדה במקום זאת — בשורה משלה עם הערה, ולוודא שהשדה לא נגזר ממה שכבר בזיכרון. אמת בספירת בקשות, לא לפי שם המתודה.

11. **`except` סביב חתימה שלא נבדקה.** אם הפרמטר אינו קיים ב-API, פייתון נכשל בקשירת הארגומנטים לפני שגוף המתודה רץ: נכנסים ל-`try` ומתים בשורה הראשונה שבו, ה-`except` הוא המסלול היחיד שמסתיים אי פעם, וההודעה שלו מתארת את ההפך ממה שקורה ("falling back without execution stats" בזמן שהמנוע מריץ דווקא את המצב הכבד). לפתוח את החתימה בקוד הספרייה של **הגרסה המותקנת** לפני שכותבים את הטיפול, ולהריץ פעם אחת עם `raise` במקום ה-`except` כדי לראות אם מגיעים לשם בכלל. ו"תיקון" סינטקטי לקריאה שנכשלת (מ-positional ל-keyword) הוא טלאי על API שאולי לא קיים.

12. **לקוח עם אישורים שפגים צריך מסלול ריענון — ושני כשלים שונים.** ‏**401 עירום אינו "הטוקן פג"** — לפי RFC 6750 הוא מסמן היעדר אישורים, והראיה לתפוגה היא `WWW-Authenticate: Bearer error="invalid_token"` (או חוזה מתועד של הספק). ‏`403` עם `insufficient_scope` הוא חוסר הרשאה וריענון לא יעזור שם. כשיש ראיה: לרענן ולנסות פעם אחת, ורק אם הפעולה idempotent או ידוע שלא בוצעה. ‏`invalid_grant` **משרת הטוקנים**, על בקשת הריענון עצמה, אומר "ה-grant בטל": ניסיון חוזר עם אותו grant יחזיר את אותה תשובה לנצח — להתנתק מפורשות ולדרוש התחברות מחדש. שירות שנבנה פעם אחת ומחזיק טוקן בלי כלום מזה מת אחרי `401` אחד, עד התחברות ידנית.

13. **אובייקטים של SDK נבדקים ב-`is None`, לא באמת בוליאנית.** pymongo זורק `NotImplementedError` בכוונה על `if collection:` — כדי למנוע את הבלבול בין "קיים" ל"לא ריק". הצורה המפורשת נכונה תמיד; הבוליאנית נכונה רק כשה-SDK הסכים לה.

ראה `BY-STACK/external-sdk.md`.
