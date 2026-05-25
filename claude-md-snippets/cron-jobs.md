# דפוסי Cron-job (להעתקה ל-CLAUDE.md)

1. **כל cron query צריך עמודת terminal-state מפורשת.** סנן על `processing_status='done'` / `archived_at IS NOT NULL` / `done_at` — לעולם לא על heuristics כמו `lead_id IS NULL` (terminal states כמו `spam`/`not_business` גם הם NULL), `attempts < MAX` (שורות שמוצו נשארות pending), או `status IN (...)` בלי לבדוק מה הפעולה כותבת.

2. **כש-`attempts == MAX`, עבור עם השורה ל-state סופי** (`status='failed'`, `processing_status='exhausted'`). אל תשאיר `pending`.

3. **סימטריה action-vs-filter:** כשהפעולה מצליחה, זהה איזה תנאי `WHERE` הופך False. אם התשובה היא "אף אחד לא מובטח", הוסף עמודה שהפעולה כותבת.

4. **סדר filter: deny קודם, ואז business logic, ואז overrides.** filters של blocked / spam / fraud רצים *לפני* כל בדיקת `force_send` / `whitelist_override`.

5. **race של beat scheduler + dispatcher ad-hoc:** CAS update atomic `UPDATE ... WHERE status='pending' RETURNING id`, בדוק rowcount.

6. **Celery + async engine:** engine ברמת module נקשר ל-loop של זמן ה-import → task שני נכשל. צור lazy לכל task, או `engine.dispose()` בין tasks.

7. **קריאות sync ב-cron async חוסמות את event loop.** עטוף עם `asyncio.to_thread(fn)` / `loop.run_in_executor`.

8. **קצוות זמן:** ולידציה לשעות 0-23 (לא "24:00"); `max(timedelta(0), now - last_seen)` לבטיחות clock-skew.

9. **state של dedup בזיכרון בלי eviction → דליפת זיכרון.** השתמש ב-TTL / LRU או Redis עם `EXPIRE`.

10. **state כמקור-אמת-יחיד חי ב-DB, לא ב-globals ברמת module.** Cross-process imports מתפצלים.

ראה `BY-STACK/cron-jobs.md` לדוגמאות קוד.
