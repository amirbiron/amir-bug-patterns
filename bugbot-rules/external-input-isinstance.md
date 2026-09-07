# external-input-isinstance

זהה type guards / shape guards חסרים בזמן ריצה על ערכים שמגיעים מחוץ לתהליך: תגובות API, payloads של webhook, output של AI/LLM, משתני סביבה, imports של CSV, MIME headers מנותחים.

## דווח כשמתקיים אחד מהבאים

1. `.get(key)` / `.append(...)` / `[key]` / iteration על ערך שמקורו ב-`response.json()`, `await request.json()`, `json.loads(...)`, `headers[...]`, או payload של webhook — בלי בדיקת `isinstance(obj, dict)` (או `list`) קודמת.

2. `.strip() / .lower() / .split()` / `+ str` על ערך שעלול לא להיות מחרוזת — בלי הגנת `isinstance(value, str)`.

3. השוואה מספרית או חשבון על מספר חיצוני בלי `math.isfinite(n)` (או JS `Number.isFinite(n)`) — `NaN < anything` הוא `False`, אז NaN עובר את כל בדיקות הטווח.

4. regex עם `\b` / escape sequences במחרוזת לא-raw ב-Python (`"\b"` הוא `\x08` (backspace), לא word boundary). דרוש `r"..."` ל-regex patterns.

5. ניתוח JSON על output של AI / LLM שמשתמש ב-regex חמדן (`\{.*\}`) במקום `json.JSONDecoder().raw_decode(...)`.

6. `setTimeout(fn, delay)` / `new Date(value)` כש-`delay` או `value` מקלט חיצוני, בלי הגנת `isFinite(...)`.

7. בדיקת **שייכות** על ערך חיצוני — `value in <set/frozenset/dict>` — בלי
בדיקת טיפוס לפניה. השורה נראית כמו שאלה שמחזירה כן/לא, אבל פייתון מחשב
`hash(value)` כדי לחפש, וערך לא-hashable (רשימה, מילון) **זורק
`TypeError`** במקום להחזיר `False`. התוצאה: 500 במקום 400, לפני
שהוולידציה הספיקה לומר מה לא תקין. `in` על `list`/`tuple` **אינו** זה: הוא
משווה ולא מגבב, ולכן טיפוסים מובנים לא תואמים פשוט מחזירים `False`
(`1 in ["a"]` ← `False`, נמדד) — אל תתריע עליו. הוא כן ראוי להתרעה רק
כשההשוואה יכולה להפעיל `__eq__` מותאם שזורק, או להחזיר ערך שההמרה שלו
ל-`bool` זורקת (מערך numpy הוא המקרה השכיח). בדוק טיפוס, ורק אז חברות.

## False positives

- קלט FastAPI שעבר ולידציית Pydantic — Pydantic כבר אוכף shape.
- מבני נתונים פנימיים שנבנו טרי בקוד שלנו.
- נתיבי `logger.debug` שלא ירוצו בפרודקשן.
- test fixtures ונתוני mock.

## חומרה

MEDIUM — קורס worker / request handler על payloads מעוותים בעולם אמיתי. HIGH אם משולב עם SQL או eval.
