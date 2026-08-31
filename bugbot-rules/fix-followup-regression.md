# fix-followup-regression

תיקון שיוצר את הבאג הבא. הבדיקה שנוספה עם ה-fix עוברת — אבל ה-fix נגע ב-helper משותף, וב-flow אחר שמשתמש באותו helper הוא שבר משהו שלא נבדק. אחרי כמה סבבים: 45 commits של "fix the fix" באותו ריפו, כל אחד תוקן כתגובה לריגרסיה שנוצרה מהקודם.

מובחן מ-`test-mirrors-spec-not-client.md` (T1): שם הבדיקה עוקבת אחרי המפרט ולא אחרי הלקוח. כאן הבדיקה עוקבת אחרי **הבאג הספציפי שתוקן**, אבל לא אחרי ה-**flows** שה-fix ריץ בהם.

מובחן מ-T2 (`prove test fails on old code`): T2 מוודא שהבדיקה יכולה ליפול. כאן הבדיקה נופלת בסדר — היא פשוט לא בודקת את מה שנשבר.

## דווח כשמתקיים אחד מהבאים

1. **commit של fix שנוגע ב-helper משותף** (פונקציה שנקראת מ-3+ callers, class base, decorator) עם test חדש שקורא רק ל-caller אחד. דגל אדום מיוחד: הפונקציה שהשתנתה מיוצאת מ-`utils/`, `common/`, `_base.py`.

2. **fix ב-signature של פונקציה פנימית** — הוספה/הסרה/שינוי טיפוס של פרמטר, שינוי ערך החזרה — כשה-mocks בטסטים משתמשים ב-`*args, **kwargs` שסופגים את השינוי בשקט. הבדיקה של ה-fix עוברת; הקריאה האמיתית מקריאה שנייה בפרודקשן משתגעת.

3. **תיקון ב-cast / normalization / parsing שהוחל על נתיב input אחד**. למשל: `bool ⊂ int` תוקן ב-Pelecard IPN status, אבל `count=True` ב-lead counter נשאר. הריגרסיה של ה-fix הראשון לא סימנה את השני.

4. **fix-of-fix pattern.** ה-commit האחרון על אותו קובץ (או אותה פונקציה) הוא כבר "fix" בעצמו, פחות מ-14 יום קודם. שני fixes רצופים באותו איזור = ריגרסיה של הראשון בסבירות גבוהה.

5. **PR body שלא מציין אילו sibling flows נבדקו.** אין רשימה של "אימתי גם ש-`bar`, `baz`, `qux` עדיין עובדים אחרי השינוי" — סימן שלא נבדקו.

## תבנית תיקון

- **integration test על כל ה-callers.** כשמתקנים helper משותף, ה-PR חייב להריץ בדיקות שקוראות ל-**כל** ה-callers, לא רק ל-caller של הבאג. פרמטריזציה על callers = הכי זול.
- **ban `*args, **kwargs` ב-mocks של פונקציות פנימיות.** ה-mock משכפל את ה-signature האמיתית; שינוי signature שובר את ה-mock, וזה בדיוק מה שרוצים.
- **PR checklist שנוגעת ל-shared helpers:** רשימה של call-sites שהריצו אותם ב-test suite אחרי ה-fix.
- **git blame על ה-file/function לפני ה-fix.** אם ה-commit האחרון היה fix — לסקור אותו קודם; יש סיכוי גבוה שאתה עומד ליצור את ה-fix-of-fix הבא.

## False positives

- Trivial refactors (rename, extract variable) — אין תיקון של באג, אין ריגרסיה בהגדרה.
- Hotfix מוצהר לפרודקשן שדחוף מ-integration test — התיעוד ב-PR body ("hotfix, follow-up test in issue #N") מכשיר את הפער זמנית.
- Multi-commit branch שבו הבדיקה המקיפה חיה ב-commit נפרד באותו PR.

## חומרה

MEDIUM (per instance) — אבל **תדירות המצטברת** של הדפוס היא הסיכון האמיתי: 45 fix-of-fix commits ב-Campaign AI פירושו שרבע מזמן ה-QA מוקדש לתיקון ריגרסיות של תיקונים. ל-users זה נראה כאילו הבאג "לא נסגר".

## ראיות

Campaign AI Meta-pattern C (`docs/source-projects/campaign-ai-patterns.md`, 2026-08-31): 45 fix-of-fix commits מזוהים באופן מפורש. דוגמאות מרכזיות: `92fba3a` (fix ל-`meta_ad_ids` שגרר fix ב-`replace_campaign_meta_ad_ids`), `67366bc` (fix ל-`awaiting_offer` דרס routing → הופרד לשני דגלים), `60ee35b` (fix ל-`AsyncOpenAI` timeout שיצר dead-code בסדר seams), `c6ac04f` (fix ל-`revise` דרס `publish` button), `56eb671` (fix ל-`_sign_asset` דרש שינוי ב-`CreativeAsset`), `98baba9` (fix ל-`.or_()` שדרש CREATE INDEX חדש), `5c34a50` (fix לבדיקת rowcount שהתגלגל ל-4 endpoints).
