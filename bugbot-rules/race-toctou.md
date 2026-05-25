# race-toctou

זהה דפוסי Time-Of-Check-Time-Of-Use בקוד concurrent / async שמסכנים בכפילויות, state ישן, או עדכונים שמתפספסים.

## דווח כשמתקיים אחד מהבאים

1. קריאה של עמודת status / state של שורה (`SELECT`, ORM `.get()`, `.scalar()`), ולאחריה הסתעפות מותנית, ולאחר מכן `UPDATE` או קריאה חיצונית על אותה שורה — בלי סעיף `WHERE` שמתייחס לערך שנקרא (אין CAS), בלי `SELECT FOR UPDATE`, ובלי constraint של `UNIQUE` / `ON CONFLICT`.

2. פונקציית `async def` שנקראת בלי `await` ומשמשת בהקשר בוליאני (`if foo():`) — coroutines הם truthy, אז הבדיקה תמיד עוברת.

3. בדיקת precondition / תקפות שרצה לפני ה-lock שאמור להגן על המשאב.

4. `commit()` / כתיבת DB שרצה אחרי קריאה חיצונית בלתי הפיכה (HTTP POST, שליחת email/SMS, payment API) — בלי שורת UNIQUE שמוכנסת כ-"רזרבציה" לפני הקריאה החיצונית.

5. עדכון CAS / cursor שמשווה עמודה nullable עם `=` (ב-Postgres: `col = NULL` מוערך כ-NULL, לא TRUE — חייב להשתמש בהסתעפות `IS NULL`).

## False positives

- script של תהליך יחיד, single-threaded, בלי runners concurrent.
- הקריאה מתבצעת בתוך `SELECT FOR UPDATE`.
- הכתיבה משתמשת ב-`INSERT ... ON CONFLICT DO NOTHING` / `ON CONFLICT DO UPDATE`.
- קריאה חיצונית read-only (status fetch, analytics fire-and-forget).
- טסטים עם mocks.

## חומרה

HIGH — side effects כפולים, השפעה פיננסית / compliance, לולאות אינסופיות.
