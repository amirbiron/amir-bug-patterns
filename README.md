# amir-bug-patterns — ספריית קונטקסט אישית של דפוסי באגים 

סט מאורגן של דפוסי באגים מהפרויקטים שלי, מאורגנים כך שאני יכול ליישם אותם מכנית על `CLAUDE.md` / הגדרת bugbot של פרויקט חדש ולמנוע חזרה על אותן טעויות.

## למה הריפו הזה קיים

שמתי לב שאותם classes של באגים מופיעים בפרויקטים מרובים שלי — stacks שונים, תחומי בעיה שונים, אותן טעויות יסודיות. אחרי תיעוד post-mortem של שלושה פרויקטים (`docs/source-projects/`), הצלבתי אותם לספרייה אחת.

הבאגים מתפצלים לפי שלושה צירים:
- **תדירות** — בכמה מהפרויקטים שלי הופיע הדפוס (סיגנל ל-"זה אני?").
- **חומרה** — אבטחה, פרטיות, אובדן נתונים, השפעה פיננסית (סיגנל ל-"חייב לתפוס בכל מקרה").
- **scope של stack** — באילו טכנולוגיות / תחומים הדפוס מתחבר (סיגנל ל-"זה רלוונטי כאן?").

## איך להחיל על פרויקט חדש

### 1. תמיד להעתיק (ללא קשר ל-stack)

| מקור | יעד |
|---|---|
| `CORE-PATTERNS.md` | לזרוק ל-`docs/` של הפרויקט החדש, או לקשר מ-`CLAUDE.md`. |
| `CRITICAL-PATTERNS.md` | אותו דבר. |
| `claude-md-snippets/universal.md` | **להדביק את התוכן ל-`CLAUDE.md` של הפרויקט** (תמציתי, 6 כללים). |
| `claude-md-snippets/critical.md` | **להדביק את התוכן ל-`CLAUDE.md` של הפרויקט** (תמציתי, 16 כללים). |
| `TESTING-PATTERNS.md` | לזרוק ל-`docs/`, או לקשר מ-`CLAUDE.md`. |
| `claude-md-snippets/testing.md` | **להדביק את התוכן ל-`CLAUDE.md` של הפרויקט** (תמציתי, 6 כללים). |
| `BY-STACK/hebrew-source.md` + `claude-md-snippets/hebrew.md` | כל פרויקט שלי — ההערות בקוד בעברית. |

זה ~90 שורות שמתווספות ל-`CLAUDE.md` שמכסות את ה-baseline האוניברסלי, האבטחה, הבדיקות והעברית.

### 2. ואז לפי stack

עבור על decision tree הזה. כל "כן" מעתיק קובץ stack אחד + snippet אחד.

| אם בפרויקט יש... | להעתיק | להדביק ל-`CLAUDE.md` |
|---|---|---|
| React frontend | `BY-STACK/react-frontend.md` | `claude-md-snippets/react.md` |
| SQLAlchemy async | `BY-STACK/async-orm.md` | `claude-md-snippets/async-orm.md` |
| Webhooks / Pub-Sub / queue consumers | `BY-STACK/webhooks.md` | `claude-md-snippets/webhooks.md` |
| Cron / tasks מתוזמנים | `BY-STACK/cron-jobs.md` | `claude-md-snippets/cron-jobs.md` |
| Postgres (או כל SQL עם migrations & pagination) | `BY-STACK/postgres.md` | `claude-md-snippets/postgres.md` |
| MongoDB / Atlas — אינדקסים שנוצרים מהקוד, אגרגציה, pymongo | `BY-STACK/mongodb.md` | `claude-md-snippets/mongodb.md` |
| מדדי בריאות, התראות, או מנגנון שפועל אוטומטית לפי מספר | `BY-STACK/observability.md` | `claude-md-snippets/observability.md` |
| Anthropic / Google / Stripe / OAuth / FCM SDKs | `BY-STACK/external-sdk.md` | `claude-md-snippets/external-sdk.md` |
| קוד דפדפן עם `mailto:` / clipboard / blob URLs | `BY-STACK/browser-handoff.md` | `claude-md-snippets/browser-handoff.md` |
| State machines / status enums | `BY-STACK/state-machine.md` | `claude-md-snippets/state-machine.md` |
| מגיש HTML / CSP / OAuth בדפדפן / iframes | `BY-STACK/browser-policy.md` | `claude-md-snippets/browser-policy.md` |

### 3. אופציונלי — אם יש זמן

`RECURRING-PATTERNS.md` מכסה דפוסים שאושרו בשני פרויקטי מקור שונים (R1–R9). קונטקסט נוסף שימושי לטווח ארוך; לא נדרש לסקירה הראשונה.

### 4. כללי bugbot

