# sdk-error-completeness

זהה קריאות SDK חיצוני שבהן exception handler צר מדי, מסדר שגוי subclass-מול-superclass, או נכשל לתפוס נכון cancellation של task async.

## דווח כשמתקיים אחד מהבאים

1. **Base צר ב-`except`.** קריאת SDK עטופה ב-`try/except SpecificError` כאשר `SpecificError` הוא subclass של ה-base class המתועד של ה-SDK (`anthropic.APIError`, `googleapiclient.errors.HttpError`, `stripe.error.StripeError`, `requests.HTTPError`). טיפוסי exception לא קשורים של ה-SDK עוברים בלי טיפול.

2. **סדר subclass שגוי.** `except APIError` ממוקם לפני `except RateLimitError` (כש-`RateLimitError` הוא subclass) — branch של ה-subclass לעולם לא רץ.

3. **בדיקת תוצאה של `asyncio.gather(return_exceptions=True)` משתמשת ב-`isinstance(r, Exception)`.** מאז Python 3.8, `asyncio.CancelledError` יורש מ-`BaseException`, לא `Exception` → tasks מבוטלים נספרים בטעות כהצלחה. השתמש ב-`isinstance(r, BaseException)`.

4. **אתחול SDK בזמן startup ב-module / import scope בלי try/except.** `webpush.set_vapid_details(...)`, `stripe.api_key = ...`, אתחול OAuth client. מפתחות פגומים → exception לא נתפס → השרת קורס ב-boot. עטוף, ולידציה, הורד את הפיצ'ר.

5. **`isinstance(r, Exception)` מול `r is True`** על אובייקטי תוצאה של SDK. ערכי החזרה של SDK עשויים להיות אובייקטים בלי `__bool__` מוגדר; השוואת identity עם `True` לעולם לא מתאימה.

6. **Provider parameter deprecation בלי adaptive seam.** ספק חיצוני (OpenAI gpt-5.x, Gemini) דוחה פרמטרים ישנים (`max_tokens` → `max_completion_tokens`; `temperature` שנעלם ואז חזר). ה-SDK client חייב **allowlist מפורש של params פר-מודל** ו-strip של params שנדחים, עם fail-loud על unknown model. אל תשתמש ב-adaptive layer שקט שמסיר params בלי דיווח — זה מדביר לך תיקון בסבב הבא (P18, P205). דגל דיף שמוסיף try/except סביב cal SDK "כדי לתפוס `unsupported_parameter`" — זה patch, לא fix. גם: `thinkingBudget` של Gemini דלוק כברירת מחדל ואוכל את `maxOutputTokens` על קריאות קצרות → response ריק שמזוהה כ-"corrupt". דרוש דגלי-config של הספק מתועדים בקוד ולא בדוקומנטציה בלבד.

## False positives

- `except` צר ל-propagation מכוון (למשל זריקה מחדש של `AppException` ש-FastAPI מטפל בה גלובלית).
- תפיסת `Exception` ב-scripts CLI שבהם כל כשל צריך להדפיס + לצאת.
- טסטים עם mocks שתמיד מצליחים.

## חומרה

MEDIUM — קריסות בפרודקשן ב-init, מספור שגוי שקט על תוצאות batch async, סופות retry כשטיפוסי שגיאה צפויים לא מזוהים.
