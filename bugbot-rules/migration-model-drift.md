# migration-model-drift

זהה סטיית schema-versioning בין קבצי migration ל-`__table_args__` של ORM model. DB טרי (test, dev, prod-from-scratch) מסתיים עם schema שונה מ-prod אחרי migrations הדרגתיים.

## דווח כשמתקיים אחד מהבאים

1. `op.create_index(...)` / `op.create_check_constraint(...)` / `op.create_unique_constraint(...)` ב-migration בלי `Index(...)` / `CheckConstraint(...)` / `UniqueConstraint(...)` תואם ב-`__table_args__` של המודל המתאים.

2. `op.drop_column(...)` ב-migration באותו PR שבו המודל עדיין מצהיר על העמודה או קוד אחר עדיין מתייחס אליה. (DROP חייב להיות ב-migration נפרד מאוחר יותר אחרי שהקוד הוסר לחלוטין.)

3. revision id של Alembic (שם קובץ או משתנה `revision`) ארוך יותר מ-30 chars. ברירת המחדל של `alembic_version.version_num` היא `VARCHAR(32)`; deploy טרי נכשל.

4. `ADD COLUMN IF NOT EXISTS` ב-migration של MySQL (syntax של PG בלבד).

5. `ALTER TABLE` של migration על טבלה שלא קיימת עדיין באף `CREATE TABLE` של migration קודם (כשל ב-deploy טרי).

6. עמודת `String(N)` / `VARCHAR(N)` שמתמלאת מ-enum שבה `N < max(len(value) for value in Enum)`.

7. עמודת `Integer` ל-IDs חיצוניים (Telegram, Discord, Stripe customer IDs) שיכולים לחרוג מ-2³¹ — צריכה להיות `BigInteger`.

## False positives

- migrations של data בלבד (backfill, fixup) בלי שינוי schema.
- test fixtures עם `extend_existing=True`.
- indexes שמנוהלים ידנית (נדיר; צריך להיות מתועד).

## חומרה

MEDIUM — DB טריים (CI, dev, prod חדש) מתפצלים מ-prod ממוגרר; constraint / index חסר ב-deploys טריים.
