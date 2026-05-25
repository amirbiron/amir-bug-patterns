# sdk-error-completeness

זהה קריאות SDK חיצוני שבהן exception handler צר מדי, מסדר שגוי subclass-מול-superclass, או נכשל לתפוס נכון cancellation של task async.

## דווח כשמתקיים אחד מהבאים

1. **Base צר ב-`except`.** קריאת SDK עטופה ב-`try/except SpecificError` כאשר `SpecificError` הוא subclass של ה-base class המתועד של ה-SDK (`anthropic.APIError`, `googleapiclient.errors.HttpError`, `stripe.error.StripeError`, `requests.HTTPError`). טיפוסי exception לא קשורים של ה-SDK עוברים בלי טיפול.

2. **סדר subclass שגוי.** `except APIError` ממוקם לפני `except RateLimitError` (כש-`RateLimitError` הוא subclass) — branch של ה-subclass לעולם לא רץ.

3. **בדיקת תוצאה של `asyncio.gather(return_exceptions=True)` משתמשת ב-`isinstance(r, Exception)`.** מאז Python 3.8, `asyncio.CancelledError` יורש מ-`BaseException`, לא `Exception` → tasks מבוטלים נספרים בטעות כהצלחה. השתמש ב-`isinstance(r, BaseException)`.

4. **אתחול SDK בזמן startup ב-module / import scope בלי try/except.** `webpush.set_vapid_details(...)`, `stripe.api_key = ...`, אתחול OAuth client. מפתחות פגומים → exception לא נתפס → השרת קורס ב-boot. עטוף, ולידציה, הורד את הפיצ'ר.

5. **`isinstance(r, Exception)` מול `r is True`** על אובייקטי תוצאה של SDK. ערכי החזרה של SDK עשויים להיות אובייקטים בלי `__bool__` מוגדר; השוואת identity עם `True` לעולם לא מתאימה.

## False positives

- `except` צר ל-propagation מכוון (למשל זריקה מחדש של `AppException` ש-FastAPI מטפל בה גלובלית).
- תפיסת `Exception` ב-scripts CLI שבהם כל כשל צריך להדפיס + לצאת.
- טסטים עם mocks שתמיד מצליחים.

## חומרה

MEDIUM — קריסות בפרודקשן ב-init, מספור שגוי שקט על תוצאות batch async, סופות retry כשטיפוסי שגיאה צפויים לא מזוהים.
