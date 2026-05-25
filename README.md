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
| `claude-md-snippets/critical.md` | **להדביק את התוכן ל-`CLAUDE.md` של הפרויקט** (תמציתי, 10 כללים). |

זה ~50 שורות שמתווספות ל-`CLAUDE.md` שמכסות את ה-baseline האוניברסלי + האבטחה.

### 2. ואז לפי stack

עבור על decision tree הזה. כל "כן" מעתיק קובץ stack אחד + snippet אחד.

| אם בפרויקט יש... | להעתיק | להדביק ל-`CLAUDE.md` |
|---|---|---|
| React frontend | `BY-STACK/react-frontend.md` | `claude-md-snippets/react.md` |
| SQLAlchemy async | `BY-STACK/async-orm.md` | `claude-md-snippets/async-orm.md` |
| Webhooks / Pub-Sub / queue consumers | `BY-STACK/webhooks.md` | `claude-md-snippets/webhooks.md` |
| Cron / tasks מתוזמנים | `BY-STACK/cron-jobs.md` | `claude-md-snippets/cron-jobs.md` |
| Postgres (או כל SQL עם migrations & pagination) | `BY-STACK/postgres.md` | `claude-md-snippets/postgres.md` |
| Anthropic / Google / Stripe / OAuth / FCM SDKs | `BY-STACK/external-sdk.md` | `claude-md-snippets/external-sdk.md` |
| קוד דפדפן עם `mailto:` / clipboard / blob URLs | `BY-STACK/browser-handoff.md` | `claude-md-snippets/browser-handoff.md` |
| State machines / status enums | `BY-STACK/state-machine.md` | `claude-md-snippets/state-machine.md` |

### 3. אופציונלי — אם יש זמן

`RECURRING-PATTERNS.md` מכסה דפוסים מ-2 מתוך 3 פרויקטי המקור (R1–R5). קונטקסט נוסף שימושי לטווח ארוך; לא נדרש לסקירה הראשונה.

### 4. כללי bugbot

`bugbot-rules/*.md` — קובץ אחד לכל כלל, stack-agnostic. השתמש בהם דרך אחת מהבאות:
- העתקת קבצים בודדים להגדרת bugbot של Cursor / דומה.
- הדבקת התוכן ל-prompt של סקירת קוד עם Claude אחד בכל פעם בעת סקירת PR.
- שילוב כמה ל-prompt אחד לסקירה ממוקדת (למשל סקירת אבטחה = כללי K1..K10).

הכללים המתויגים CRITICAL (`pii-in-logs`, `xss-innerhtml`, `rate-limit-xff-spoofing`, וכו') צריכים תמיד לרוץ על PRs שנוגעים ב-auth, endpoints חשופים-לציבור, או קלט משתמש.

## איך לתחזק

כשאני נתקל בדפוס חדש שלא היה בספרייה:

1. **תעד אותו תחת `docs/source-projects/<project-name>-patterns.md`** באותה תבנית בסגנון EmailFlow (P1, P2, ..., עם commits, false positives, מצב מומלץ).

2. **הצלב מול ה-tiers הקיימים:**
   - אם 3 מסמכי מקור מאשרים עכשיו את אותו דפוס → קדם ל-`CORE-PATTERNS.md`.
   - אם 2 מתוך 3 מאשרים → `RECURRING-PATTERNS.md`.
   - אם החומרה היא HIGH (אבטחה, אובדן נתונים, פרטיות) ללא קשר לתדירות → `CRITICAL-PATTERNS.md`.
   - אחרת → רק `BY-STACK/*.md` הרלוונטי.

3. **הוסף `bugbot-rules/<name>.md`** לכל דפוס עם detection signature נקייה לאוטומציה.

4. **עדכן `claude-md-snippets/*.md`** אם הדפוס תמציתי מספיק להיכנס ב-≤20 שורות.

5. **קרא מחדש את `MIGRATION-NOTES.md`** רבעונית כדי לראות אם המודל המנטלי שלי של "אוניברסלי vs ספציפי ל-stack" עדיין מחזיק.

## מבנה הריפו

```
amir-bug-patterns/
├── README.md                    # הקובץ הזה
├── CORE-PATTERNS.md             # U1..U6 — 3/3 מקורות, החל בכל מקום
├── CRITICAL-PATTERNS.md         # K1..K10 — חומרה גבוהה, החל בכל מקום
├── RECURRING-PATTERNS.md        # R1..R5 — 2/3 מקורות, החל אם ה-stack תואם
├── MIGRATION-NOTES.md           # meta-analysis, top-3 day-1 picks
├── BY-STACK/                    # 8 קבצים, מאורגנים לפי מודל מנטלי
│   ├── react-frontend.md
│   ├── async-orm.md
│   ├── state-machine.md
│   ├── webhooks.md
│   ├── cron-jobs.md
│   ├── postgres.md
│   ├── external-sdk.md
│   └── browser-handoff.md
├── claude-md-snippets/          # ≤20 שורות כל אחד, להדבקה ל-CLAUDE.md של הפרויקט
│   ├── universal.md
│   ├── critical.md
│   ├── react.md
│   ├── async-orm.md
│   ├── state-machine.md
│   ├── webhooks.md
│   ├── cron-jobs.md
│   ├── postgres.md
│   ├── external-sdk.md
│   └── browser-handoff.md
├── bugbot-rules/                # כלל אחד לכל קובץ, stack-agnostic
│   ├── race-toctou.md
│   ├── react-stale-state-on-prop.md
│   ├── external-input-isinstance.md
│   ├── postgres-null-cas.md
│   ├── linked-field-atomicity.md
│   ├── migration-model-drift.md
│   ├── pagination-tiebreaker.md
│   ├── sdk-error-completeness.md
│   ├── window-open-protocol-handoff.md
│   ├── cron-terminal-state.md
│   ├── filter-too-narrow.md
│   ├── pii-in-logs.md                       # CRITICAL
│   ├── secret-in-error-response.md          # CRITICAL
│   ├── xss-innerhtml.md                     # CRITICAL
│   ├── rate-limit-xff-spoofing.md           # CRITICAL
│   ├── auth-before-irreversible-action.md   # CRITICAL
│   ├── privilege-escalation-unverified.md   # CRITICAL
│   ├── network-exposed-without-auth.md      # CRITICAL
│   └── like-wildcard-injection.md           # CRITICAL
└── docs/source-projects/        # מסמכי post-mortem מקוריים (reference)
    ├── noa-leads-patterns.md
    ├── emailflow-patterns.md
    └── eight-projects-patterns.md
```

## ראה גם

- **`MIGRATION-NOTES.md`** — מה הפתיע אותי במהלך ההצלבה, ומהם 3 הדפוסים העליונים לחיבור לפרויקט חדש ביום הראשון.
- **`docs/source-projects/`** — מסמכי post-mortem מקוריים בעברית שמזינים את הספרייה הזו. ההפניות הצולבות בכל קובץ דפוס (`commit 33af59e`, `commit f847a44`, וכו') מצביעות לתוך מסמכי המקור.
