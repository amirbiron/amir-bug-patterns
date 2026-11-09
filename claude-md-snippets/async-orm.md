# דפוסי SQLAlchemy async (להעתקה ל-CLAUDE.md)

1. **AsyncSession אחד לכל task.** לעולם אל תעביר את אותו session ל-coroutines מרובים דרך `asyncio.gather` / `asyncio.create_task` — sessions לא בטוחים ל-task. כל task פותח את שלו:
   ```python
   async with sessionmaker() as session: ...
   ```

2. **אין גישה ל-attributes של ORM אחרי `await session.rollback()`.** ה-rollback מסמן את כל האובייקטים כפגי תוקף, והגישה מנסה טעינה עצלה מחוץ להקשר ה-async — `MissingGreenlet`. חלץ primitives (`.id`, `.email`) **לפני** ה-try-block, או `session.expunge(obj)` כדי לנתק — גם הוא לפני ה-rollback, ועל אובייקט שהשדות שלו טעונים. אחרי ה-rollback, או אחרי commit עם `expire_on_commit=True`, האובייקט המנותק ריק וזורק `DetachedInstanceError`.

3. **`await session.commit()` בתוך לולאה → `await session.refresh(row)` לפני קריאה מחדש של attributes.** ההתנהגות תלויה ב-`expire_on_commit`: ב-`True` (ברירת המחדל) commit מסמן את כל האובייקטים כפגי תוקף, והגישה ב-async זורקת `MissingGreenlet`; ב-`False` השדות נשארים עם הערכים מלפני ה-commit, גם אם המסד השתנה. החלופה — לרכז את ה-commits מחוץ ללולאה.

4. **Celery + async engine:** engine ברמת module: החיבורים ב-pool נקשרים ל-loop שבו נפתחו (של ה-task הראשון, לא של זמן ה-import), וה-task הבא רץ ב-loop חדש (`asyncio.run`) ונכשל ב-`attached to a different loop`. צור lazy לכל task, או קרא ל-`engine.dispose()` בין tasks, או `poolclass=NullPool`, או engine סינכרוני ב-Celery ואסינכרוני רק בשכבת ה-API.

5. **`joinedload` + `with_for_update` לא תואמים** → השתמש ב-`contains_eager` + join מפורש. ב-Postgres `joinedload` הוא LEFT OUTER JOIN, וה-DB זורק `FOR UPDATE cannot be applied to the nullable side of an outer join`. אבל `contains_eager` + `join` הוא INNER JOIN ומשמיט בשקט שורות בלי קשר — נכון רק כשהקשר חובה. כשהקשר אופציונלי: `with_for_update(of=Model)`, שנועל רק את הטבלה הראשית ושומר את ה-LEFT JOIN.

6. **פעולות מחרוזת של Python על Column expressions הן no-ops שקטים** ב-SQL. השתמש ב-`func.trim(col)`, `func.lower(col)`.

7. **CAS על עמודה nullable צריך הסתעפות `IS NULL`.** `WHERE col = NULL` מוערך כ-`NULL`, לא `TRUE`. ב-SQLAlchemy: `col.is_(None)` כשהערך הוא `None`.

8. **על `UPDATE` עם `rowcount=0` (דחיית CAS), עדיין לוג activity עם `metadata.applied=false`.** Cron / dashboards downstream תלויים בלוג כדי לדעת ש-events קרו.

ראה `BY-STACK/async-orm.md` בריפו amir-bug-patterns לדוגמאות קוד.
