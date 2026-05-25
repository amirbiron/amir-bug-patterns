# like-wildcard-injection

**CRITICAL — מניפולציה של SQL query / חשיפת נתונים**

זהה סעיפי `LIKE` שנבנים מקלט שסופק על ידי המשתמש בלי escape לתווי ה-wildcard `_` ו-`%`. קלט שסופק על ידי המשתמש יכול להתאים ליותר שורות מהמיועד (דליפת נתונים) או לכל השורות (`%`).

## דווח כשמתקיימים כל הבאים

1. סעיף SQL `LIKE` (או `ILIKE`, `NOT LIKE`) שבו ה-pattern נבנה מערך שסופק על ידי המשתמש.
2. ערך המשתמש משורשר / מוזרק ישירות:
   - `f"{user_prefix}%"` / `f"%{user_input}%"`
   - `:param || '%'` / `'%' || :param || '%'`
   - `.like(`f"...{value}..."`)` ב-SQLAlchemy
3. הקלט אינו מצוין escape (`_` → `\_`, `%` → `\%`, backslash → `\\`) וה-query לא כולל `ESCAPE '\\'`.

## דפוסי תיקון

- **SQLAlchemy:** השתמש ב-`column.startswith(value, autoescape=True)` / `.endswith(...)` / `.contains(...)` — אלה עושים escape אוטומטית.
- **Raw SQL:** escape והכרזה:
  ```python
  esc = value.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
  q = "SELECT ... WHERE col LIKE :p ESCAPE '\\\\'"
  conn.execute(q, {"p": f"{esc}%"})
  ```
- **או השתמש ב-`=`** אם חיפוש prefix לא באמת נדרש (לרוב זו התשובה).

## False positives

- patterns קשיחים (בלי קלט משתמש).
- כלי admin פנימיים שבהם רק operators אמינים מספקים קלט — עדיין מסוכן.

## חומרה

CRITICAL — `prefix="%"` בוחר את כל השורות; `prefix="user_id_"` מתאים ל-`user_idXfoo` וכו' — דולף נתונים שהמשתמש לא צריך לראות.
