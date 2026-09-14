# BY-STACK: MongoDB (אינדקסים, אגרגציה, pymongo)

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...

- MongoDB / Atlas, עם pymongo או motor
- אינדקסים שנוצרים מהקוד (`create_index` בעלייה או ב-`ensure_*_indexes`)
- צינורות אגרגציה — חיפוש, קיבוץ גרסאות, דוחות
- מסמכים עם שדה גדול (`code`, `content`, `html`, `embedding`) לצד שדות קטנים

**המודל המנטלי:** מונגו כמעט לא אומרת "לא". היא מקבלת מסמך שאומר משהו אחר ממה שהתכוונת, מריצה אותו, ומחזירה תשובה תקינה לפעולה שלא ביקשת. רוב הדפוסים כאן הם לא קריסות — הם **הסכמה שקטה לדבר הלא נכון**.

---

## דפוס 1 — `$ne` / `$not` / `$nin` בתוך `partialFilterExpression`

התיעוד הרשמי מונה **רשימה סגורה** של מה שמותר בתוך `partialFilterExpression`:

- ביטויי שוויון — `field: value` או `$eq`
- `$exists: true`
- `$gt`, `$gte`, `$lt`, `$lte`
- `$type`
- `$and`, `$or`, `$in`
- `$geoWithin`, `$geoIntersects`

מקור: https://www.mongodb.com/docs/manual/core/index-partial/

‏`$ne`, ‏`$not` ו-`$nin` **אינם ברשימה**, ו-`create_index` **זורק** — `OperationFailure`.

**ומכאן הנקודה שקובעת אם זה רועש או שקט:** אם הקריאה יושבת בפונקציית אתחול שעוטפת ב-`try/except` וממשיכה (הצורה הנפוצה: ‏`ensure_*_indexes()` שנקראת בעלייה ולא אמורה להפיל את השירות), האילוץ הייחודי או האינדקס **פשוט אינם קיימים** — והמערכת עולה כרגיל. באינדקס ייחודי זו הזמנה לכפילויות בנתונים; באינדקס של שאילתת פולינג זו סריקה מלאה בלולאה. בלי הבליעה, לעומת זאת, השירות נופל בעלייה ואי אפשר לפספס את זה.

```python
def ensure_indexes():
    try:
        coll.create_index(...)      # ← זורק OperationFailure
    except Exception:
        logger.warning("index setup failed")   # ← וכאן האילוץ נעלם בשקט
```

```python
# ❌ נכשל בשקט — האינדקס לא נוצר
coll.create_index("username", unique=True,
                  partialFilterExpression={"username": {"$type": "string", "$ne": ""}})

# ✅
coll.create_index("username", unique=True,
                  partialFilterExpression={"username": {"$exists": True, "$type": "string"}})
```

ושים לב לחצי השני של התיקון: `$exists` + `$type` **אינם** אותה סמנטיקה כמו `$ne: ""` — הם לא מוציאים מחרוזת ריקה. לכן הכלל השלם הוא *"ולוודא שהערך הריק לא נכתב מלכתחילה"*, בוולידציה בשכבת הכתיבה.

### Commits אמיתיים
- CodeBot PR #895 (`anchor_id: {"$ne": ""}`) ← PR #2121 (`username_unique`) ← PR #2627 (`needs_push: {"$ne": False}`) — **אותה טעות שלוש פעמים**, בשלושה אוספים שונים ולאורך שלושה חודשים.
- **והראיה שהיא חזרה, מהקוד של היום:** הלקח כתוב עכשיו כהערה ב-`database/manager.py:1994` ("קריטי: אינדקס חלקי לא תומך ב-`$ne`/`$not`"), כ-docstring ב-`sticky_notes_target.py:117` ("נבדק מול מונגו"), ויש עליו אפילו טסט ייעודי ב-`tests/test_note_boards_mongo.py:468`. שלוש הערות על אותו כלל הן מה שקורה כשאין לו שורת טריגר — הן נקראות רק אחרי שכבר הגעת לשורה הנכונה. (נבדק מול הקלון של `amirbiron/CodeBot` ב-HEAD `94885d2`; בקוד הייצור היום אין אף הפרה — כל ה-`partialFilterExpression` הפעילים משתמשים בשוויון או ב-`$exists`.)

---

## דפוס 2 — סדר מפתחות באינדקס שאינו סדר השאילתה

**קודם מה שאינו נכון:** סדר השדות **בשאילתה** אינו צריך להתאים לסדר המפתחות באינדקס. המתכנן מתאים predicate למפתח בלי קשר לסדר הכתיבה, ומפתחות שוויון יכולים להופיע ביניהם בכל סדר.

