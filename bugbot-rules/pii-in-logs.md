# pii-in-logs

**CRITICAL — פרטיות / GDPR / compliance**

זהה מידע אישי-מזהה (PII), סודות, או חשיפת לוגיקה פנימית בקריאות `logger.*`, פרטי exception שמוחזרים ללקוחות, ו-bodies של תגובות API.

## דווח כשמתקיים אחד מהבאים

### אסור בקריאות `logger.*` (כל רמה) וגם בכל response של API

- שמות שדות: `email`, `phone`, `mobile`, `from_email`, `to_email`, `address`, `street`, `city`, `zip`, `postal_code`.
- שדות שם אישי: `name`, `full_name`, `first_name`, `last_name`, `contact_name`, `display_name`, `external_contact_id`.
- תוכן body של email / chat / messages (יכול להכיל כל דבר).
- סודות: `password`, `passwordHash`, `password_hash`, `salt`, `refresh_token`, `access_token`, `api_key`, `secret`, `private_key`, JWT bearer tokens.

### אסור ב-response של API בלבד (logs בסדר אם גישה ללוגים נשלטת)

- סיבות heuristic להחלטה (`"esp:mailchimp.com"`, `"spam_score=0.8"`, שמות חוקים פנימיים).
- UUIDs / IDs פנימיים של DB של tenants / users *אחרים* (`courier_id`, `worker_id` שלא בבעלות המבקש).
- Stack traces, שמות מחלקות exception, הודעות framework (`Exception: <details>`).
- שברי SQL, מחרוזות query, נתיבי route פנימיים.

### החלפות מותרות

- PII → רק *domain* של email (`example.com`), או own-user_id (ערך שלמבקש כבר יש), או hash לא הפיך.
- לוגיקה פנימית → הודעת שגיאה מתורגמת גנרית ("Service unavailable, please try again").
- IDs פנימיים → רק IDs של משאבים שהמבקש הוא הבעלים שלהם.

## התאמות דפוס

- `logger.<level>("... %s ...", x)` כש-`x` הוא משתנה ששמו דומה לרשימה האסורה.
- `HTTPException(detail=str(exc))` או `detail=f"... {internal_var} ..."`.
- `raise X from exc` בגבולות API בלי `detail` בטוח מפורש.
- החזרת שורות ORM ישירות ללקוחות (במקום דרך DTO / response model).

## False positives

- נתיבי `logger.debug` שאומתו כמוחרגים מאיגוד logs בפרודקשן.
- שירותים פנימיים בלבד (כלי admin / scripts) — הכלל מחמיר מדי אבל שווה ניקיון רבעוני.
- מזהים גנריים שאינם PII (own user_id, request_id, trace_id).

## חומרה

CRITICAL — פריצת פרטיות, חשיפה אפשרית ל-GDPR / רגולציה.
