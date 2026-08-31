# inferring-external-state-from-indirect-indicator

**CRITICAL** — הסקת מסקנה על מצב חיצוני מסיגנל עקיף, במקום לשאול את המקור. הסמנטיקה של "חסר / ריק / None / no-op" מפורשת כ"לא קרה / לא קיים", כשהיא בעצם רק אומרת "לא ידעתי". התוצאה: חיוב כפול, לידים אבודים, מודעות יתומות שממשיכות לשרוף תקציב, tokens שממשיכים להיחשב תקפים אחרי שנשללו.

## דווח כשמתקיים אחד מהבאים

1. **`None` / `[]` / `False` / `0` שמתפרש כ"מצב חיצוני שלילי" בלי query מכוון.**
   - `if not cookie: return "no session"` — cookie חסר אינו הוכחה שאין session; ייתכן שהבקשה פשוט לא נשאה אותו.
   - `if not events: return "day free"` — רשימה ריקה מ-API יכולה להיות "אין events" **או** "השאילתה נכשלה בשקט" **או** "אין הרשאה".
   - `if delete_result is None: mark_as_deleted()` — no-op של API יכול להיות "כבר נמחק" **או** "לא רץ בכלל" (חסרות credentials).
   - `if raw_campaign is None: return {leads: 0}` — `None` מהמקור העיקרי נסגר מיד ל-0, בלי fallback ל-DB count.

2. **תגובת 200 עם שדה `errors` שלא נבדק.** `response.status_code == 200` נחשב הצלחה, אבל body כמו `{data: {...}, errors: [...]}` (Google FreeBusy, GraphQL, בנקאות) אומר "כלום לא רץ בהצלחה". קרא את שדה השגיאה **לפני** שאתה מפרש את ה-data.

3. **סיווג שלילי → מסקנה חיובית על המצב.**
   - `if not is_transient(err): mark_token_dead()` — "השגיאה לא זמנית" אינו "ה-token מת"; זה יכול להיות `NotFound`, `BadRequest`, או שגיאה לא-מסווגת.
   - `if trial_ends_at > now(): has_paid_access = True` — future timestamp אינו הוכחה לתשלום; ה-status עצמו יכול להיות `canceled` או `trial`.

4. **fallback שקט של `default=` שמסתיר את היעדר המקור.**
   - `os.getenv("X", "production")` — env var חסר → פרודקשן ← וזה יכול להיות typo של המשתמש. הכפף `is None` במפורש.
   - `ContextVar("tenant", default=None)` שמסתיר "השארתי context ריק" מ"אין tenant" (ראה `tenant-row-scoping.md`).
   - `data.get("busy", [])` בלי לבדוק `errors` — ראה §2.

5. **בדיקת קיום שכתובה כ"לא נמצא ⇒ יצירה" בלי CAS.**
   `if not row: create_row(...)` — קריאה־ואז־כתיבה בלי atomicity, וגם: "לא נמצא" יכול להיות "עוד לא נוצר" **או** "נמחק בזמן שקראתי". חופף עם `race-toctou.md`, אבל כאן ההדגשה על המסקנה השגויה, לא על ה-race.

## תבנית תיקון

- **Query directly, don't infer.** כשה-decision נגזר ממצב חיצוני — שאל את המקור ("האם ה-session תקף?" ולא "האם ה-cookie מגיע?").
- **Fail-closed on ambiguity.** אם ה-signal יכול להיות משהו אחר, ברירת המחדל היא "לא ידוע" ולא "לא קיים". Route ל-`UNKNOWN` שדורש טיפול מפורש (retry / escalation / human review), לא ל-fallback שקט.
- **הפרד שלושה מצבים.** "success", "failure known", "failure unknown" — כל אחד עם outcome משלו. Sentinels יחידים (`None` / `[]`) שמכסים שני מצבים או יותר הם באג בהמתנה.
- **שדות שגיאה נקראים לפני שדות תוצאה.** ל-response מ-API הטרוגני: `if response.get("errors"): raise` **לפני** ש-`response.get("data")` נקרא.

## False positives

- Sentinels מתועדים במפורש בחוזה של הפונקציה (`Optional[User]` עם docstring "None = user not found, raises on transient").
- Local state — `x = None` שלנו זה עתה השמנו, בהקשר שאין בו state חיצוני.
- UI defaults שאין להם השלכות state (`placeholder = "כתובת המייל שלך"`).

## חומרה

CRITICAL — כל instance בבסיס ה-Campaign AI היה real-money או auth (חיוב כפול, מודעה שממשיכה לרוץ, session שנחשב תקף אחרי logout, יום שנחשב פנוי כשהיו אירועים). הדליפה שקטה: הקוד רץ, לא זורק, מחזיר "תקין".

## ראיות

Campaign AI Meta-pattern A (`docs/source-projects/campaign-ai-patterns.md`, 2026-08-31): 7 מופעים בעלי מוצא נפרד — `944b45c` (missing refresh cookie ⟹ no session), `bc71425` (not transient ⟹ token dead), `c0ac42c` (`[]` מ-Google ⟹ no event), `760c84f` (`busy` חסר ⟹ day free), `5deee2f` (`delete` no-op ⟹ deleted), `5813e00` (`raw_campaign=None` ⟹ `leads=0`), `d4a6911` (`trial_ends_at` future ⟹ paid).
