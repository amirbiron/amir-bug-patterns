# rate-limit-xff-spoofing

**CRITICAL — עקיפת בקרת אבטחה**

זהה rate-limiter, abuse-detection, או כל החלטת security שקוראת `X-Forwarded-For` (או `X-Real-IP`, `Forwarded`) ישירות בלי לוודא שה-peer המיידי הוא proxy אמין.

## דווח כשמתקיימים כל הבאים

1. הקוד קורא אחד מ:
   - `request.headers["x-forwarded-for"]` / `req.headers["x-forwarded-for"]`
   - `request.headers["x-real-ip"]`
   - `request.headers["forwarded"]`
   - ניתוח ידני של `X-Forwarded-For` שלוקח את הסגמנט השמאלי / ימני ביותר
2. הערך משמש ל:
   - מפתח של rate-limit
   - חיפוש ברשימת abuse / block
   - logs של audit / fraud-detection
   - אימות / allowlisting מבוסס-IP
3. ה-framework / app *אינו* מוגדר עם רשימת trusted-proxy מפורשת:
   - FastAPI / Starlette: אין `ProxyHeadersMiddleware(app, trusted_hosts="...")` מוגדר עם ערכים ספציפיים.
   - Express: אין `app.set('trust proxy', <specific value>)`.
   - Flask: אין `ProxyFix(app, x_for=N)` עם hop count ספציפי.

## תיקון

הגדר middleware קודם, ואז קרא `request.client.host` / `req.ip` (שה-middleware תיקן ל-IP האמיתי של הלקוח).

אם אין proxy מקדים לשירות, *אל* תקרא את ה-header בכלל — השתמש ב-`request.client.host` ישירות.

## False positives

- routes פנימיים בלבד מאחורי VPN מאומת שבהם IP לא מגביל כלום.
- שימוש לוגינג / debug בלבד (עדיין דווח לסקירה — אלה לרוב מחליקים להחלטות security מאוחר יותר).

## חומרה

CRITICAL — עוקף את כל ה-rate limiter; תוקף מזייף את ה-header לכל בקשה ונתקל בלי limit.
