# הערות מ-Migration — Meta-Analysis

הערות שכתבתי *אחרי* הצלבת שלושת מסמכי המקור. שימושיות לכיול חיפוש דפוסים עתידיים: מה הפתיע אותי, מה לא תרגם כפי שציפיתי, ומה לתפוס מיום ראשון בפרויקט חדש.

---

## 1. דפוסים שציפיתי שיהיו אוניברסליים — והם לא

### שלמות state-machine
**איפה זה חי:** כבד ב-Noa_Leads (P1 status transitions, P6 touchpoints, P9 activity log). חלקי ב-EmailFlow (P1 reserve-then-fill יש לו חפיפה). **כמעט לא קיים** בסריקת 8-הפרויקטים — רוב הפרויקטים האלה לא בנויים סביב state machines מפורשות, יש להם טרנזקציות one-shot או צורות CRUD פשוטות יותר.

**מסקנה:** שלמות state-machine היא עוצמה ספציפית ל-Noa, אבל ה-*עקרון הבסיסי* (לעדכן atomically את כל השדות המקושרים) מכליל — וזו הסיבה שזה CORE U5 ("partial atomic updates / linked-field drift") ולא ערך ספציפי ל-Noa בלבד. ההקשר של CRM פשוט גורם למצב הכשל להיות יותר ברור.

### לולאות אינסופיות של Cron
**איפה זה חי:** מרכזי ב-Noa (P5 — שוב ושוב). לא מופיע ב-EmailFlow (שמשתמש ב-Pub/Sub, לא ב-cron). סריקת 8-הפרויקטים יש בה "לולאות" אבל הן לולאות routing/UI (C20 driver-secretary, C27 admin reset), לא filters של cron.

**מסקנה:** "ל-cron אין terminal state" ייחודי לפרויקטים עם לולאות retry מתוזמנות על שורות DB. נתתי לזה `BY-STACK/cron-jobs.md` משלו למרות תדירות חד-מקורית כי ההשפעה חמורה והדפוס דביק (כל פרויקט שמשתמש ב-cron יפגע בזה).

### Pydantic schema defaults דורסים את הכוונה של ה-caller
**איפה זה חי:** רק Noa (P4). נראה לי כמו דפוס כללי של Python "type hints לא באמת בודקות types", אבל רק Noa משתמש ב-Pydantic בכבדות בגבולות API.

**מסקנה:** ספציפי ל-stack. חי ב-`BY-STACK/external-sdk.md` וב-`state-machine.md` כהערת צד, לא ב-CORE.

### שגיאות סדר hooks ב-React / Rules of Hooks
**איפה זה חי:** EmailFlow P2 מפורש. Noa מזכיר בעיות useEffect אבל לא מסדר אותן בצורה פורמלית. ל-8-projects יש stale closures (C22, C33) שקשורות אבל לא בדיוק אותו דבר.

**מסקנה:** זה נכנס ל-CORE U2 כי ה-*משפחה* של באגים (state sync, stale closure, hooks ordering) מופיעה בכל 3 המקורות גם אם הניסוח הספציפי שונה.

---

## 2. חיבורים מפתיעים שלא ציפיתי להם

### "Reserve-then-fill" ≡ "TOCTOU duplicate sends"
EmailFlow מסגר את P1 סביב at-least-once delivery של Pub/Sub וטרנזקציות מפצות. Shipment-bot מסגר את C5 סביב beat scheduler של Celery + `.delay()` שמתחרים על `SELECT ... PENDING`. **אותו root cause** — כתיבה ל-DB לפני הפעולה החיצונית הבלתי הפיכה בלי UNIQUE constraint או CAS atomic. אוצר המילים שונה, התיקון זהה:
```
INSERT INTO ... (with UNIQUE) BEFORE the external call
```
זו הסיבה ש-CORE U1 כל כך רחב: race conditions, missing await, reserve-then-fill, TOCTOU duplicate sends, ו-check-outside-lock הם כולם מופעים של אותה שגיאה בסיסית.

### "Activity log as source of truth" ≡ "Audit log lifecycle"
Noa P9 אמר: כש-`UPDATE` נכשל (rowcount=0 בגלל דחיית CAS), עדיין לוג את ה-activity עם `metadata.applied=false`, כי cron ו-dashboards צורכים את הלוג. EmailFlow P1 אמר: audit logs חייבים לתעד *intent*, לא רק *completion*, אחרת compliance מראה "שליחה" שלעולם לא קרתה. **אותו עקרון** — לוג את ה-intent לפני side-effect, לוג את התוצאה אחרי, לעולם אל תאבד את ה-event signal בין לבין.

