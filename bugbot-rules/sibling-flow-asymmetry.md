# sibling-flow-asymmetry

תיקון של קטגוריה שלמה שהוחל רק על flow אחד מבין sibling flows שעושים עבודה דומה. ה-fix חי בקוד, אבל שלושה sibling handlers שנקראים באותה נשימה נשארו פגיעים — כי הריוויוור אימת רק את הנתיב שהופיע בדיף.

מובחן מ-`linked-field-atomicity.md`: שם המדובר בשדות מקושרים **בתוך אותה ישות** שצריכים להתעדכן יחד. כאן המדובר על **נתיבי קוד עצמאיים** שמבצעים פעולה זהה על ישויות אחרות, וצריכים להתפתח במקביל.

## דווח כשמתקיים אחד מהבאים

1. **דיף שמוסיף guard / validation / cleanup לפונקציה `foo_X`** כשקיימות ב-repo פונקציות `foo_Y`, `foo_Z` עם שם דומה (`*_push`, `handle_*`, `_run_*`, `_process_*`) שלא נגעו בהן.

2. **תיקון error handling לספק חיצוני שהוחל על נתיב אחד.** למשל: `optimization_push` תופס עכשיו `TransientError` נכון; `lead_form_push` / `rejection_push` / `campaign_push` — לא. או הפוך: `campaign_push` הוסיף `TransientError` mixin ל-46 exception classes; ה-nphandlers האחרים משתמשים עדיין ב-tuple ידני.

3. **fix ל-API contract שמכסה קריאה אחת.** `delete_event` תוקן לזרוק `None` כשאין credentials; `list_events_by_appointment_id` נשאר עם `[]` (מסקנה שגויה מנוגדת ב-`inferring-external-state-from-indirect-indicator.md`).

4. **best-effort שהוחל אסימטרית בין branches של אותה פונקציה.** `_today_count` לענף A עטוף ב-try/except; לענף B לא — transient DB error בענף B מפיל את כל ה-flow.

5. **הוסף שדה / עמודה לשאילתה אחת** (למשל: `meta_ad_ids` GIN array מתעדכן ב-`publish_creative` אבל לא ב-`rejection_push`, `optimization_push`, `lead_form_push`) — 4 flows שכותבים אותה ישות אבל רק אחד עודכן.

## תבנית תיקון

- **grep מבוסס-שם** לפני ה-commit: כשמתקנים `foo_push`, לרוץ `git grep -l "def.*_push"` ולעבור ידנית על כל אחד; לתעד ב-PR body איזה sibling flows נבדקו.
- **helper משותף במקום duplication**: אם 4 flows עושים אותו דבר, לחלץ ל-`_common_push_pre_flight()` שמוזרק לכולם. הגורם המניע של הדפוס הוא duplication; המניעה היא לצמצם אותו.
- **בדיקת אי-הפרעה** (contract test): פרמטריזציה על `[optimization_push, lead_form_push, rejection_push, campaign_push]` שמאמתת את ה-guard/cleanup/write על כל אחד.

## False positives

- Sibling flows שהם באמת שונים (למשל `create_*` vs `delete_*`) — התיקון של האחד לא רלוונטי לשני.
- ניסיון-מכוון של rollout הדרגתי: fix חדש נבדק על flow אחד לפני שמוחל על השאר (חייב להיות מתועד ב-PR).

## חומרה

MEDIUM — הבאג לא חדש; הוא היה שם לפני התיקון. אבל **הריגרסיה של התיקון** מזיזה קונטקסט: משתמש שסבל ממנו בעבר יסבור שהוא נעלם, ויגלה שהוא רק זז לצד שני. בפרויקטים עם sibling flows רבים (Campaign AI: 4 push flows, 3 reconcilers, 2 branches של `_today_count`) — זה מקור לשכתוב חוזר של אותה קטגוריה 3-4 פעמים.

## ראיות

Campaign AI Meta-pattern B (`docs/source-projects/campaign-ai-patterns.md`, 2026-08-31): 10+ מופעים במסמך. דוגמאות מרכזיות: `92fba3a` / `4e3f425` (`meta_ad_ids` GIN atomicity ב-4 sibling push flows), `839bb48` (`campaign_push` הוגן, `lead_form_push` לא), `c0ac42c` (`delete_event` תוקן, `list_events` לא), `beee243` (`_today_count` — branch A best-effort, branch B לא), `0403d9d` (`TransientError` mixin ב-`campaign_push` בלבד).