מה שכן קובע הוא **ESR** — הכלל הרשמי לסדר המפתחות בהגדרת האינדקס: ‏**E**quality קודם, אחריו **S**ort, ובסוף **R**ange. התיעוד מנסח את זה כך: *"An index can have multiple equality keys. They can appear in any order relative to each other, but all equality keys must precede any sort or range fields"*, ו-*"An index supports sort operations on a subset of its keys only when the query includes equality conditions on all prefix keys that precede the sort keys"*. (מקור: https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/ — אומת מול התיעוד.) והחריג המתועד: כשה-range סלקטיבי במיוחד, ‏ERS עדיף.

אינדקס שסדרו מפר את ESR נבנה, תופס מקום, מאט כתיבות — ואינו משרת את השאילתה שלמענה נוצר, או משרת אותה בלי המיון.

- `user_file_version_desc` נוצר `(user_id, file_name, version)` בזמן שהשאילתות דורשות `(file_name, user_id, version)` — CodeBot PR #2517.
- אינדקס פולינג של תזכורות נוצר `(status, remind_at, needs_push)` בזמן שהשאילתה ממיינת לפי `remind_at`; ‏`remind_at` הועבר לראש — CodeBot PR #2627.

### כלל
לכל `create_index` — לכתוב בהערה את השאילתה שהוא משרת (`filter` + `sort`), לסדר את המפתחות לפי ESR, ו**לאמת ב-`explain`** שהשאילתה באמת בוחרת בו (`IXSCAN` ולא `COLLSCAN`, והאינדקס בשם). ‏`explain` הוא הקובע כאן, לא קריאת הסדר בעין. ובקוד שמנסה "לתקן" אינדקסים: **לא** `try/except: pass` סביב `drop_index` — מחיקה שנכשלת בשקט משאירה שני אינדקסים סותרים.

---

## דפוס 3 — מחרוזת ב-`$project` היא קבוע, לא שדה

```python
{"$project": {"file_name": "<value>"}}     # ❌ "החזר את הקבוע <value>"
{"$project": {"file_name": "$file_name"}}  # ✅ "החזר את השדה"
```

