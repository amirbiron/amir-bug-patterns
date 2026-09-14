# mongo-index-and-operator-traps

זהה מסמכי אינדקס ושלבי אגרגציה שמונגו **מקבלת** אף שהם אומרים משהו אחר ממה שהתכוונת. רוב הממצאים כאן אינם קריסות — הם הסכמה שקטה לפעולה אחרת.

## דווח כשמתקיים אחד מהבאים

1. **`$ne` / `$not` / `$nin` בתוך `partialFilterExpression`.** התיעוד מונה רשימה סגורה: שוויון (`field: value` / `$eq`), `$exists: true`, `$gt`/`$gte`/`$lt`/`$lte`, `$type`, `$and`, `$or`, `$in`, `$geoWithin`, `$geoIntersects` (https://www.mongodb.com/docs/manual/core/index-partial/). יצירת האינדקס נכשלת, ולכן האילוץ הייחודי או האינדקס **אינם קיימים** והקוד ממשיך לרוץ. השתמש ב-`$exists` + `$type` — **ושים לב שזו אינה אותה סמנטיקה**, ולכן מחרוזת ריקה נחסמת בשכבת הכתיבה.

2. **`sparse=True` במקום `partialFilterExpression`** על אינדקס ייחודי — `sparse` מדלג רק על מסמכים שבהם השדה **חסר**, לא על מסמכים שבהם הוא ריק או `null`.

3. **סדר מפתחות באינדקס מורכב שאינו סדר השאילתה** (הסינון והמיון). לכל `create_index` — הערה עם השאילתה שהוא משרת, ואימות ב-`explain` שהיא בוחרת בו.

4. **`try/except: pass` סביב `drop_index`** — מחיקה שנכשלת בשקט משאירה שני אינדקסים סותרים.

5. **מחרוזת בלי `$` בתוך `$project`** — `{"f": "<value>"}` מחזיר קבוע, לא שדה, ואינו זורק.

6. **`$setOnInsert` ו-`$set` על אותו שדה** — מונגו זורקת conflict והעדכון כולו נכשל.

7. **`$project` שמסיר שדה כבד, שממוקם אחרי `$sort` / `$group`.** וכשמגיעה שגיאה 292 (`QueryExceededMemoryLimitNoDiskUseAllowed`) — `allowDiskUse` אינו הפתרון ב-Atlas.

8. **`if collection:` / `if not db:` על אובייקטים של pymongo** — `Collection` / `Database` / `Cursor` זורקים `NotImplementedError` בכוונה. תמיד `is None` / `is not None`.

9. **`$substrBytes` / `$strLenBytes` / `$indexOfBytes` על שדה טקסט** — במיוחד מעורבב עם `$regexFind ← idx` שהוא **תווים**. ראה `hebrew-source-and-data.md` §6.

## False positives

- `$ne` בשאילתה רגילה — מותר לגמרי; האיסור הוא רק בתוך `partialFilterExpression`.
- מדידה בבייטים שהיא באמת על גודל אחסון או תעבורה.
- אינדקס שנוצר ידנית בכלי ניהול ומתועד ככזה.

## חומרה

HIGH לסעיפים 1–2 (אילוץ ייחודיות שאינו קיים = כפילויות בנתונים). MEDIUM לשאר.
