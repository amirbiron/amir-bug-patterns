# cookie-session-last-write-wins

זהה ערך שנכתב ל-session שהוא cookie (Flask בלי Flask-Session), כשבקשה **אחרת** צריכה למצוא אותו — state של OAuth, ‏`code_verifier` של PKCE, nonce, יעד חזרה, דגל "פעם אחת" — או ערך שנצרך ב-`session.pop` כדי שלא יעבוד שוב. ה-cookie נמצא אצל הדפדפן, והדפדפן שומר את ה-Set-Cookie האחרון שהגיע. כל תשובה של בקשה מקבילה מחזירה את ה-cookie עם ה-session כפי שהבקשה הזו ראתה אותו בסופה — מה שהיה בתחילתה, ועוד מה שהיא עצמה כתבה.

## החתימה, בשורה אחת

**כתיבה ל-session ב-cookie היא "האחרון מנצח" מול כל בקשה מקבילה של אותו דפדפן — ולא רק מול בקשות שכותבות.** ב-session קבוע Flask שולח את ה-cookie בכל תשובה: ``SessionInterface.should_set_cookie`` מחזיר ``session.modified or (session.permanent and SESSION_REFRESH_EACH_REQUEST)`` (Flask 3.1.2, ``flask/sessions.py``), ו-`SESSION_REFRESH_EACH_REQUEST` הוא `True` כברירת מחדל.

## דווח כשמתקיים אחד מהבאים

1. **`session[...] = ` של ערך שהבקשה הבאה בזרימה חייבת למצוא**, באפליקציה שה-session שלה cookie — ובפרט ב-session קבוע, שבו כל תשובה כותבת, גם כזו שרק קראה. ובמיוחד לפני `redirect` לצד שלישי (OAuth, תשלום), שבזמנו הדף הקודם עוד חי ושולח בקשות.
2. **`session.pop(...)` כמנגנון של "פעם אחת"** — state, ‏nonce, ‏`code_verifier`, טוקן שיתוף, יציאה ממצב מיוחד — logout (`session.clear()`), התחזות, מצב עריכה. בקשה שהתחילה לפני ה-pop מחזירה את הערך. וב-logout, ב-session קבוע: תשובה מקבילה של בקשה שרק קראה מחזירה את ה-cookie המחובר, והמשתמש נשאר מחובר (לא נמדד).
3. **מקור לבקשות מקבילות באותו דפדפן:** `fetch` ב-`beforeunload` / `pagehide` / `visibilitychange`, ‏`setInterval` של polling, טעינה ברקע. לא תנאי לדיווח — כמעט לכל אפליקציה יש אחד — אבל הוא מה שהופך את החשיפה לתקלה.

## התיקון

- **ערך שזרימה תלויה בו נשמר בשרת**, צמוד למשתמש (או ל-id אקראי שנשמר ב-session פעם אחת ולא משתנה): במסד, עם תוקף. ב-cookie נשאר רק מה שלא משתנה במהלך הזרימה — זהות המשתמש.
- **"פעם אחת" נאכף בשרת, בפעולה אטומית** — `find_one_and_update` עם `$unset` / `DELETE ... RETURNING` — ולא ב-`session.pop`.
- **כל דחייה נרשמת עם סיבה.** כאן הדחייה הייתה במסלול שלא כתב לוג, ולכן התקלה נראתה כמו "גוגל לא מחזיר".
- ‏`SESSION_REFRESH_EACH_REQUEST = False` **מצמצם ולא סוגר:** כשהוא False, תשובה שלא שינתה את ה-session אינה שולחת cookie; בקשה מקבילה שכן כותבת עדיין דורסת. ויש לו מחיר: התוקף של session קבוע לא מתחדש בכל בקשה.

## איך בודקים

‏test client עם `use_cookies=True` מחזיק cookie אחד ומריץ בקשות ברצף, ולכן המרוץ לא יכול לקרות בו, והטסט ירוק גם על הקוד השבור. הטסט מעביר את ה-cookie ביד (`use_cookies=False`, כותרת `Cookie`), שולח את שתי הבקשות עם ה-cookie שלפני הכתיבה, ומשתמש בהמשך ב-cookie של התשובה שהגיעה **אחרונה**. ובתצורת הייצור: `session.permanent = True`, אחרת Flask לא מחזיר cookie בתשובה שקוראת בלבד, והטסט לא משחזר כלום.

## False positives

- **session בצד השרת** (Flask-Session עם Redis/מונגו, או מימוש משלך): ה-cookie נושא רק מזהה, והכתיבות לא נמחקות כך. (מרוץ בין כתיבות בשרת הוא `race-toctou`.)
- **ערך שנכתב פעם אחת בהתחברות ולא משתנה** — `user_id`. תשובה מקבילה מחזירה את אותו ערך.
- **מסגרות אחרות:** לא נבדק. ‏Starlette `SessionMiddleware` ודומיו צריכים בדיקה מול הגרסה המותקנת לפני שמחילים עליהם את הכלל.

## חומרה

MEDIUM. אין שגיאה, ושתי הבקשות מצליחות מבחינת השרת. התקלה תלויה בתזמון — כשהבקשה ברקע מהירה, הכול עובד — ולכן היא נראית כמו "לפעמים לא עובד".

## ראיות

CodeBot, PR #3525 (2026-10-05): חיבור Google Drive מהוובאפ. בלוג של Render ‏`POST /api/ui_prefs` הסתיימה כ-100ms אחרי ההפניה של `/api/drive/auth`; בדפדפן Chromium אמיתי הקוד הישן נדחה כ-`csrf` והחדש התחבר. הצד השני (`session.pop` שחוזר) נמדד ב-test client.

## ראה גם

- `bugbot-rules/race-toctou.md` — אותו "האחרון מנצח", כשהמאגר הוא מסד בשרת.
- `docs/source-projects/campaign-ai-patterns.md`, "OAuth state ניתן ל-replay" — state של OAuth בלי שימוש חד-פעמי, בתכנון. כאן השימוש החד-פעמי קיים ב-`session.pop`, ובקשה מקבילה מבטלת אותו.
- `bugbot-rules/return-value-failure-unchecked.md` — הדחייה כאן הייתה במסלול בלי לוג.
