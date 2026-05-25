# network-exposed-without-auth

**CRITICAL — RCE / השתלטות admin**

זהה שרתי HTTP שנקשרים ל-all-interfaces (`0.0.0.0`, `::`) בלי middleware של אימות שדוחה בקשות לא מאומתות לפני שכל route רץ.

## דווח כשמתקיימים כל הבאים

1. עליית השרת נקשרת לאחד מ:
   - `0.0.0.0`
   - `::` / `[::]`
   - המחרוזת `"all"` / שווה ערך ב-framework
   - כתובת bind ריקה/לא מוגדרת שברירת המחדל שלה היא all interfaces (חלק מה-frameworks)
2. אין middleware של אימות שרשום לרוץ ללא תנאי לפני dispatch של route:
   - FastAPI / Starlette: אין `app.add_middleware(AuthMiddleware)` גלובלי שבודק כל request.
   - Express: אין `app.use(authMiddleware)` ברמת ה-app.
   - Flask: אין `@app.before_request` שעושה auth, או אין `Flask-Login` / `flask-httpauth` שמכסה את כל ה-routes.
3. ה-application חושף endpoints של admin / control / write (panel, settings, debug, admin API).

## הגדרות מותרות

- bind ל-`127.0.0.1` / `localhost` ל-dev / deploys של מכונה יחידה (ברירת מחדל מועדפת).
- middleware של אימות ברמת framework, שדוחה בקשות בלי token / session תקפים לפני שכל route רץ (לא רק decorators של `@require_auth` שיכולים להישכח ב-routes חדשים).
- בקרות גישה ברמת רשת (firewall, ingress allowlist) מתועדות ב-config של ה-deployment.

## False positives

- HTTPS termination proxy שאוכף mTLS / client certs מול שרת אחרת פתוח (ודא שה-proxy באמת לפנים ונדרש).
- endpoint רק ל-health-check ב-`:/healthz` מקובל ב-`0.0.0.0` אם הוא לא מחזיר נתונים רגישים.

## חומרה

CRITICAL — לכל מי שיש גישת רשת ל-port יש גישת admin / write; שכיח בסביבות dev שקודמו בטעות ל-prod או נחשפו דרך security groups של cloud עם הגדרה שגויה.