`bugbot-rules/*.md` — קובץ אחד לכל כלל, stack-agnostic. השתמש בהם דרך אחת מהבאות:
- העתקת קבצים בודדים להגדרת bugbot של Cursor / דומה.
- הדבקת התוכן ל-prompt של סקירת קוד עם Claude אחד בכל פעם בעת סקירת PR.
- שילוב כמה ל-prompt אחד לסקירה ממוקדת (למשל סקירת אבטחה = כללי K1..K10 + K12 בידוד דיירים + K13 סוד במחרוזת נגזרת + K14 סוד בשורת שאילתה + K16 גבול נתיב כקידומת מחרוזת; K11 (שלמות-נתונים) ו-K15 (זמינות) אינם אבטחה — צרף אותם לסקירות correctness).

**כל** הכללים המתויגים CRITICAL ב-`bugbot-rules/` (הרשימה בעץ למטה; ‏`pii-in-logs`, ‏`xss-innerhtml`, ‏`rate-limit-xff-spoofing`, ‏`path-prefix-not-boundary`, וכל השאר) צריכים לרוץ על PRs שנוגעים ב-auth, ב-endpoints חשופים-לציבור, בקלט משתמש, או בפעולות על קבצים. השמות כאן הם דוגמה — הרשימה הקובעת היא התיוג בקבצים עצמם.

## איך לתחזק

כשאני נתקל בדפוס חדש שלא היה בספרייה:

1. **תעד אותו תחת `docs/source-projects/<project-name>-patterns.md`** באותה תבנית בסגנון EmailFlow (P1, P2, ..., עם commits, false positives, מצב מומלץ).

2. **הצלב מול ה-tiers הקיימים:**
   - אם **שלושה פרויקטי מקור שונים** מאשרים עכשיו את אותו דפוס → קדם ל-`CORE-PATTERNS.md`. (פרויקטים, לא מסמכים: לפרויקט אחד יכולים להיות שני מסמכי מקור — ל-CodeBot יש — ושניים כאלה אינם שני אישושים.)
   - אם **שני פרויקטי מקור שונים** מאשרים → `RECURRING-PATTERNS.md`. (הניסוח המקורי היה "2 מתוך 3", מהתקופה שבה היו שלושה מסמכי מקור בלבד. ככל שנוספים מקורות יחס מספרי מאבד משמעות, והבר הוא מה שהכלל התכוון אליו: שני פרויקטים, לא שני שלישים.)
   - אם החומרה היא HIGH (אבטחה, אובדן נתונים, פרטיות, או השבתה שקטה של שירות — הציר שעליו נכנס K15) ללא קשר לתדירות → `CRITICAL-PATTERNS.md`.
   - אחרת → רק `BY-STACK/*.md` הרלוונטי.

3. **הוסף `bugbot-rules/<name>.md`** לכל דפוס עם detection signature נקייה לאוטומציה.

   **לפני שמוסיפים דפוס — לשאול אם הוא בכלל באג בקוד.** אם הבאג היה
   בפער בין מה שהבדיקות אימתו לבין מה שהמערכת עושה, מקומו
   ב-`TESTING-PATTERNS.md`, לא בקטגוריה לפי stack. הציר הזה נוסף
   מאוחר בדיוק כי פספסתי אותו: שלושה באגים רצופים ב-Markdown-Docs
   תוקנו כבאגי קוד, בזמן שהשורש המשותף היה שהבדיקות עקבו אחרי המפרט
   ולא אחרי הלקוח.

4. **עדכן את הסניפט המשויך למסמך שהדפוס נכנס אליו.** צעד 2 קובע את המסמך, וממנו נגזר הסניפט — ה-≤20 שורות הן תקרת גודל, לא ההחלטה:
   - נכנס ל-`CORE-PATTERNS.md` (U) — הסניפט: `claude-md-snippets/universal.md`.
   - נכנס ל-`CRITICAL-PATTERNS.md` (K) — הסניפט: `claude-md-snippets/critical.md`, **באותו מספר**: פריט N שם הוא KN.
   - נכנס ל-`TESTING-PATTERNS.md` (T) — הסניפט: `claude-md-snippets/testing.md`.
   - נכנס ל-`BY-STACK/<x>.md` — הסניפט: `claude-md-snippets/<x>.md`, אותו שם קובץ.
   - נכנס ל-`RECURRING-PATTERNS.md` (R) — הסניפט של הסטאק התואם. ל-R אין סניפט משלו: ‏R1–R5 כולם stack-bound (והכלל הבסיסי של R2 ו-R4 יושב גם ב-`universal.md`), ‏R8 ו-R9 נשענים על `mongodb.md` ו-`observability.md`. ‏**R6 (עותק שני של כלל) ו-R7 (אזור זמן) הם היוצאים מן הכלל — חוצי-סטאק ובלי סניפט**, ולכן מסלול ההגעה היחיד שלהם הוא שורת הטריגר. זו החלטה: הם לא נכנסו ל-`universal.md` כי הוא ממופה אחד-לאחד ל-U1..U6, והוספה שם הייתה שוברת את המיפוי שעליו נשען צעד 2.
   - **נשאר רק ב-`bugbot-rules/` + מסמך המקור — אין לו סניפט, וזו החלטה ולא פטור.**

   השורה האחרונה היא העיקר: הסניפטים הם מה שמודבק **במלואו** לפרויקט חדש, ולכן הם מוגבלים לשכבות שחלות בכל מקום. דפוס ממקור אחד שלא קודם לאף tier מגיע לפרויקטים דרך **ההפניה בלבד** — בדיוק העיקרון שב-`INTEGRATION.md` ("לא מעתיקים את הידע לפרויקטים, מעתיקים רק את ההפניה"). ולכן, בשבילו, שורת הטריגר שבצעד 5 אינה תוספת נחמדה אלא **מסלול ההגעה היחיד שלו**.

