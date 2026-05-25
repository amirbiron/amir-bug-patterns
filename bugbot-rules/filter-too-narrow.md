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

## False positives

- צמצום scope מכוון (owner-scoped, role-scoped, tenant-scoped) כש-ה-filter *הוא* הפיצ'ר.
- filters debug-only / admin-only כשה-scope הצר מכוון.
- test fixtures.

## חומרה

MEDIUM — UI ריק / פעולות חסומות (שובר UX); HIGH אם סדר filter גורם ל-security bypass.
