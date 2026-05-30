# input-field-not-persisted

זהה schema-to-write drift: שדה שעובר את כל שכבות ה-input (Pydantic schema מקבל אותו, frontend שולח אותו) אך לא ממופה ב-row builder בנקודת הכתיבה הסופית. השדה מתקבל, נשלח, ונופל בשקט — ה-DB שומר את ה-default. הפיצ'ר נראה שלם אבל לא שומר כלום, ואין שגיאה.

**זה לא `linked-field-atomicity`:** הכלל ההוא עוסק ב**קבוצת** שדות מקושרים (status + timestamps + activity log) שצריכים להתעדכן יחד. הכלל הזה עוסק ב**שדה בודד** שעבר את כל השכבות אך הושמט מה-write. failure modes נפרדים — שניהם מתקיימים במקביל.

## דווח כשמתקיים אחד מהבאים

1. **Field defined in input schema, missing in row builder.** שדה ב-`*Create` / `*Update` BaseModel שאינו `Optional` ולא נראה ב-`Model(...)` constructor / `dict(...)` של ה-CRUD שמשתמש בסכמה. שווה ערך: `schema.model_fields.keys() - set(<crud_function>.assigned_columns)` כולל שדה non-derived.

2. **Wrong-source mapping בכתיבה.** ה-`Model(...)` כן מקבל ערך לעמודה, אבל מהמקור הלא נכון — `summary` במקום `raw_body`, `display_name` במקום `email`, `ai_classification` במקום `user_input`. ה-payload מכיל את כל השדות; הבאג הוא ב-assignment עצמו (פעמים רבות העתק-הדבק מ-flow אחר).

3. **שינוי schema ללא שינוי תואם ב-write layer.** PR שמוסיף שדה חדש ל-`*Create` schema **ולשכבת ה-UI** אבל לא נוגע בקובץ ה-CRUD (`crud_*.py`, `services/*.py`) שבונה את ה-row. signal של drift.

4. **שדה boolean / enum שמשמט ב-INSERT.** השדה מופיע ב-frontend payload וב-API contract, אבל ב-INSERT הוא מושמט → DB default (False / NULL / "") נשמר. בלי שגיאה כי העמודה nullable / יש default.

5. **Fix שמורכב משורה אחת בנקודת הכתיבה.** היסטוריית commits שכוללת diff שכל-כולו `+ row.field = payload.field` (או `+ field=data.field,` בתוך `Model(...)`) הוא retro-signal שהדפוס קרה — השדה עבר את שאר השכבות אבל נשמט שם. שווה לחפש את הדפוס הפוך ב-PRs פתוחים.

## False positives

- שדות **derived/computed** שלא אמורים להגיע ישירות מ-payload (מחושבים מ-fields אחרים, או מ-context). סינון: רק שדות שמופיעים גם ב-schema וגם ב-payload המתועד.
- **Audit columns** שמתמלאים אוטומטית (`created_at`, `created_by_id`, `updated_at`). סינון: לא להריץ על שדות שכלולים ב-`Base` / mixin.
- **PATCH endpoints** שכותבים subset מכוון של שדות. סינון: רק על create / replace endpoints (POST שיוצר entity חדש, PUT שמחליף שלם).
- **Schema המשמש כ-DTO לקריאה בלבד** (`*Read` / `*Response`) — לא רלוונטי לכתיבה.

## חומרה

MEDIUM — איבוד נתונים שקט. הפיצ'ר נראה עובד (UI מציג את הערך אם יש cache אופטימי או redirect ל-detail page); הסכמה לא דוחה (validation עברה); אין log שגיאה. ה-impact מתגלה רק כש-flow downstream קורא את ה-row ומקבל default במקום הערך שהמשתמש שלח. ב-CRM/CMS/forms — פגיעה ישירה ב-feature parity.
