# דפוסי SQLAlchemy async (להעתקה ל-CLAUDE.md)

1. **AsyncSession אחד לכל task.** לעולם אל תעביר את אותו session ל-coroutines מרובים דרך `asyncio.gather` / `asyncio.create_task` — sessions לא בטוחים ל-task. כל task פותח את שלו:
   ```python
   async with sessionmaker() as session: ...
   ```

2. **אין גישה ל-attributes של ORM אחרי `await session.rollback()`.** חלץ primitives (`.id`, `.email`) **לפני** ה-try-block, או `session.expunge(obj)` כדי לנתק.

3. **`await session.commit()` בתוך לולאה → `await session.refresh(row)` לפני קריאה מחדש של attributes.** Commit מרענן רק PK כברירת מחדל.

4. **Celery + async engine:** engine ברמת module נקשר ל-loop של זמן ה-import → task שני נכשל. צור lazy לכל task, או קרא ל-`engine.dispose()` בין tasks.

5. **`joinedload` + `with_for_update` לא תואמים** → השתמש ב-`contains_eager` + join מפורש.

6. **פעולות מחרוזת של Python על Column expressions הן no-ops שקטים** ב-SQL. השתמש ב-`func.trim(col)`, `func.lower(col)`.

7. **CAS על עמודה nullable צריך הסתעפות `IS NULL`.** `WHERE col = NULL` מוערך כ-`NULL`, לא `TRUE`. ב-SQLAlchemy: `col.is_(None)` כשהערך הוא `None`.

8. **על `UPDATE` עם `rowcount=0` (דחיית CAS), עדיין לוג activity עם `metadata.applied=false`.** Cron / dashboards downstream תלויים בלוג כדי לדעת ש-events קרו.

ראה `BY-STACK/async-orm.md` לדוגמאות קוד.
