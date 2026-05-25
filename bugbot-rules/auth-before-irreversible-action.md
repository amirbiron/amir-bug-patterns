# auth-before-irreversible-action

**CRITICAL — auth bypass / OAuth takeover / שימוש לרעה ב-OTP**

זהה flows של אימות / אישור שמשלחים פעולה בלתי הפיכה (שליחת OTP, קישור חשבון, קביעת סיסמה) לפני שמירת state ה-verification, או שמציגים נתיב fallback בכשל storage.

## דווח כשמתקיים אחד מהבאים

1. **שליחת credential לפני storage.** סדר הפעולות:
   ```
   send_otp(user, code)  ❌
   redis.set(f"otp:{user}", code, ex=TTL)
   ```
   אם Redis נכשל אחרי send, למשתמש יש קוד ביד אבל אף verifier לא מתאים. גרוע יותר, אם יש נתיב fallback "דלג על OTP ב-Redis miss", התוקף מקבל עקיפה.

   סדר נכון:
   ```
   redis.set(f"otp:{user}", code, ex=TTL)
   send_otp(user, code)
   ```

2. **fallback ללא-OTP בכשל storage.** כל נתיב קוד שממשיך עם אימות כשאחסון verification לא בר השגה. fail closed.

3. **endpoint של "set password" / "register" / "link account" שמקבל email** בלי לוודא שהמבקש באמת בעל ה-email או זהות ה-OAuth. אם חשבון כבר קיים דרך OAuth (או כל IdP), דחה את קביעת הסיסמה אלא אם מאומת כאותו משתמש, או הוכח דרך קישור one-time מאומת שנשלח ל-email המקושר ל-OAuth.

4. **טיפול בשגיאת login מאחד 5xx → "invalid credentials".** הסתעפות:
   - `401 / 403` → "Invalid credentials" (גנרי; לא דולף אם ה-email קיים).
   - `5xx` → "Service temporarily unavailable" + התראה למוניטורינג.
   - `429` → "Too many attempts."
   לעולם אל תציג "invalid credentials" לשגיאות DB.

## False positives

- storage סינכרוני שבו ה-dispatch וה-persist בטרנזקציה אחת (atomic).
- טסטים עם storage verification ב-mock.

## חומרה

CRITICAL — auth bypass, השתלטות על credential, או denial-of-auth-availability שמוצג כשגיאת משתמש.
