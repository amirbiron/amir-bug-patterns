# דפוסים אוניברסליים (להעתקה ל-CLAUDE.md — חל על כל פרויקט)

1. **Async race / TOCTOU.** read-then-write דורש UNIQUE constraint, advisory lock, או CAS. `INSERT` מקומי **לפני** כל קריאה חיצונית בלתי הפיכה. כל `async def` שנקראת בהקשר בוליאני (`if foo():`) חייבת `await`. CAS על עמודה nullable: הסתעפות `is None` → השתמש ב-`IS NULL`.

2. **סנכרון state ב-React.** `useState(props.X)` מקומי ישן כש-`props.X` משתנה — השתמש ב-`key={id}`, `useEffect([X], () => setState(X))`, או derived state. כל ה-hooks לפני כל early return. deps של `useCallback`/`useMemo` חייבים לכלול כל prop/state בגוף. `setState` אחרי `await` בודק cancellation flag.

3. **ולידציה של external input.** לפני `.get()` / `.append()` / `.strip()` / iteration על נתון חיצוני: `isinstance(...)` guard. מספרים: `isfinite()` + טווח. regex על טקסט חיצוני: raw strings + word boundaries; עדיף `json.JSONDecoder().raw_decode()` על regex. קריאות SDK: תפוס base class (`anthropic.APIError`), סדר subclass-לפני-superclass. אתחול SDK ב-startup: try/except + ולידציית פורמט — הורד את הפיצ'ר, לעולם אל תקרוס את ה-boot.

4. **SQL/Postgres edges.** `col = NULL` הוא NULL, לא TRUE — הסתעפות `IS NULL`. `VARCHAR(N)` ≥ ערך enum הארוך ביותר (טסט CI). Telegram / IDs חיצוניים: `BigInteger`. כל `ORDER BY` משולב עם `LIMIT`/`OFFSET` דורש tiebreaker `, id`. `LIKE` עם קלט משתמש: `.startswith(value, autoescape=True)` או escape ל-`_`/`%`.

5. **atomicity של linked-field.** שינויי status מעדכנים את כל השדות המקושרים (`status` + `last_outbound_at` + `last_activity_type` + סגירת task קשור + activity-log) בטרנזקציה אחת. קריאה חיצונית: כתוב שורה מקומית עם `UNIQUE` קודם; או כתוב audit log עם `metadata.applied=false` בכשל. Token pairs (access + refresh) נשמרים/מתעדכנים יחד.

6. **סטיית migration.** כל `Index`/`CheckConstraint`/`UniqueConstraint` ב-migration חייב לשקף ב-`__table_args__` של המודל. revision id של Alembic ≤ 30 chars. פרויקטי MySQL: אסור `ADD COLUMN IF NOT EXISTS`. `DROP COLUMN` הוא migration נפרד אחרי שהקוד הפסיק להשתמש בשדה.

ראה `BY-STACK/*.md` לדוגמאות קוד ו-`bugbot-rules/*.md` ל-prompts של כללים עצמאיים.