### "VARCHAR(20) קטן מדי ל-enum" ≡ "Integer קטן מדי ל-Telegram ID"
Noa (`2c8263a`) הוסיף ערך `StrEnum` חדש ארוך מ-`VARCHAR(20)`. Shipment-bot (`b16b99f`) גילה ש-Telegram IDs חורגים מ-2³¹. **אותו root cause** — טיפוס עמודה שנבחר צר מדי ל-value space האמיתי, נתפס רק כשערך אמיתי פוגע ב-prod. שניהם נכנסים ל-CORE U4 (Postgres/SQL edges) ו-U6 (migration drift).

### "Stale closure" ≡ "useEffect dep על reference של object"
8-projects C22 (`activeChildId` חסר מ-deps של `useCallback`) ו-Noa P3 React fragment (`useEffect` deps על reference של object שמפעיל re-renders שדורסים edits) הם אותה משפחה של stale-closure-staleness ב-React. ניסוחים שונים, ערך CORE אחד (U2).

---

## 3. Top-3 דפוסים לתפוס מיום ראשון בפרויקט חדש

מסודר לפי תדירות במקורות × חומרה:

### #1 — CORE U1: race conditions async
**למה ראשון:** 15+ מופעים בכל 3 המקורות. בפער ניכר ה-class הגדול ביותר של באגים בעבודה שלי.
**Day-1 action:** לפני כתיבת ה-webhook handler / queue worker / cron job הראשון:
1. החלט על אסטרטגיית idempotency לכל endpoint (UNIQUE constraint? Idempotency key ב-header? Advisory lock?).
2. חבר תבנית `INSERT ... ON CONFLICT` או `SELECT FOR UPDATE` או CAS ל-utility של הפרויקט.
3. הוסף item ל-PR template: "אילו כתיבות concurrent מוגנות על ידי איזה מנגנון?"

### #2 — CORE U2: סנכרון state ב-React מ-props
**למה שני:** משפיע על כל פרויקט React ברגע שיש לו טופס או dropdown שמסונכרן עם נתוני backend. ההתאוששות מהבאג הזה יקרה (שחיתות נתונים שקטה — `expected_status` שגוי נשלח ל-backend).
**Day-1 action:** החלט על convention לכל הפרויקט:
- ברירת מחדל: `<Child key={id} />` על כל קומפוננטה שמקבלת נתונים מ-`useQuery`.
- או: `useEffect([id])` resync מפורש.
- או: derived state (בלי `useState` מקומי בכלל).
בחר אחד, כתוב ל-`CLAUDE.md`, והחל מהטופס הראשון.

### #3 — CORE U3: ולידציה של external input
**למה שלישי:** קריסות מופיעות תוך שבועות מהגעת טראפיק אמיתי. test/sandbox/prod תמיד נסחפים על צורה (Gmail/Meta/Stripe), והקריסה היא בזמן הגרוע ביותר (משתמש יחיד עם payload פגום מפיל את ה-worker).
**Day-1 action:** לפני *כל* `.get()`, `.append()`, `.strip()` על נתון חיצוני:
1. isinstance guard.
2. בדיקת NaN/Inf למספרים.
3. raw string + word boundaries ל-regex על טקסט חיצוני.
4. SDK base-class `except` מסודר subclass-לפני-superclass.

גם: כל אתחול SDK בזמן startup (VAPID, OAuth, Stripe) עטוף ב-try/except — אחרת env var רע אחד מפיל את ה-boot.

---

## הערות תהליך לפעם הבאה

- **מבנה מסמך המקור משנה.** המסמך של EmailFlow היה הכי שימושי — רשימה מפורשת P1..P7 עם commits, false positives, ו-mode מומלץ. למסמך 8-projects יש breadth עשירה יותר אבל מבנה שטוח יותר; קשה יותר להצליב. **מסמכים עתידיים: השתמש בתבנית של EmailFlow.**
- **חומרה vs תדירות צריכים להיות מופרדים מההתחלה.** התחלתי לערבב אותם בתוכנית, ואתה (בצדק) דחפת חזרה. הוסף שדה `severity` לכל דפוס מתועד מיום ראשון כדי שהצלבה לא תאבד מידע.
- **מקור אחד ≠ לא חשוב.** האשכול של 8-projects של אבטחה (OAuth takeover, XSS, rate-limit spoofing, hash leak, panel exposure) כולם הגיעו ממקור אחד. קידום שלהם ל-CRITICAL בכל זאת הוא נכון — תדירות היא proxy רועש לחומרה.
