# cron-terminal-state

זהה tasks מתוזמנים / cron שבהם ה-filter של ה-query הראשי לעולם לא יכול להפוך False אחרי עיבוד מוצלח — מה שמוביל ל-reprocessing אינסופי, side-effects כפולים, ושריפת מכסת API.

## דווח כשמתקיימים כל הבאים

1. הקוד הוא task תקופתי / מתוזמן (Celery beat task, APScheduler job, script שמופעל על ידי cron, handler של `setInterval` בצד שרת, ערך cron של Render).
2. ה-task מריץ query (`SELECT ... WHERE ...`) ומפעיל פעולה על כל שורה (`UPDATE`, `INSERT`, קריאה חיצונית).
3. סעיף ה-`WHERE` משתמש באחת מה-heuristics האלה של signal-לא-שלם:
   - `column IS NULL` כש-terminal states (spam, rejected, abandoned) גם הם NULL לעמודה הזו.
   - `attempts < MAX_ATTEMPTS` כש-שורות שמוצו (`attempts == MAX_ATTEMPTS`) נשארות באותו status לנצח.
   - `status IN (...)` בלי לוודא שהפעולה באמת מוציאה את השורה מה-filter set.
4. הפעולה אינה כותבת עמודה שמבטיחה יציאה מה-filter set.

## תנאי יציאה נדרשים

כל cron query חייב לסנן על עמודה שהפעולה **כותבת במפורש** בהצלחה:
- `processing_status = 'pending'` → אחרי הצלחה, הפעולה מגדירה `'done'`.
- `done_at IS NULL` → אחרי הצלחה, הפעולה מגדירה `done_at = now()`.
- `attempts < MAX` ו-כש-`attempts == MAX`, מעבר ל-state סופי (`status='failed'`).

## קשור: שגיאות scope של filter

דווח גם באותה סקירה:
- filter שמופעל אחרי בדיקת "override / force-send" (משתמשים חסומים צריכים תמיד להיות מסוננים קודם).
- filter צר מדי שמוציא מקרים לגיטימיים (למשל `channel='whatsapp'` שמפספס leads שמעדיפים email).

## False positives

- cron של reporting (logs בלבד, בלי כתיבות DB / קריאות חיצוניות) — לולאה בסדר.
- tasks one-shot של startup (לא תקופתיים).

## חומרה

HIGH — לולאות אינסופיות מרוקנות compute, מכסת API, ומייצרות התראות / הודעות כפולות למשתמשי קצה.
