# MongoDB (להעתקה ל-CLAUDE.md — פרויקטים עם מונגו/Atlas)

1. **`partialFilterExpression` מקבל רשימה סגורה של אופרטורים.** מותר: שוויון (`field: value` / `$eq`), `$exists: true`, `$gt`/`$gte`/`$lt`/`$lte`, `$type`, `$and`, `$or`, `$in`, `$geoWithin`, `$geoIntersects`. ‏**`$ne`, `$not` ו-`$nin` אינם נתמכים** ו-`create_index` זורק `OperationFailure`. אם הקריאה יושבת ב-`ensure_*_indexes()` שעוטפת ב-`try/except` וממשיכה — האילוץ הייחודי או האינדקס פשוט לא קיימים והמערכת עולה כרגיל; בלי הבליעה השירות נופל בעלייה. השתמש ב-`$exists` + `$type`, **וּודא שהערך הריק לא נכתב מלכתחילה**, כי אלה לא אותה סמנטיקה.

2. **סדר המפתחות באינדקס נקבע לפי ESR, לא לפי סדר השדות בשאילתה.** סדר ה-predicates בשאילתה אינו רלוונטי, ומפתחות שוויון יכולים להופיע ביניהם בכל סדר — אבל **כולם קודמים** לשדות המיון והטווח: ‏Equality ← Sort ← Range (וכשה-range סלקטיבי במיוחד, ‏ERS). לכל `create_index` — הערה עם ה-`filter` וה-`sort` שהוא משרת, ו**אימות ב-`explain`** שהשאילתה בוחרת בו בפועל. ולא `try/except: pass` סביב `drop_index` — מחיקה שנכשלת בשקט משאירה שני אינדקסים סותרים.

3. **מחרוזת בלי `$` בתוך `$project` היא קבוע, לא שדה.** `{"file_name": "<value>"}` מחזיר את הקבוע. אינו זורק, בניגוד ל-`$limit`. ובאותה משפחה: שאילתה שעברה סיבוב דרך JSON איבדה טיפוסים — תאריך שהפך למחרוזת תואם 0 מסמכים ומחזיר `explain` מושלם לכאורה. Extended JSON (`bson.json_util`) בשני הכיוונים.

4. **`$setOnInsert` ו-`$set` לא נוגעים באותו שדה** — מונגו זורקת conflict והעדכון נכשל כולו.

5. **ההיטלה לפני המיון — כשהשדה לא נחוץ בהמשך.** `$project` שמסיר שדה כבד (`code`, `content`, `embedding`) שייך **לפני** `$sort` ו-`$group`, אלא אם שלב מאוחר משתמש בו (`$first: "$$ROOT"`, `$push`, accumulator שנוגע בשדה) — שם ההסרה משנה את התוצאה וזה באג. ולגבי שגיאה 292 (`QueryExceededMemoryLimitNoDiskUseAllowed`): ‏`allowDiskUse: true` **כן** מתיר ל-`$sort` ול-`$group` לגלוש לדיסק, אבל **אשכולות Atlas Free ו-Flex מתעלמים ממנו** ומתנהגים כאילו הוא `false`. כלומר הדגל אינו תחליף לצינור יעיל, ובאשכול שתומך בו — לא להסיר אותו.

6. **`if collection:` זורק `NotImplementedError`.** pymongo אוסר בכוונה על בדיקת אמת בוליאנית על `Collection` / `Database` / `Cursor`. תמיד `is not None`.

7. **חיתוך טקסט בתווים ולא בבייטים** — `$substrCP` / `$strLenCP`. ‏`$regexFind ← idx` הוא אינדקס **תווים**. ראה `BY-STACK/hebrew-source.md` H6.

ראה `BY-STACK/mongodb.md`.