5. **הוסף שורת טריגר ב-`CLAUDE.md` של הפרויקטים הרלוונטיים** (התבנית
   והמיפוי ב-`INTEGRATION.md`). דפוס בלי טריגר הוא דפוס שלא ייקרא בזמן
   המימוש — שני הצעדים הם צעד אחד, לא שניים.

6. **קרא מחדש את `MIGRATION-NOTES.md`** רבעונית כדי לראות אם המודל המנטלי שלי של "אוניברסלי vs ספציפי ל-stack" עדיין מחזיק.

### מתי הלולאה הזו נסגרת — הטריגרים לתיעוד

(הנוסח המודבק ל-`CLAUDE.md` של פרויקטים חי ב-`INTEGRATION.md` §1 — עדכון
לכללים האלה מעדכן את שני המקומות יחד.)

- **ריוויוור (cubic / qodo / CodeRabbit / claude) תפס ממצא אמיתי ב-PR**
  שאינו מכוסה כאן → הממצא כבר מנוסח, עם קוד והסבר. לתעד **באותו יום**,
  בזמן שהראיות טריות — לא בסוף הסשן ולא "כשיהיה זמן".
- **אותו סוג טעות תוקן פעמיים** — גם בלי שריוויוור תפס. פעמיים = דפוס.
- **וכשכותבים את שורת הטריגר: טריגר מזהה מה אתה מקליד, לא באיזה מצב אתה נמצא.** ‏`LOCK_FAIL_OPEN` ו-`0.0.0.0` רואים על המסך; "מסלול שרץ גם ברקע" ו"אחד מארבעת הנתיבים האלה" הם דברים שצריך **לדעת**, ושורה שדורשת אותם כתנאי כניסה דורשת את התשובה שהיא אמורה לתת. התנאי שייך למסמך. ומאותה סיבה — לתאר מחלקה ולא למנות מופעים: רשימה מתיישנת ברגע שנוסף המופע הבא.
- הלקח מ-CodeBot P1: הדפוס חזר **שלוש פעמים** לפני שתועד, ובפעם השלישית
  ריוויוור הצביע על ה-PR הקודם בעצמו. תיעוד אחרי הפעם הראשונה היה חוסך
  את שתי הבאות.

## מבנה הריפו

