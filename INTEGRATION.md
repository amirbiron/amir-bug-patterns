# INTEGRATION — איך הידע מהריפו הזה מגיע לסשנים בזמן אמת

הספרייה הזו שווה בדיוק כמה שהיא נקראת **בזמן המימוש**. המסמך הזה מגדיר
שלושה מנגנונים שמחברים אותה לעבודה השוטפת, ותהליך אחד שמונע ממנה להתיישן.

**עקרון החלוקה:** `CLAUDE.md` של פרויקט מכיל *טריגרים* — מתי לקרוא ומה.
הריפו הזה מכיל את *הידע* — למה, איך מזהים, ומה false positive. לא מעתיקים
את הידע לפרויקטים (הוא מתיישן שם); מעתיקים רק את ההפניה.

---

## 1. בלוק הטריגרים ל-CLAUDE.md (לכל פרויקט פעיל)

מדביקים ב-`CLAUDE.md` של הפרויקט את התבנית שלמטה, ואת שורות הטבלה שבתוכה
ממלאים מ-**§2** לפי ה-stack של הפרויקט. שני החלקים יחד הם הבלוק — התבנית
לבדה חסרה את הטריגרים, והשורות לבדן חסרות את הוראת הקריאה.

דרכי קריאה, לפי מה שזמין בסשן: mirror של הריפו הזה ב-CodeKeeper
(`codekeeper_search_repo` / `codekeeper_get_repo_file`), או ישירות
מ-GitHub (`amirbiron/amir-bug-patterns` הוא ריפו ציבורי).

### תבנית הבלוק

```markdown
## דפוסי באגים — amir-bug-patterns

לפני שאתה נוגע באחד מהנושאים בטבלה — קרא את הקובץ המתאים
ב-`amirbiron/amir-bug-patterns` (דרך MCP של CodeKeeper אם יש mirror,
אחרת מ-GitHub). אלה דפוסים שכבר עלו לי בפרודקשן — לא תיאוריה.

| כשאתה נוגע ב... | קרא |
|---|---|
| <נושא> | <קובץ> |
<!-- מלא את השורה הזו משורות הנתונים של הפרויקט שלך ב-§2, ומחק הערה זו. -->

תמיד, בכל פרויקט:
- לפני עטיפת קריאה ב-try/except → `CRITICAL-PATTERNS.md` K11 (כשל בערך החזרה)
- לפני כתיבת טסט חדש → `claude-md-snippets/testing.md`
- אחרי שטסט נופל על חריגה → `bugbot-rules/widened-exception-scope.md` (אל תרחיב except)

### סגירת הלולאה (חובה, לא רשות)
1. **ריוויוור (cubic/qodo/CodeRabbit/claude) תפס דפוס אמיתי** שאינו
   ב-amir-bug-patterns → פתח שם PR שמוסיף אותו (מסמך מקור + הצלבה לפי
   ה-README), **וגם** הוסף שורת טריגר לטבלה כאן.
2. **אתה בעצמך זיהית דפוס חוזר אצלך** (תיקנת פעמיים את אותו סוג טעות) →
   אותו תהליך בדיוק.
3. דפוס בלי שורת טריגר = דפוס שלא ייקרא. שני הצעדים הם צעד אחד.
```

### למה זה עובד
- `CLAUDE.md` נקרא בכל סשן ממילא — אין תלות בזיכרון של אף אחד.
- הטבלה קצרה (שורות בודדות) — לא מנפחת את הקובץ.
- הידע נשאר במקום אחד ומתעדכן במקום אחד.

---

## 2. מיפוי פר-פרויקט — מה ממלא את הטבלה שב-§1

> ⚠️ **מה שלמטה הוא רק שורות הטבלה, לא הבלוק להדבקה.**
> הטבלאות כאן נראות שלמות (יש להן כותרת ושורת מפריד) — אבל הן רק החלק
> שמשתנה בין פרויקטים. אם תדביק רק אותן, סוכן יראה `CRITICAL-PATTERNS.md`
> ולא יידע שזה ריפו אחר, ולא יקבל את הכללים הקבועים ולא את סגירת הלולאה.

**איך מרכיבים, בשני צעדים:**

1. קח את **התבנית המלאה מ-§1** — היא נותנת את המעטפת: הוראת הקריאה
   (מאיפה מביאים את הקבצים), שלושת הכללים שחלים תמיד, וסגירת הלולאה.
2. החלף בה את שורת ה-placeholder `| <נושא> | <קובץ> |` בשורות של הפרויקט
   שלך מהרשימה כאן — **רק שורות הנתונים**. אל תעתיק את שורת הכותרת
   (`| כשאתה נוגע ב... | קרא |`) ואת שורת המפריד (`|---|---|`): הן כבר
   קיימות בתבנית, והעתקה שלהן תיצור כותרת כפולה באמצע הטבלה.

