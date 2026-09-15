# filter-too-narrow

זהה ביטויי filter (`WHERE`, regex, `Array.filter`) שמוציאים מקרים לגיטימיים או שמופעלים בסדר שגוי — מייצרים רשימות UI ריקות, emails חסומים, או security-bypass דרך override.

## דווח כשמתקיים אחד מהבאים

1. **Filter על channel/source/type יחיד** כשהישות מתועדת כבעלת מספר variants. דוגמה: `WHERE channel = 'whatsapp'` ברשימת UI שצריכה להציג גם ישויות שמעדיפות email.

2. **Domain blacklist עם exact match** (`host == "mailchimp.com"`) במקום suffix match (`host.endswith(".mailchimp.com") or host == "mailchimp.com"`).

3. **Regex על email / URL / phone** בלי טיפול ב-display-name (`"Alice <alice@example.com>"`), subdomain, או variants של פורמט בינלאומי.

4. **סדר filter: override של business לפני בדיקת security/deny.** דוגמה:
   ```python
   if message.contains(FORCE_SEND_KEYWORD):
     send(lead, message); return
   if blocked_publishers.contains(lead.publisher_id):
     return  # לעולם לא מגיע ל-force_send
   ```
   Filters של security / deny / block חייבים לרוץ **קודם**.

5. **`Array.filter` ולאחריו UI של `.length === 0`** כש-predicate ה-filter לא מכסה את כל variants הישות הצפויות → המשתמש רואה רשימה ריקה בטעות.

6. **Filter שמסתמך על truthy של nullable boolean** במקום השוואה מפורשת. דוגמה: `if closed:` במקום `if closed is True` כש-`closed` יכול להיות `None` / `False` / `True`. ב-Python, `None` ו-`False` שניהם falsy, אבל הסמנטיקה לרוב דורשת הבחנה — `None` = "לא נקבע" (אקטיבי כברירת מחדל היסטורית), `False` = "סגור במפורש שלילי", `True` = "סגור". הכשל הקלאסי: filter שאמור להוציא רק לידים סגורים (`closed is True`) משאיר לידים עם `closed=None` ברשימת האקטיביים — או הפוך, תופס לידים עם `None` כאילו הם סגורים. דווח על `if <bool_col>:` / `if not <bool_col>:` / `.filter(model.col)` כש-העמודה nullable, בלי `is True` / `is False` / `is None` או `!= True` מפורש. שווה ערך ב-SQL: `WHERE col` במקום `WHERE col IS TRUE`.

7. **ברירת מחדל שנקבעת לפי הקריטריון הלא נכון.** שלושה אופרטורים
   שנראים חליפיים ואינם, וכל אחד בודק שאלה אחרת:

   | | מתי הוא משים ערך |
   |---|---|
   | `dict.setdefault(k, v)` | רק כשהמפתח **חסר**. קיים עם `None` או `""` — לא נוגע |
   | `x ||= v` (JS) | על כל ערך **falsy**: `""`, `0`, `false`, `null`, `undefined`, `NaN` |
   | `x ??= v` (JS) | רק על `null` או `undefined`. `0` ו-`""` נשארים |

   הכשל: `doc.setdefault("story_id", doc.get("id") or uuid4().hex)` משאיר
   מזהה ריק בדיוק במקרה שבשבילו הוא נכתב, כי `""` הוא מפתח קיים. והכשל
   ההפוך, מסוכן לא פחות: `||=` על מזהה שבו `0` **חוקי** דורס אותו.

   הצורה הנכונה נגזרת מחוזה השדה, ולא מהאופרטור שנוח: אם רק היעדר ערך
   מצדיק ברירת מחדל — `if "k" not in doc`; אם גם `None` ו-`""` —
   **בדיקה מפורשת של שני אלה**, `if doc.get("k") in (None, "")`, ולא
   `if not doc.get("k")`. ‏**הבדיקה הרחבה היא בדיוק הבאג מהצד השני**: היא
   בולעת גם `0`, ‏`False`, ‏`[]` ו-`{}` — ערכים שברוב הסכימות חוקיים לגמרי,
   ואז ברירת המחדל דורסת נתון אמיתי. זה אח
   של סעיף 6: שם ההבחנה בין `None` ל-`False`, כאן בין "חסר", "ריק"
   ו-"falsy". ובאותה הזדמנות — המרת טיפוס מפורשת, כי מזהה שנשמר כמספר
   לא יימצא בשאילתה שמחפשת מחרוזת.

## False positives

- צמצום scope מכוון (owner-scoped, role-scoped, tenant-scoped) כש-ה-filter *הוא* הפיצ'ר.
- filters debug-only / admin-only כשה-scope הצר מכוון.
- test fixtures.

## חומרה

MEDIUM — UI ריק / פעולות חסומות (שובר UX); HIGH אם סדר filter גורם ל-security bypass.