מחרוזת שאינה מתחילה ב-`$` בתוך היטלה היא **ערך קבוע**. הכשל שקט לגמרי: בניגוד ל-`$limit`, מחרוזת בהיטלה אינה גורמת למונגו לזרוק. נמדד מול MongoDB 8.0.32: ה-`queryShapeHash` שונה — **המנוע עצמו סופר את שתי הצורות כשתי שאילתות**, כלומר שלב שמושך את `code` נותח כשלב שאינו קורא שום שדה (CodeBot PR #3350).

**המשפחה הרחבה:** שאילתה שנשמרת, מנורמלת או עוברת סיבוב דרך JSON אינה בהכרח השאילתה שרצה. אותו ריפו, אותו דשבורד: תאריכים נשמרו כמחרוזות JSON (ל-JSON אין טיפוס תאריך), והתוצאה הייתה `explain` מהיר עם אפס סריקה ויעילות מושלמת — על שאילתה שתאמה **0 מסמכים** במקום 1,157. דוח שנראה מצוין ומסקנתו הפוכה, וזה גרוע מ-`<value>` כי `<value>` לפחות נראה שבור. התיקון: Extended JSON (`bson.json_util`) בשני הכיוונים (CodeBot PR #3346).

---

## דפוס 4 — `$setOnInsert` ו-`$set` על אותו שדה

```python
coll.update_one(flt, {"$setOnInsert": {"username": u}, "$set": {"username": u}}, upsert=True)
# ❌ Updating the path 'username' would create a conflict
```

מונגו זורקת והעדכון נכשל כולו (CodeBot PR #2182). שדה שצריך להיכתב רק ביצירה שייך ל-`$setOnInsert` בלבד; שדה שמתעדכן תמיד — ל-`$set` בלבד.

---

## דפוס 5 — השדות הכבדים נגררים דרך המיון (ו-`allowDiskUse` אינו התשובה)

הצינור שבונה "האחרון לכל מפתח" מרוויח מהסרת השדה הכבד **לפני** `$sort` ו-`$group` — **אבל רק כשהשלבים המאוחרים באמת לא צריכים אותו.**

```python
# ❌ code נגרר דרך המיון והקיבוץ
[{"$match": q}, {"$sort": {...}}, {"$group": {...}}, {"$project": {"code": 0}}]
# ✅
[{"$match": q}, {"$project": {"code": 0}}, {"$sort": {...}}, {"$group": {...}}]
```

**התנאי אינו קישוט:** אם ה-`$group` משתמש בשדה — ‏`$first: "$$ROOT"`, ‏`$push`, ‏`$addToSet`, או כל accumulator שנוגע בו — ההסרה המוקדמת **משנה את התוצאה**, וזה באג ולא אופטימיזציה. הכלל חל על צינור שבו השדה אינו נקרא אחרי שלב ההסרה, ואת זה בודקים בקריאת הצינור, לא בהנחה.

**ועל שגיאה 292 — `QueryExceededMemoryLimitNoDiskUseAllowed` — מה שנכון ומה שלא:** ‏`allowDiskUse: true` **כן** מתיר ל-`$sort` ול-`$group` לכתוב קבצים זמניים ולחרוג מ-100MB; זו בדיוק מטרתו (https://www.mongodb.com/docs/manual/core/aggregation-pipeline-limits/). מה שנכון בצמצום: **אשכולות Atlas Free ו-Flex אינם תומכים בכתיבת קבצים זמניים כלל** — *"Atlas ignores the `allowDiskUse` option and the corresponding commands behave as if the `allowDiskUse` option is set to `false`"* (https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/), ובאשכול Free גם מגבלת המיון בזיכרון היא 32MB ולא 100. כלומר ב-CodeBot הדגל הועבר ולא עזר **מפני שהאשכול שם אינו תומך בו**, ולא מפני ש-`allowDiskUse` אינו עובד ב-Atlas.

המסקנה המעשית זהה בשני המקרים ובאה מכיוון אחר: הנפילה למסלול החלופי (`find` + `skip` במנות) עלתה יותר מהבעיה — `/files` לקח 3.1–3.4 שניות בטעינה רגילה (CodeBot PR #3336) — ולכן מתקנים את הצינור. ‏**ואין להסיר את הדגל** באשכול שכן תומך בו: שם הוא רשת הביטחון.

ראה `RECURRING-PATTERNS.md` R8 לשאר המשפחה — N+1, בנייה לפני בדיקה, וסריאלייזר עם denylist.

---

## דפוס 6 — בדיקת אמת בוליאנית על `Collection` / `Database`

```python
if collection:          # ❌ NotImplementedError
if not default_db:      # ❌ NotImplementedError
if collection is not None:   # ✅
```

pymongo **זורק בכוונה**, כדי למנוע את הבלבול בין "האובייקט קיים" ל"האוסף אינו ריק". ב-CodeBot שמירת סקילים נכשלה בגלל זה (PR #3199), ובמופע מוקדם הבוט עשה `sys.exit(1)` על מסד תקין לחלוטין (`4e20f7b5`). אותו כלל חל על `Cursor` ועל תוצאות אגרגציה: להשוות ל-`None` במפורש.

---

## דפוס 7 — אופרטורים על בייטים מול אופרטורים על תווים

`$substrBytes` / `$strLenBytes` / `$indexOfBytes` מודדים בבייטים; ‏`$regexFind ← idx` מחזיר **תווים**. בעברית אלה שני מספרים שונים, והחיתוך נוחת באמצע תו ומפיל את כל האגרגציה.

הכלל המלא, עם הטבלה המדודה ושתי הודעות השגיאה: `BY-STACK/hebrew-source.md` **H6**.

---

## דפוס 8 — אתחול עצל של החיבור, ואינדקסים בתוך הנעילה

`get_db()` שמפרסם את השומר לפני הערך הוא **K15** — הכלל המלא ב-`CRITICAL-PATTERNS.md`, והוא נולד בדיוק בקובץ הזה.

ובן-משפחה שלו מאותו ריפו: `get_db` קרא ל-`ensure_recent_opens_indexes()` ול-`ensure_code_snippets_indexes()` **בתוך הנעילה שהוא מחזיק**, והן קוראות ל-`get_db` בעצמן — קריאה re-entrant בזמן האתחול, שהופיעה כתקיעה (CodeBot PR #1003). יצירת אינדקסים היא צרכן של החיבור, לא חלק מהקמתו.

---

## הפניות צולבות

- **`CRITICAL-PATTERNS.md` K15** — שומר שמתפרסם לפני הערך
- **`RECURRING-PATTERNS.md` R8** — עבודה ומטען שאינם פרופורציונליים
- **`BY-STACK/hebrew-source.md` H6** — בייטים מול תווים
- **`BY-STACK/postgres.md`** — המקבילה ב-SQL; דפוס 4 שם (tiebreaker) חל כאן מילה במילה
- **`bugbot-rules/mongo-index-and-operator-traps.md`**
- **`docs/source-projects/codebot-history-scan-patterns.md` P15**