**דוגמה חיה, כבר מודבקת בפועל:** הסעיף *"דפוסי באגים — amir-bug-patterns"*
בסוף [`CLAUDE.md` של CodeBot](https://github.com/amirbiron/CodeBot/blob/main/CLAUDE.md).
שם רואים את התוצאה המורכבת — כולל התאמות מקומיות שהתבנית לא מכתיבה
(שורת "מתי להשתמש" בסגנון הריפו, וכלל K11 שנפרס בגוף הטקסט כי הוא זה
שכבר עלה שם שלוש פעמים). התבנית היא בסיס, לא חוזה נוקשה.

השורות עצמן, לפי ה-stack של כל פרויקט:

### CodeBot (בוט טלגרם + webapp + MongoDB/GridFS + Sphinx docs)

| כשאתה נוגע ב... | קרא |
|---|---|
| שמירה/מחיקה שמסתיימת בהודעת ✅ למשתמש | `CRITICAL-PATTERNS.md` K11 |
| קאש / invalidation | `bugbot-rules/return-value-failure-unchecked.md` §4 |
| callbacks / handlers מקביליים, מזהים מבוססי-זמן | `CORE-PATTERNS.md` U1 |
| PyGithub / קריאות SDK חיצוני | `BY-STACK/external-sdk.md` |
| `docs/**/*.rst` | `bugbot-rules/line-number-coupling.md` |
| טסטים עם סטאבים ידניים | `TESTING-PATTERNS.md` + `bugbot-rules/widened-exception-scope.md` |

### ai-business-bot (Flask + SQLite WAL + OpenAI/Gemini + Twilio/Meta + multi-tenant)

| כשאתה נוגע ב... | קרא |
|---|---|
| webhook handlers (Twilio/Meta/Telegram) | `BY-STACK/webhooks.md` |
| קריאות OpenAI/Gemini/Graph API | `BY-STACK/external-sdk.md` |
| jobs מתוזמנים (תזכורות, purge תיקון 13) | `BY-STACK/cron-jobs.md` |
| לוגים בנתיב שיחות לקוח | `bugbot-rules/pii-in-logs.md` (CRITICAL — שיחות = PII) |
| בידוד tenant / ContextVar | `CORE-PATTERNS.md` U1 + U5 |
| שליחת הודעה + עדכון סטטוס | `claude-md-snippets/universal.md` §5 (linked-field atomicity) |

### Campaign AI (FastAPI + Supabase/Postgres + Meta Marketing API + סליקה)

| כשאתה נוגע ב... | קרא |
|---|---|
| migrations / שאילתות / pagination | `BY-STACK/postgres.md` |
| webhook Upay→Summit, חיוב פר-קמפיין | `BY-STACK/webhooks.md` + `CORE-PATTERNS.md` U1 (כסף = strict) |
| Meta Marketing API / OpenAI | `BY-STACK/external-sdk.md` |
| endpoints של auth / roles | `claude-md-snippets/critical.md` (K1, K3, K10) |
| סטטוסים של קמפיין/חיוב | `BY-STACK/state-machine.md` |

### CodeKeeper (WebApp + בוט + MongoDB + MCP)

| כשאתה נוגע ב... | קרא |
|---|---|
| כלי MCP שכותבים (save/edit/append) | `CRITICAL-PATTERNS.md` K11 — `save_file` שמחזיר `ok:true` בלי לעדכן הוא בדיוק הדפוס |
| Repo Sync Engine / mirrors | `CORE-PATTERNS.md` U1 |
| ChatOps / admin gating | `claude-md-snippets/critical.md` §5 (רשת) + fail-open flags |
| endpoints של ה-webapp | `BY-STACK/browser-policy.md` |

### Noa_Leads (FastAPI + Next.js + Supabase + Calendar/Gmail)
הפרויקט הוא מקור P1..P9 — רוב הדפוסים כבר נולדו כאן. הטריגרים:

| כשאתה נוגע ב... | קרא |
|---|---|
| React forms / dropdowns מסונכרני-backend | `BY-STACK/react-frontend.md` |
| sync tokens / webhooks של Calendar/Gmail | `BY-STACK/webhooks.md` + `CORE-PATTERNS.md` U1 |
| סטטוסים ו-activity log | `BY-STACK/state-machine.md` |
| SQLAlchemy async | `BY-STACK/async-orm.md` |

### פרויקטים קטנים (TaskFlow, myAgent, APIWatchBot...)
מספיק הבלוק האוניברסלי: K11 + testing + הכלל הרלוונטי היחיד לפי ה-stack
(myAgent: webhooks; TaskFlow: cron-jobs לתזכורות).

---

## 3. נוסח ל-Code Review Instructions של הבאגבוטים

להדבקה בממשק הווב של cubic / qodo / CodeRabbit (שדה custom instructions /
review guidelines). מנוסח תמציתי כי הוא מוזרק לכל ריוויו.

### הבלוק להדבקה

```text
בנוסף לבדיקות הרגילות, אכוף את הכללים האלה — כולם דפוסים שכבר גרמו
לבאגים אמיתיים בפרויקטים שלי (ריפו הרפרנס: github.com/amirbiron/amir-bug-patterns):

1. ערך החזרה ככשל: לכל קריאה עטופה ב-try/except או שאחריה דיווח הצלחה —
   ודא שהקורא בודק את הערך החוזר אם הפונקציה מחזירה None/False/0 בכשל
   במקום לזרוק. דגל אדום: `saved = True` קבוע אחרי קריאה, או הודעת ✅
   למשתמש בלי תנאי. (בפרט: save_backup_bytes, delete_pattern, rowcount.)

2. הרחבת except: כל דיף שמרחיב `except X` ל-`except Exception` או עוטף
   קוד קיים ב-try/except חדש — דרוש נימוק. אם באותו PR יש טסט שנופל בלי
   ההרחבה, השורש כנראה בסטאב/fixture של הטסט, לא בקוד.

3. race/TOCTOU: קריאה חיצונית בלתי-הפיכה (שליחה, תשלום, draft) לפני
   INSERT מקומי עם UNIQUE — דגל. מזהה ייחודי מבוסס-timestamp ברזולוציית
   שניות — דגל (התנגשות בכתיבות מקבילות).

4. טסטים: טסט חדש שנוסף עם תיקון חייב להיכשל בלי התיקון — אם ה-assert
   מתקיים גם בקוד הישן (למשל בודק תוצאה ריקה שנכונה בשני המקרים), דגל.
   הבדיקה עוברת דרך הממשק של הצרכן האמיתי, לא דרך המפרט.

5. הפניות שורה: `literalinclude` עם `:lines:` כשיש חלופת `:pyobject:` —
   דגל. הפניית file.py:123 בתיעוד ארוך-חיים — דגל.

6. אבטחה (strict תמיד): PII בלוגים (email/phone/message body), secrets
   ב-response, innerHTML בלי sanitizer, X-Forwarded-For להחלטות security,
   קרדנציאל שנשלח לפני שנשמר (fail closed).

עברית בהערות קוד היא המוסכמה בריפו — אל תדגל עליה.
```

### הערות
- **cubic** מוגבל באורך ההוראות — אם צריך לקצר, סעיפים 1, 2, 4 הם
  העדיפות (הדפוסים שחזרו בפועל); 6 מכוסה חלקית על ידי הסורקים שלו ממילא.
- **qodo** תומך ב-best practices file ברמת ריפו (`best_practices.md`) —
  אפשר במקום ההדבקה בממשק.
- כלל שמתווסף לריפו הזה → לעדכן גם את הבלוק הזה, אם הוא מספיק כללי.

---

## 4. תהליך פתיחת פרויקט חדש

צ'קליסט, בסדר הזה — כ-20 דקות סה"כ:

1. **CLAUDE.md ראשוני**: להדביק את שלושת הסניפטים האוניברסליים —
   `claude-md-snippets/universal.md`, `claude-md-snippets/critical.md`,
   `claude-md-snippets/testing.md` (~80 שורות). בפרויקט עברי: גם
   `claude-md-snippets/hebrew.md`.
2. **decision tree של ה-stack** (README §2): לכל "כן" — להדביק את
   ה-snippet המתאים ולרשום את קובץ ה-BY-STACK בטבלת הטריגרים.
3. **בלוק הטריגרים** (סעיף 1 כאן): להדביק את התבנית עם השורות של
   ה-stack + כללי סגירת הלולאה.
4. **באגבוטים**: לחבר את הריפו ל-cubic/qodo ולהדביק את הבלוק מסעיף 3.
5. **Day-1 defaults** (`MIGRATION-NOTES.md` §3): להחליט אסטרטגיית
   idempotency, convention ל-React state sync (אם רלוונטי), ו-guards
   לקלט חיצוני — ולרשום את ההחלטות ב-CLAUDE.md.
6. **mirror ב-CodeKeeper** לריפו החדש (אם הוא הולך להיות פעיל) — כדי
   שכלי ה-MCP יראו אותו.
7. **שורה ב-INTEGRATION.md** (הקובץ הזה): להוסיף את הפרויקט למיפוי
   בסעיף 2.

---

## 5. מה נשאר ידני בכוונה

- **אין הזרקה אוטומטית של דפוסים בכל סשן** (primer/hook גלובלי): סט
  הדפוסים רחב מדי להזרקה קבועה, והרלוונטיות תלוית-משימה. הטריגרים
  ב-CLAUDE.md הם הפשרה הנכונה — נטענים תמיד, שוקלים כמעט כלום, ומפנים
  לקריאה רק כשנוגעים בנושא.
- **אפשרות עתידית** אם הטריגרים לא יספיקו: PreToolUse hook פר-ריפו
  שמזהה עריכה בקובץ "רגיש" (למשל `*webhook*`, `*handler*`) ומדפיס
  תזכורת חד-פעמית לקרוא את הדפוס המתאים. לא ממומש — קודם רואים אם
  השכבה הפשוטה עובדת.
