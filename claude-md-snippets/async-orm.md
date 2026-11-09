# דפוסי SQLAlchemy async (להעתקה ל-CLAUDE.md)

1. **AsyncSession אחד לכל task.** לעולם אל תעביר את אותו session ל-coroutines מרובים דרך `asyncio.gather` / `asyncio.create_task` — sessions לא בטוחים ל-task. כל task פותח את שלו:
   ```python
   async with sessionmaker() as session: ...
   ```

2. **אין גישה ל-attributes של ORM אחרי `await session.rollback()`.** ה-rollback מסמן את כל האובייקטים כפגי תוקף, והגישה מנסה טעינה עצלה מחוץ להקשר ה-async — `MissingGreenlet`. חלץ primitives (`.id`, `.email`) **לפני** ה-try-block (וכך גם לפני commit עם `expire_on_commit=True`), או `session.expunge(obj)` כדי לנתק — גם הוא לפני ה-rollback: באובייקט המנותק נשארים זמינים השדות שכבר נטענו, וגישה לשדה שפג תוקפו או שלא נטען (למשל אחרי commit עם `expire_on_commit=True`) זורקת `DetachedInstanceError`. ו-`expunge` מוציא את האובייקט מהמעקב — שינוי שלא נשמר בו לא ייכתב; אובייקט שעוד משתנה — רק חילוץ primitives. וערך שכבר נשלח ב-flush נשאר באובייקט המנותק גם אחרי שה-rollback ביטל אותו במסד — כשצריך את מצב המסד, טוענים מחדש אחרי ה-rollback.

3. **`await session.commit()` בתוך לולאה → `await session.refresh(obj)` לפני קריאה מחדש של attributes.** ההתנהגות תלויה ב-`expire_on_commit`: ב-`True` (ברירת המחדל) commit מסמן את כל האובייקטים כפגי תוקף, והגישה ב-async זורקת `MissingGreenlet`; ב-`False` השדות נשארים עם הערכים מלפני ה-commit, גם אם המסד השתנה. ה-`refresh` על אובייקט ORM (מ-`scalars()`), לא על `Row`; והוא לא טוען קשר עצל. ‏`refresh(obj, attribute_names=[...])` מרענן רק את מה שברשימה — כולל קשר עצל (מ-SQLAlchemy 2.0.4) — ושדה שלא ברשימה נשאר פג תוקף: `["email", "rel"]`, לא רק `["rel"]`. החלופה — לרכז את ה-commits מחוץ ללולאה.

4. **Celery + async engine:** Celery לא מריץ `async def` כ-task — task סינכרוני שעוטף `asyncio.run(...)`. engine ברמת module: החיבורים ב-pool נקשרים ל-loop שבו נפתחו (של ה-task הראשון, לא של זמן ה-import), וה-task הבא רץ ב-loop חדש (`asyncio.run`) ונכשל ב-`attached to a different loop`. צור engine לכל task וסגור אותו ב-`await engine.dispose()` בסופו, לפני שה-loop נסגר — עובד גם כשה-tasks חופפים, בלי תנאים. engine משותף: עם pool — רק כשה-tasks בתהליך רצים אחד-אחד (prefork), ועם `dispose()` בסוף כל task, כי במקביל חיבורים עוברים בין loops; עם `poolclass=NullPool` — גם במקביל, ובלבד שהחיבור הראשון קרה לפני שה-tasks המקבילים מתחילים (בלי זה הם נתקעו). או engine סינכרוני ב-Celery ואסינכרוני רק בשכבת ה-API.

5. **`joinedload` + `with_for_update()` נופל ב-Postgres** כש-`joinedload` נבנה כ-LEFT OUTER JOIN (ברירת המחדל): ה-DB זורק `FOR UPDATE cannot be applied to the nullable side of an outer join`. כשהקשר אופציונלי: `with_for_update(of=Model)` (ובישות aliased — ה-alias עצמו), שנועל רק את הטבלה הראשית ושומר את ה-LEFT JOIN; כשההחלטה תלויה גם בשורה המקושרת — נועלים אותה בנפרד וקוראים אותה אחרי הנעילה. כשהקשר חובה: `contains_eager` + `join` מפורש, או `joinedload(..., innerjoin=True)` כשאין בשאילתה outer join אחר — שניהם INNER JOIN, שמשמיט בשקט שורות בלי קשר, ובלי `of` נועל גם את שורות הטבלה המקושרת.

6. **פעולות מחרוזת של Python על Column expressions הן no-ops שקטים** ב-SQL. השתמש ב-`func.trim(col)`, `func.lower(col)`.

7. **CAS על עמודה nullable צריך הסתעפות `IS NULL`.** `WHERE col = NULL` מוערך כ-`NULL`, לא `TRUE`. ב-SQLAlchemy: `col.is_(None)` כשהערך הוא `None`.

8. **על `UPDATE` עם `rowcount=0` (דחיית CAS), עדיין לוג activity עם `metadata.applied=false`.** Cron / dashboards downstream תלויים בלוג כדי לדעת ש-events קרו.

ראה `BY-STACK/async-orm.md` בריפו amir-bug-patterns לדוגמאות קוד.
