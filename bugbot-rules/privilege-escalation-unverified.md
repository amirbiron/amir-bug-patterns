# privilege-escalation-unverified

**CRITICAL — הסלמת הרשאות דרך attributes לא מאומתים**

זהה הענקת תפקיד / הרשאה שתלויה ב-attribute שמסופק על ידי המשתמש (email, claim) בלי לוודא שהמשתמש באמת בעל ה-attribute.

## דווח כשמתקיימים כל הבאים

1. הקוד מעניק תפקיד / הרשאה מוגברת (`admin`, `staff`, `owner`, `super_user`, תפקיד מותאם בהרשאה גבוהה).
2. החלטת ההענקה מבוססת על ערך שסופק על ידי המשתמש בזמן registration / login / link:
   - `request.body.email == OWNER_EMAIL` (או כל השוואת allowlist).
   - claim מ-JWT לא מאומת.
   - ערך header (`X-User-Role`).
   - ערך משדה profile שמוצהר עצמית.
3. ההענקה קורית *לפני* אחד מ:
   - email verification (token נשלח ב-mail, `email_verified_at` מסומן).
   - פעולה out-of-band על ידי admin קיים (invite token).
   - הוכחת בעלות על זהות OAuth (token מ-IdP).

## דפוס נדרש

הענקות תפקיד מוגבר חייבות להיות gated על ידי verification מפורש:

```python
if user.email_verified_at is None:
  raise NotVerified()
if request.body.email == settings.OWNER_EMAIL:
  user.role = "owner"
```

או דרך invite tokens שהונפקו על ידי admins קיימים:

```python
invite = await get_invite_by_token(request.body.token)
if invite and invite.role == "admin" and invite.email == request.body.email:
  user.role = "admin"
  await invite.consume()
```

## False positives

- תצוגת תפקיד read-only (הצגת UI של "אתה admin" כשהתפקיד כבר אמין).
- test fixtures / נתוני seed.

## חומרה

CRITICAL — תוקף שיודע את ה-email של admin יוצר חשבון, לעולם לא מאמת, מקבל תפקיד admin.
