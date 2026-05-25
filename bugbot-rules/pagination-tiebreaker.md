# pagination-tiebreaker

זהה סעיפי `ORDER BY` שחסר להם tiebreaker משני, מה שמוביל לסדר שורות לא דטרמיניסטי על ties. ב-queries מדפדפים (LIMIT/OFFSET או cursor), זה גורם לשורות להיות כפולות או להידלג בין דפים.

## דווח כשמתקיימים כל הבאים

1. query של SQL או ORM משתמש ב-`ORDER BY` (או `.order_by()`) עם **רק expression אחת** (בדרך כלל timestamp כמו `created_at`, `updated_at`, או שדה score / rank).
2. ה-query נמצא אחרי `LIMIT` / `OFFSET`, או בשימוש בדפדוף מבוסס-cursor, או בשימוש ב-query של CAS עם סמנטיקת "latest".
3. עמודת ה-ordering אינה constraint של `UNIQUE` (timestamps יכולים להיות שווים, scores יכולים להיות שווים).

## תיקון

הוסף את המפתח הראשי כ-expression משנית:
```python
.order_by(Model.created_at.desc(), Model.id.desc())
```

ל-queries של CAS עם סמנטיקת "latest", ה-selector וה-verifier חייבים להשתמש באותו tuple של multi-expression.

## False positives

- queries בלי `LIMIT` / `OFFSET` (סט תוצאות מלא, סדר על ties פחות קריטי).
- אגרגציות (`GROUP BY` + `SUM`) — `ORDER BY` על אגרגט לא צריך tiebreaker של PK.
- queries של שורה יחידה (`.first()`, `.scalar_one_or_none()`) שבהן עמודת ה-ordering היא `UNIQUE`.

## חומרה

MEDIUM — דפדוף מציג שורות כפולות בדף אחד וחסרות בבא; משתמשים רואים רשימות "זזות".
