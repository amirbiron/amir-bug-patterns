# background-thread-liveness

זהה background threads קריטיים (בוט לצד פאנל, worker לצד web, consumer לצד API) שמותם אינו מורגש: חריגה ב-thread לא מפילה את התהליך, ה-health check של הפלטפורמה בודק רק את ה-HTTP — והשירות נראה "חי" בזמן שהלב שלו מת.

## דווח כשמתקיים אחד מהבאים

1. **`threading.Thread` / `asyncio.create_task` לרכיב קריטי בלי supervision.** חריגה (כולל `SystemExit`!) ב-thread לא עוצרת את התהליך הראשי — Python מדפיס traceback וממשיך. דרוש אחד מאלה: wrapper שתופס, מדווח, ומפיל את התהליך (`os._exit(1)` — כדי שהפלטפורמה תפעיל restart); `threading.excepthook` שעושה זאת; או לולאת restart מפוקחת עם backoff.

2. **Health endpoint שבודק רק את ה-web.** `/health` שמחזיר 200 כשה-Flask/FastAPI חי — בלי לבדוק `thread.is_alive()` ו-heartbeat עדכני (timestamp שה-thread מעדכן בכל iteration). Render/K8s יראו שירות תקין כשהבוט מת לפני שעה.

3. **`daemon=True` על thread קריטי.** נוח לכיבוי, אבל מבטיח שאף אחד לא ימתין לו ולא ישים לב שהוא מת. thread קריטי הוא לא daemon — או שהוא daemon עם heartbeat מנוטר.

4. **`asyncio.create_task` בלי שמירת reference ובלי callback.** ה-task נאסף ב-GC או נכשל בשקט; דרוש `task.add_done_callback` שבודק `task.exception()`.

## False positives

- threads אופציונליים באמת (מטריקות, ניקוי עיתי) שכשל שלהם מוצהר כנסבל — אבל גם אז עדיף לוג ברור על שתיקה.
- מערכות עם supervisor חיצוני שכבר מנטר את ה-thread (systemd עם watchdog, Celery עם ניטור workers).

## חומרה

HIGH — downtime שקט: הבוט מת, הפאנל חי, אין התראה, והלקוח מגלה ראשון.

## ראיות

8-Projects #8 (Amazon-bot `c27c769`): `SystemExit` נזרק ב-thread של הבוט; Python לא מפסיק process בגלל חריגה ב-thread. הפאנל המשיך לרוץ ו-Render לא זיהה תקלה — הבוט מת והשירות נראה תקין.