```text
amir-bug-patterns/
├── README.md                    # הקובץ הזה
├── INTEGRATION.md               # איך הידע מגיע לסשנים: טריגרים ל-CLAUDE.md, נוסח לבאגבוטים, תהליך פרויקט חדש
├── CORE-PATTERNS.md             # U1..U6 — 3/3 מקורות, החל בכל מקום
├── CRITICAL-PATTERNS.md         # K1..K16 — חומרה גבוהה, החל בכל מקום
├── RECURRING-PATTERNS.md        # R1..R9 — אושרו בשני פרויקטים, החל אם ה-stack תואם
├── TESTING-PATTERNS.md          # T1..T3 — הבדיקה כמקור הבאג, החל בכל מקום
├── MIGRATION-NOTES.md           # meta-analysis, top-3 day-1 picks
├── BY-STACK/                    # 12 קבצים, מאורגנים לפי מודל מנטלי
│   ├── react-frontend.md
│   ├── async-orm.md
│   ├── state-machine.md
│   ├── webhooks.md
│   ├── cron-jobs.md
│   ├── postgres.md
│   ├── mongodb.md
│   ├── observability.md
│   ├── external-sdk.md
│   ├── browser-handoff.md
│   ├── browser-policy.md
│   └── hebrew-source.md
├── claude-md-snippets/          # קצר, להדבקה ל-CLAUDE.md של הפרויקט (critical.md חורג: כלל אחד לכל K)
│   ├── universal.md
│   ├── critical.md
│   ├── react.md
│   ├── async-orm.md
│   ├── state-machine.md
│   ├── webhooks.md
│   ├── cron-jobs.md
│   ├── postgres.md
│   ├── mongodb.md
│   ├── observability.md
│   ├── external-sdk.md
│   ├── browser-handoff.md
│   ├── browser-policy.md
│   ├── testing.md
│   └── hebrew.md
├── bugbot-rules/                # כלל אחד לכל קובץ, stack-agnostic
│   ├── race-toctou.md
│   ├── test-mirrors-spec-not-client.md
│   ├── test-infra-shared-state.md
│   ├── blanket-policy-silent-block.md
│   ├── hebrew-source-and-data.md
│   ├── react-stale-state-on-prop.md
│   ├── react-async-media-resource.md
│   ├── external-input-isinstance.md
│   ├── postgres-null-cas.md
│   ├── linked-field-atomicity.md
│   ├── input-field-not-persisted.md
│   ├── migration-model-drift.md
│   ├── pagination-tiebreaker.md
│   ├── sdk-error-completeness.md
│   ├── sdk-lazy-object-not-validated.md
│   ├── side-effect-riding-on-log-line.md
│   ├── window-open-protocol-handoff.md
│   ├── cron-terminal-state.md
│   ├── filter-too-narrow.md
│   ├── return-value-failure-unchecked.md
│   ├── line-number-coupling.md
│   ├── widened-exception-scope.md
│   ├── background-thread-liveness.md
│   ├── content-hash-normalization.md
│   ├── state-record-without-state-change.md
│   ├── lazy-init-guard-publish-order.md
│   ├── silent-fallback-to-worse-path.md
│   ├── naive-datetime-no-conversion.md
│   ├── duplicate-rule-second-copy.md
│   ├── work-disproportionate-to-answer.md
│   ├── metric-mixes-sources.md
│   ├── linter-fix-changes-runtime-behavior.md
│   ├── import-time-side-effects.md
│   ├── logical-entity-vs-version-document.md
│   ├── silent-truncation-at-sink.md
│   ├── rtl-geometry-and-clamp.md
│   ├── mongo-index-and-operator-traps.md
│   ├── stale-asset-cache-policy.md
│   ├── dead-parameter-external-api.md
│   ├── derived-field-added-to-one-writer.md
│   ├── host-metric-in-container.md
│   ├── prose-restates-code-fact.md
│   ├── body-read-outside-cheap-reject.md
│   ├── wait-without-own-deadline.md
│   ├── pii-in-logs.md                       # CRITICAL
│   ├── secret-in-error-response.md          # CRITICAL
│   ├── secret-in-derived-text.md            # CRITICAL
│   ├── secret-in-url-query.md               # CRITICAL
│   ├── xss-innerhtml.md                     # CRITICAL
│   ├── rate-limit-xff-spoofing.md           # CRITICAL
│   ├── auth-before-irreversible-action.md   # CRITICAL
│   ├── privilege-escalation-unverified.md   # CRITICAL
│   ├── network-exposed-without-auth.md      # CRITICAL
│   ├── like-wildcard-injection.md           # CRITICAL
│   ├── tenant-row-scoping.md                # CRITICAL
│   └── path-prefix-not-boundary.md          # CRITICAL
├── scripts/                     # בדיקות על הריפו עצמו
│   └── check_readme_tree.py     # משווה את העץ שלמטה לקבצים שבמעקב, בשני הכיוונים
└── docs/source-projects/        # מסמכי post-mortem מקוריים (reference)
    ├── noa-leads-patterns.md
    ├── emailflow-patterns.md
    ├── eight-projects-patterns.md
    ├── markdown-docs-mcp-patterns.md
    ├── campaign-ai-patterns.md
    ├── codebot-patterns.md
    └── codebot-history-scan-patterns.md
```

## ראה גם

- **`INTEGRATION.md`** — הצד השני של הספרייה: איך הידע מגיע לסשנים בזמן המימוש, ולא רק שוכב כאן.
- **`MIGRATION-NOTES.md`** — מה הפתיע אותי במהלך ההצלבה, ומהם 3 הדפוסים העליונים לחיבור לפרויקט חדש ביום הראשון.
- **`TESTING-PATTERNS.md`** — הציר שבו הקוד שבור, הבדיקות ירוקות, וה-CI הוא זה שמשקר. אי אפשר לתפוס אותו בעזרת עוד בדיקה מאותו סוג.
- **`docs/source-projects/`** — מסמכי post-mortem מקוריים בעברית שמזינים את הספרייה הזו. ההפניות הצולבות בכל קובץ דפוס (`commit 33af59e`, `commit f847a44`, וכו') מצביעות לתוך מסמכי המקור.
