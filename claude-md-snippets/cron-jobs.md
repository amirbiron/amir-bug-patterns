# דפוסי Cron-job (להעתקה ל-CLAUDE.md)

1. **כל cron query צריך עמודת terminal-state מפורשת.** סנן על `processing_status='done'` / `archived_at IS NOT NULL` / `done_at` — לעולם לא על heuristics כמו `lead_id IS NULL` (terminal states כמו `spam`/`not_business` גם הם NULL), `attempts < MAX` (שורות שמוצו נשארות pending), או `status IN (...)` בלי לבדוק מה הפעולה כותבת.

2. **כש-`attempts == MAX`, עבור עם השורה ל-state סופי** (`status='failed'`, `processing_status='exhausted'`). אל תשאיר `pending`.

3. **סימטריה action-vs-filter:** כשהפעולה מצליחה, זהה איזה תנאי `WHERE` הופך False. אם התשובה היא "אף אחד לא מובטח", הוסף עמודה שהפעולה כותבת.

4. **סדר filter: deny קודם, ואז business logic, ואז overrides.** filters של blocked / spam / fraud רצים *לפני* כל בדיקת `force_send` / `whitelist_override`. ושלמות: למנות את כל הווריאנטים שה-filter אמור לכסות (ערוצים, סטטוסים, סוגי מקור) ולעבור על כל אחד — `channel == "whatsapp"` מפספס את מי שמעדיף email.

5. **race של beat scheduler + dispatcher ad-hoc:** CAS update atomic `UPDATE ... WHERE status='pending' RETURNING id`, בדוק rowcount.

6. **Celery + async engine:** engine ברמת module: החיבורים ב-pool נקשרים ל-loop שבו נפתחו (של ה-task הראשון, לא של זמן ה-import), וה-task הבא רץ ב-loop חדש (`asyncio.run`) ונכשל ב-`attached to a different loop`. צור lazy לכל task, או `engine.dispose()` בין tasks, או `poolclass=NullPool`.

7. **קריאות sync ב-cron async חוסמות את event loop.** עטוף עם `asyncio.to_thread(fn)` / `loop.run_in_executor`.

8. **קצוות זמן:** ולידציה לשעות 0-23 (לא "24:00"); `max(timedelta(0), now - last_seen)` לבטיחות clock-skew. וריצות חופפות (זמן עיבוד ארוך מהמרווח): נעילה (advisory lock) בתחילת כל ריצה, ודילוג אם היא מוחזקת.

9. **state של dedup בזיכרון בלי eviction → דליפת זיכרון.** השתמש ב-TTL / LRU או Redis עם `EXPIRE`.

10. **state כמקור-אמת-יחיד חי ב-DB, לא ב-globals ברמת module.** Cross-process imports מתפצלים.

11. **ג'וב שיוצר עותק "אם חסר" צריך גם שלב שמוחק עותק שהמקור כבר לא מכיר.** מסלול ההסרה במקור לא תמיד מגיע אליו (שירות אחר, TTL, גרסה שהוחלפה). ובשלב הזה: כשהקריאה נכשלה או נקטעה, או שהיא לא מכירה אף פריט מהעותק (ריקה, מזהים לא שמישים, מסד אחר), לא מוחקים כלום, ורושמים אזהרה עם כמה פריטים נחסכו. קוראים מהמקור הסמכותי, מוחקים רק את מה שהג'וב היה יוצר (לא קישור ולא פריט בתהליך), דרך מנגנון המחיקה הקיים, וסופרים לפי קריאה חוזרת. מנייה של העותק שנכשלה היא שגיאה, לא רשימה ריקה.

12. **הרצה ראשונה בלי baseline שולחת את כל הבקלוג.** ג'וב "מה חדש מאז הפעם הקודמת" מכריע מה קורה כשאין פעם קודמת: לקבוע את הסמן על "עכשיו" ולא לשלוח כלום, או לשלוח פריט אחד עם ציון שזה הראשון. ההחלטה כתובה בקוד ליד `if not last_seen:`, ולא נגזרת ממה שקרה להיות ברירת המחדל.

ראה `BY-STACK/cron-jobs.md` בריפו amir-bug-patterns לדוגמאות קוד.
