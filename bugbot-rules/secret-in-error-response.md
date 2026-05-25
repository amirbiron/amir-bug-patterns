# secret-in-error-response

**CRITICAL — חשיפת חומר סודי / IDs פנימיים**

זהה responses של API או bodies של exception שמדלפים credentials, password hashes, UUIDs פנימיים של actors אחרים, או הודעות framework / debug.

## דווח כשמתקיים אחד מהבאים

1. אובייקט ORM דמוי-משתמש או דמוי-actor מוחזר ללקוח *בלי* לעבור דרך DTO / Pydantic response model מפורש שמפרט שדות מותרים. ORM-row-to-JSON אסור בגבולות API.

2. שמות שדות אסורים בכל מקום ב-body של תגובת HTTP:
   - `password`, `passwordHash`, `password_hash`, `salt`
   - `refresh_token`, `access_token`, `api_key`, `secret`, `private_key`
   - JWT bearer tokens בשדות תגובה שאינם cookie
   - שדות תפעוליים פנימיים בלבד (`internal_status`, `decision_factors`, `model_version`)

3. מחלקת exception מותאמת כוללת מזהים פנימיים ב-`message` / `to_dict()` / serialization שלה, ואז נזרקת בגבול API. דוגמה:
   ```python
   class InsufficientCreditError(AppException):
     def __init__(self, courier_id):
       super().__init__(f"Insufficient credit for courier {courier_id}")  # ❌ דולף courier_id ללקוח
   ```
   תיקון: הפרד `public_message` (בטוח) מ-`detail` (server-only).

4. `raise X` נזרק מחדש בלי המרה ל-error response בטוח; handler ברירת מחדל של FastAPI / Express פולט `{"detail": "<exception repr>"}`.

## False positives

- Tokens ב-headers של `Set-Cookie` (תוכננו ל-transit סודי, לא ב-body).
- endpoints של שירותים פנימיים בלבד מאחורי authn לצוות בלבד — עדיין מסוכן אם נחשף, אבל חומרה נמוכה יותר.
- טסטים / mocks.

## חומרה

CRITICAL — חשיפת חומר סודי ישיר או סיוע לסיור של תוקף.
