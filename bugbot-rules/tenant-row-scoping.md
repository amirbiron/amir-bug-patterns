# tenant-row-scoping

זהה שאילתות בטבלאות רב-דייריות שחסרות סינון לפי ה-tenant הנוכחי, ו-context של tenant שנופל בשקט לברירת מחדל. הדליפה שקטה לגמרי: אין חריגה, אין לוג — רק תשובה "תקינה" עם נתונים של לקוח אחר.

## דווח כשמתקיים אחד מהבאים

1. **שאילתה בלי tenant scope.** `SELECT` / `UPDATE` / `DELETE` על טבלה שיש בה עמודת `tenant_id` / `account_id` / `org_id`, בלי predicate על ה-tenant המאומת. ול-**INSERT / UPSERT** חוזה משלו: ה-`tenant_id` הנכתב נגזר מה-context המאומת — ערך שמגיע מגוף הבקשה של הלקוח הוא דגל; וב-UPSERT מפתח ה-conflict כולל את ה-tenant, אחרת דייר דורס שורה של דייר אחר.

2. **get-by-id בלי scope.** `WHERE id = :id` כשה-id מגיע מהלקוח, בלי `AND tenant_id = :current` — מי שמונה ids קורא שורות של דיירים אחרים (IDOR).

3. **נתיב משני שנשכח.** ה-list הראשי מסונן, אבל export / חיפוש / aggregation / webhook handler / משימת רקע — לא. הבידוד חזק בדיוק כמו השאילתה הכי חלשה; דגל כל נתיב חדש שניגש לטבלה רב-דיירית בלי לעבור דרך שכבת ה-scoping.

4. **Context של tenant עם fallback שקט.** `ContextVar("tenant", default=None)` או `default=DEFAULT_TENANT`, כשקוד במורד משתמש בערך בלי לבדוק — נתיב ששכח לקבוע context רץ על הדייר הלא נכון במקום להיכשל. דרוש fail-closed: בלי default, ונתיב בלי context זורק. דגל `TENANCY_STRICT` (או שווה ערך) שכבוי בפרודקשן — דגל אדום בפני עצמו.

5. **מפתח cache / session בלי tenant.** `cache.get(f"leads:{page}")` במערכת רב-דיירית — ה-cache מגיש נתוני דייר אחד לאחר. כל מפתח של cache, session, וקובץ זמני כולל את ה-tenant.

6. **אין בדיקת בידוד.** פיצ'ר רב-דיירי חדש בלי טסט של שני tenants שמאמת ששום תשובה לא מכילה נתונים של השני. הבדיקה חייבת ליפול כשה-scoping מוסר (T2).

## False positives

- טבלאות גלובליות באמת (קונפיג מערכת, קטלוג ציבורי משותף) — כשהן מסומנות ככאלה במפורש.
- נתיבי admin מוצהרים שסורקים את כל הדיירים בכוונה, עם אימות admin ו-audit log.
- מערכת חד-דיירית באמת — אין עמודת tenant, אין מה לדגל.

## חומרה

CRITICAL — דליפת נתונים בין לקוחות היא אירוע אבטחה מהדליפה הראשונה. אין warning-period לדפוס הזה.

## ראיות

EmailFlow: 3 מופעי auth/tenant isolation ב-HIGH (נספח "מחוץ ל-Top 7" של מסמך המקור). הקשר חי: ai-business-bot — ContextVar עם `default=None` בסטייה מה-spec, כך שבלי `TENANCY_STRICT` נתיב ששוכח context נופל בשקט ל-default.
