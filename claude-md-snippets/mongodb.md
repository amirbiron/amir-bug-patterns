# MongoDB (להעתקה ל-CLAUDE.md — פרויקטים עם מונגו/Atlas)

1. **`partialFilterExpression` מקבל רשימה סגורה של אופרטורים.** מותר: שוויון (`field: value` / `$eq`), `$exists: true`, `$gt`/`$gte`/`$lt`/`$lte`, `$type`, `$and`, `$or`, `$in`, `$geoWithin`, `$geoIntersects`. ‏**`$ne`, `$not` ו-`$nin` אינם נתמכים** ויצירת האינדקס נכשלת — כלומר האילוץ הייחודי או האינדקס פשוט לא קיימים, והקוד ממשיך. השתמש ב-`$exists` + `$type`, **וּודא שהערך הריק לא נכתב מלכתחילה**, כי אלה לא אותה סמנטיקה.

2. **סדר המפתחות באינדקס הוא סדר השאילתה.** לכל `create_index` — הערה עם ה-`filter` וה-`sort` שהוא משרת, ואימות ב-`explain` שהשאילתה בוחרת בו בפועל. ולא `try/except: pass` סביב `drop_index` — מחיקה שנכשלת בשקט משאירה שני אינדקסים סותרים.

3. **מחרוזת בלי `$` בתוך `$project` היא קבוע, לא שדה.** `{"file_name": "<value>"}` מחזיר את הקבוע. אינו זורק, בניגוד ל-`$limit`. ובאותה משפחה: שאילתה שעברה סיבוב דרך JSON איבדה טיפוסים — תאריך שהפך למחרוזת תואם 0 מסמכים ומחזיר `explain` מושלם לכאורה. Extended JSON (`bson.json_util`) בשני הכיוונים.

4. **`$setOnInsert` ו-`$set` לא נוגעים באותו שדה** — מונגו זורקת conflict והעדכון נכשל כולו.

5. **ההיטלה לפני המיון.** `$project` שמסיר שדה כבד (`code`, `content`, `embedding`) שייך **לפני** `$sort` ו-`$group`. שגיאה 292 היא `QueryExceededMemoryLimitNoDiskUseAllowed` — ב-Atlas ‏`allowDiskUse` מועבר ואינו עוזר, ולכן הוא לא הפתרון וגם לא האבחנה.

6. **`if collection:` זורק `NotImplementedError`.** pymongo אוסר בכוונה על בדיקת אמת בוליאנית על `Collection` / `Database` / `Cursor`. תמיד `is not None`.

7. **חיתוך טקסט בתווים ולא בבייטים** — `$substrCP` / `$strLenCP`. ‏`$regexFind ← idx` הוא אינדקס **תווים**. ראה `hebrew.md` §6.

ראה `BY-STACK/mongodb.md`.
