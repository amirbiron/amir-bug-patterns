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

## דוגמאות אמיתיות

Campaign AI היה הפרויקט הצפוף ביותר בדפוס הזה — 11%+ מהבאגים (23 מ-210):
- **P12** (`20ee07c`): `_handle_no_connection` / `_handle_token_unavailable` תמיד כתבו `status='failed'`, גם על retry אחרי שנוצרו IDs; `cleanup_stuck_campaigns` סרק רק `pushing`. תוצאה: orphan Meta campaigns ששרפו תקציב לנצח.
- **P46** (`14b65af`): `process_job` כתב status סופי דרך best-effort `_update_job`; DB failure לא retried; `claim_next_job` בוחר רק `pending` → jobs תקועים `running` לנצח.
- **P60** (`36b433a`): `send_notification` handler זרק `ValueError` על סוג לא מוכר; runner התייחס לזריקה כ-transient → 3 retries → `job=failed` בזמן שההתראה נשארה `pending` לנצח.
- **P64** (`095f8f9`): "skipped" בלי סגירת action → action נשאר `due` → fetch תפס אותו כל שעה + spam ל-Sentry. תיקון: permanent/unknown → terminal `escalated`.
- **P66** (`a75ab3b`): CAS ל-`push_failed` רץ **לפני** `escalate_session`; זריקה של escalate → השורה כבר לא בסלקציה. תיקון: signal-first (escalate), commit-last (CAS).
- **P77** (`ef7933c`): flag `offer_generating` בלי TTL → כשל אחרי הצלחת claim נעל לנצח. תיקון: TTL recovery במיגרציה 0060.
- **P124** (`7968842`): `.lt("trial_ends_at", "now()")` — מחרוזת literal ב-PostgREST, לא DB function. Cron של day-8 שהיה אמור לעבוד בסוף trial לא רץ.
- **P197** (`283a3ca`): `charge_campaign` "SKIPPED" בלי מעבר terminal → crons תפסו את הקמפיין בכל tick → `capture_alert` 1440 פעם/יום/קמפיין.

הדפוס הפרונטי-דומיננטי בפרויקטים עם reconcilers ו-workers מרובים.
