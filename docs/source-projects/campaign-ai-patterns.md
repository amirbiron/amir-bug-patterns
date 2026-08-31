# אנליזת איכות קוד — Campaign AI

> תאריך: 2026-08-31 | סה"כ באגים מתועדים: **210** (50 MAJOR · 91 MEDIUM · 69 LOW)
> מקור: סריקת **935 commits** (מלוא ההיסטוריה, אחרי `git fetch --unshallow`) + `docs/code-reviews/*`.
> מתוכם **256 commits** הם תיקוני-באג מפורשים; **130** מהם נושאים בכותרת ייחוס לסוקר-אוטומטי (Cursor / Bugbot).
> היקף הקוד הנסרק: 161 קבצי Python (~43,600 שורות), 148 מיגרציות, 108 קבצי-טסט.

**כלל שהנחה את הכתיבה:** כל באג ברשימה נראה בפועל ב-diff או בגוף ה-commit שמתאר את הקוד הישן ואת התיקון.
פריטים שהופיעו במסמכי-הסקירה אך **לא** נמצא להם commit-תיקון בהיסטוריה — לא נכללו (למעט 3 שסומנו במפורש "מתועד").

---

## סיכום דפוסים

| דפוס | כמות | % מסה"כ | דוגמה מרכזית |
|---|---|---|---|
| **לוגיקה עסקית / מקרי קצה** | 35 | 17% | `9733a45` — `current_period_start` נכתב בתחילת ה-trial → 23 ימי גישה חינם למי שביטל ביום 3 |
| **ניהול מצב / concurrency** (race, TOCTOU, check-then-act) | 29 | 14% | `c7b4f08` — advisory lock משתחרר בסוף ה-RPC → שני `approve` מקבילים יצרו 6 מודעות חיות |
| **סיווג שגיאות מספק חיצוני** (transient / permanent / unknown) | 26 | 12% | `bc71425` — logout הסיק "לא transient ⟹ token מת" והחזיר 204 כוזב בזמן שה-session חי |
| **API design** (dead code, כפילות לוגיקה, חוזה לא-עקבי) | 24 | 11% | `8ceaf0b` — רשימת סוגי-ההתראות שוכפלה Python↔SQL → המונה בדשבורד סטה מהאכיפה בפועל |
| **Terminal-state / re-pick אינסופי** (cron + worker) | 23 | 11% | `20ee07c` — `status='failed'` הוציא קמפיין עם orphans מרשת ה-cleanup → spending לנצח ב-Meta |
| **DOM / UI** | 23 | 11% | `d93f77f` — `_enterAppShell` לא הסתיר את ה-hero (`z-index:9999`) → מנוי חוזר ראה מסך-כניסה מעל הדשבורד |
| **תאימות לחוזה ספק חיצוני** (SDK/API/scopes/פורמטים) | 16 | 8% | `4156ba4` — `upload_ad_image` שלח bytes גולמיים; ה-Marketing API דורש base64 → כל ה-push נחסם |
| **ולידציית קלט** | 13 | 6% | `09d397c` — `bool` הוא subclass של `int`: `DebitTotal=true` עבר כסכום של אגורה אחת |
| **עקביות DB** (rowcount, כתיבה חלקית, צורת-תגובה) | 10 | 5% | `9e69ce9` — UPDATE שתפס 0 שורות דווח כהצלחה → מסמך-מס "אבד" ונוצר כפול ב-retry |
| **בטיחות נתונים** (PII, injection, auth, IDOR) | 8 | 4% | `de1507d` — `sign_out(scope='local')` → refresh token גנוב נשאר תקף ~30 יום אחרי logout |
| **סכימת DB / מיגרציות** | 3 | 1% | `2e452f1` — התנגשות שמות constraint בתוך `CREATE TABLE` → ה-deploy הראשון נכשל |
| **async / control flow** | 3 | 1% | `a8e02bf` — `wait_for` לא מבטל thread → ה-SDK השלים את ה-write במקביל ל-retry = double-spend |

> הסכום עולה על 210 בשלושה, כי שלושה באגים משתייכים לשני דפוסים במקביל (מסומנים ב-`+` ברשימה).

**קריאה של הטבלה — שתי מסקנות:**

1. **הנזק אינו מתפלג כמו הכמות.** "לוגיקה עסקית" ו-"DOM/UI" הם הגדולים בכמות, אבל כמעט כל
   הנזק הבלתי-הפיך (כסף שירד פעמיים, לידים אבודים, קמפיינים ששרפו תקציב, גישה חינם) הגיע משלושת
   הדפוסים האמצעיים — **concurrency + סיווג-שגיאות + terminal-state, יחד 78 באגים (37%)**.
2. **לשלושתם שורש אחד:** הקוד הסיק מסקנה על מצב חיצוני מתוך **אינדיקטור עקיף**, במקום לוודא את
   הפעולה בפועל — ואז פעל על המסקנה השגויה. זה בדיוק מה שמפורט בסעיף "דפוסים שקלאוד קוד פספס" למטה.

---

## רשימה מלאה לפי חומרה

### MAJOR

#### 1. logout לא ביטל את ה-session — 6 וריאנטים רצופים
- **בעיה:** `revoke_session` נבנה סביב ה-**access** token, בעוד שמה שצריך להתבטל הוא ה-**refresh** token. שרשרת של שישה באגים נפרדים על אותו קוד: (א) early-return כשאין access token + `except Exception` שבלע הכול (`71004f7`); (ב) `refresh_session` **מסובב** את הטוקן לפני `sign_out` — כשל ב-`sign_out` שבר את ההנחה "טוקן פסול ⟹ session מת" (`779eb56`); (ג) `_raise_if_transient` בלבד → "לא transient ⟹ token מת" → 204 על שגיאת 400 (`bc71425`); (ד) אין refresh cookie → הוסק "אין session" למרות Bearer תקף (`944b45c`); (ה) כשל `set_session` (JWT מזויף עם `exp` עתידי) סווג `TOKEN_INVALID` → 204 ו-`sign_out` לא רץ (`a256d9c`); (ו) `scope='local'` — ברירת-המחדל של supabase-py — ביטלה רק את ה-session הנוכחי (`de1507d`).
- **תוצאה:** משתמש לוחץ "התנתק", מקבל 204, וה-`POST /auth/refresh` שלו ממשיך לעבוד. Refresh token שדלף (XSS / מכשיר משותף / לוג) נשאר תקף ~30 יום. בשילוב עם (ה) — שרשרת takeover מלאה.
- **מקור:** `71004f7`, `779eb56`, `bc71425`, `944b45c`, `a256d9c`, `de1507d`
- **דפוס:** בטיחות נתונים + סיווג שגיאות

#### 2. OAuth password takeover ב-signup
- **בעיה:** `sign_up` קרא ל-Supabase ישירות ללא בדיקה מקדימה. אם ה-email כבר רשום דרך OAuth (Facebook/Google) ו-Supabase מוגדר `auto-link` → signup עם אותו email+סיסמה השתלט על החשבון. ההגנה נשענה **כולה** על הגדרת dashboard — נקודת-כשל יחידה הרגישה ל-config drift.
- **תוצאה:** תוקף שיודע email של משתמש OAuth מקבל שליטה מלאה בחשבון (כולל נכסי Meta והחיובים).
- **מקור:** `7ff65c5` (RPC `email_has_oauth_identity`, migration 0075)
- **דפוס:** בטיחות נתונים

#### 3. OAuth state ניתן ל-replay
- **בעיה:** ה-state היה חתום (HMAC) + nonce + TTL + double-submit cookie, אך **בלי single-use** — אותו זוג `(signed_state, state)` היה ניתן ל-replay בתוך חלון ה-TTL (5 דקות).
- **תוצאה:** שכבת ההגנה האחרונה בשרשרת ה-OAuth הייתה חסרה; replay בתוך החלון היה מייצר session נוסף.
- **מקור:** `c5bed1e` (RPC `consume_oauth_nonce`, migration 0076)
- **דפוס:** בטיחות נתונים

#### 4. 23 ימי גישה חינם אחרי ביטול
- **בעיה:** `activate_trial_with_billing` קבע `current_period_start=now()` **בתחילת** ה-trial. ה-docstring טען מפורשות "אין cps לפני חיוב ראשון" — וה-RPC סתר אותו. משתמש שביטל ביום 3: `cps=day0`, `trial_ends=day7`; ביום 8 ענף ה-grace (`canceled + cps`) חישב `now < add_one_month(day0) = day30` → True.
- **תוצאה:** 23 ימי שירות בתשלום, חינם, לכל מי שביטל בזמן ה-trial.
- **מקור:** `9733a45` (migration 0077)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 5. Double-charge בשדרוג חבילה (race של targets שונים)
- **בעיה:** שני שדרוגים **שונים** מקבילים מאותו old-state קיבלו `idempotency_key` שונה (ה-target חלק מהמפתח) → שני `INSERT` עברו → שני חיובי J4 במקביל. ה-CAS-הכפול ב-`finalize` מנע double-UPGRADE, אבל החיוב השני כבר ירד.
- **תוצאה:** חיוב כפול אמיתי בכרטיס האשראי; ההתאוששות הייתה reactive בלבד (alert + החזר ידני).
- **מקור:** `baa6a16` (partial-unique index, migration 0136)
- **דפוס:** ניהול מצב / concurrency

#### 6. מסמך מס כפול ב-retry חשבוניות
- **בעיה:** `retry_failed_invoices` שלף שורות (`provider_document_id IS NULL`) ב-`select` והריץ `retry_pending_invoice` לכל אחת **בלי claim/lock**. שתי ריצות חופפות ראו את אותה שורה, שתיהן עשו search (0 התאמות) ושתיהן קראו ל-Green Invoice `create` — שאינו idempotent.
- **תוצאה:** שני מסמכי-מס לאותו חיוב — הפרת חוק חשבונית מס; `PCN874` cross-check של מ.ר.ש תופס כפולים.
- **מקור:** `21e425f` (RPC `claim_pending_invoices` + `FOR UPDATE SKIP LOCKED`, migration 0018)
- **דפוס:** ניהול מצב / concurrency

#### 7. חשבונית כפולה בחציית-יום ב-retry
- **בעיה:** `issue_invoice_for_charge` יוצר את המסמך עם `payment_date=now`, אבל `retry_pending_invoice` חיפש יום-בודד לפי `period_start[:10]`. חיוב שמתחיל לפני חצות והמסמך נוצר אחריה → search ביום הלא-נכון → 0 התאמות → יצירה מחדש.
- **תוצאה:** חשבונית כפולה (אותה חשיפה משפטית כמו #6), בתרחיש שקורה מאליו פעם ביום.
- **מקור:** `fe3be60` (0-2#9) — search על טווח `[period_start, today]`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 8. חשבונית לפי המחירון ולא לפי הסכום שחויב
- **בעיה:** אחרי חיוב מוצלח, `_charge_subscription` קרא ל-`issue_invoice_for_charge` עם `amount_ils = amount/100` (מחיר ה-tier), ולא לפי `DebitTotal` — הסכום שעבר בפועל בכרטיס.
- **תוצאה:** חשבונית מס שאינה משקפת את התשלום בפועל (בעיה חוקית) בכל מקרה שבו פלאקארד מחזירה `DebitTotal` שונה מהמבוקש.
- **מקור:** `e541509`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 9. `approve` מקבילי יצר עד 6 מודעות חיות
- **בעיה:** `open_optimization_push_action` השתמש ב-`pg_advisory_xact_lock` שמשתחרר בסוף ה-RPC. שני `approve` מקבילים (double-submit): הראשון עשה `INSERT` ל-action ב-`pushing` ושחרר; השני **מצא** את ה-action ב-`pushing` והחזיר אותו בלי להבחין שמישהו כבר תופס אותו.
- **תוצאה:** שניהם רצו `create_ad ×3` → עד 6 מודעות חיות באותו Ad-Set = תקציב כפול.
- **מקור:** `c7b4f08` (CAS-lease, migration 0079)
- **דפוס:** ניהול מצב / concurrency

#### 10. חסימת דחיות-מודעה לתמיד
- **בעיה:** `rejection_intake` פתח סדרה (`open_optimization_session`) ואז עשה `enqueue` בשני צעדים נפרדים. כשל ב-`enqueue` אחרי שהסדרה נפתחה → סדרה פתוחה בלי job.
- **תוצאה:** `has_open_session` החזיר True לכל webhook הבא → כל דחיית-מודעה עתידית של אותו קמפיין נחסמה **לנצח**, וה-handler מעולם לא רץ.
- **מקור:** `d62c5ee` (RPC `open_meta_rejection_session` — session+job בטרנזקציה אחת, migration 0078)
- **דפוס:** ניהול מצב / concurrency

#### 11. `finalize` שכשל גילגל אחורה swap מוצלח
- **בעיה:** `_handle_failure` ב-`optimization_push` הסתעף על **סוג** השגיאה (transient↔permanent) ולא על **שלב** ה-state. בשלב `finalize` ה-swap כבר בוצע ב-Meta (3 חדשות חיות, ישנות paused), וכל כשל שם הוא כשל DB בלבד. שגיאה לא-transient (`40001` serialization, `40P01` deadlock) → סווגה permanent → rollback.
- **תוצאה:** מחיקת 3 מודעות חיות תקינות + reactivate של הישנות = קמפיין מת בשקט, כסף אבוד.
- **מקור:** `5719dc4` (step-based branching; `839bb48` הוסיף את אותו guard ל-`lead_form_push`)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 12. קמפיינים יתומים ב-Meta ששורפים תקציב
- **בעיה:** `_handle_no_connection` / `_handle_token_unavailable` כתבו `status='failed'` **תמיד** — גם ב-retry שבו כבר נוצרו `meta_campaign_id`/`meta_ad_set_id`. ההערה בקוד הצדיקה "אין מה לנקות (עוד לא נוצר)" — נכון לניסיון ראשון, שגוי ב-retry. `cleanup_stuck_campaigns` סורק רק `pushing`.
- **תוצאה:** campaign + ad_set חיים ב-Meta (live → spending) **לנצח**, מחוץ לרשת המנקה, עד שמישהו ימצא אותם ידנית ב-Ads Manager.
- **מקור:** `20ee07c` (3#1)
- **דפוס:** Terminal-state / re-pick

#### 13. cleanup cron נתקע ולעולם לא ניקה
- **בעיה:** ההשלמה ל-#12: במסלול `_handle_token_unavailable` (secret פגום/יתום ב-Vault), `get_decrypted_token` **זורק** `FbTokenUnavailableError` במקום להחזיר `None`. ה-cron טיפל רק ב-`None` → ה-exception עלה ללולאה → `log+continue` בלי לקדם `cleanup_attempts`.
- **תוצאה:** הקמפיין נשאר `pushing` לנצח, לעולם לא הגיע ל-`failed_rollback_pending` (escalation/Sentry), וה-orphans המשיכו לרוץ.
- **מקור:** `38f402a`
- **דפוס:** Terminal-state / re-pick

#### 14. `wait_for` על `to_thread` → הרצה כפולה של write ל-Meta
- **בעיה:** ה-timeout ב-`_run` היה `asyncio.wait_for(to_thread(fn), 60)`. Python לא מבטל threads — כשה-`wait_for` קופץ, ה-SDK thread ממשיך לרוץ. בנוסף התברר ש-`FacebookSession` נוצר **בלי** `timeout=` → `requests` ממתין לנצח, כך שה-thread נתקע לצמיתות.
- **תוצאה:** ה-runner תופס `MetaTransientError`, עושה retry, וה-thread הזומבי **משלים את ה-write במקביל** → `create_campaign`/`create_ad`/`create_creative` רצים פעמיים = double-spend + orphans.
- **מקור:** `a8e02bf` (socket timeout `(10,60)` ברמת ה-session + watchdog) ; קדם לו `c13eb3d` שהוסיף רק את ה-`wait_for`
- **דפוס:** async / control flow

#### 15. לידים אבודים — מודעות חדשות לא קושרו ל-`campaigns.meta_ad_ids`
- **בעיה:** ה-webhook של Meta מאתר קמפיין דרך `find_by_ad_id` (`GIN @>` על `campaigns.meta_ad_ids`). **ארבעה** flows שיוצרים מודעות חדשות לא עדכנו את המערך: `publish_creative` (Ad רביעי), `rejection_push` (ה-fix Ad), `optimization_push` (creative-swap), `lead_form_push` (screening).
- **תוצאה:** כל ליד שמגיע מהמודעה החדשה → `find_by_ad_id` מחזיר None → orphan → **ליד אבוד**. בנוסף: דחייה של אותה מודעה לא זוהתה, ו-Insights פר-מודעה נשברו.
- **מקור:** `0965efb`, `71a7032` (RPC `replace_campaign_meta_ad_ids`, migration 0068), `5f8c80f`, `9b6712c`, ו-`03be86b` (ה-RPC עשה `return` שקט על קמפיין חסר → ה-caller המשיך כאילו הצליח)
- **דפוס:** עקביות DB

#### 16. Double-booking בתיאום תורים (שני שורשים)
- **בעיה א':** `idx_appointments_active_slot` היה partial-UNIQUE על `(user_id, preferred_date, preferred_time)` — תופס רק start-time **זהה**. עם duration 60 דק' מול grid של 30 דק', תור 10:00–11:00 ותור 10:30–11:30 חופפים בפועל אבל עוברים את ה-UNIQUE. בנוסף ה-flow עשה `gather_and_decide` ואז `create_appointment` בשני צעדים → race בין הבדיקה ל-INSERT.
- **בעיה ב':** Google FreeBusy מחזיר HTTP 200 גם כשיש תקלת-יומן — כ-`{calendars:{id:{errors:[...]}}}` **בלי** `busy`. הקוד עשה `entry.get("busy", [])` → קיבל `[]` → פירש "כל היום פנוי".
- **תוצאה:** שני לקוחות מקבלים את אותו תור. בבעיה ב' — ה-picker הציע slots **מעל אירועים אמיתיים** ביומן.
- **מקור:** `9910cea` (`EXCLUDE USING gist` על `tsrange`, migration 0080) ; `760c84f` (fail-closed על `errors`)
- **דפוס:** ניהול מצב / concurrency + סיווג שגיאות

#### 17. `upload_ad_image` שלח bytes גולמיים במקום base64
- **בעיה:** ה-SDK מגדיר `param_types['bytes'] = 'string'` ושולח את ה-params as-is; ה-Marketing API מצפה ל-base64-encoded string.
- **תוצאה:** העלאת התמונה ב-push נכשלה **תמיד**, גם עם URL וטוקן תקינים — כלומר כל זרימת יצירת-הקמפיין הייתה חסומה בשלב ה-Ad.
- **מקור:** `4156ba4`
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 18. gpt-5.x דחה `max_tokens` — כל קריאות ה-LLM נכשלו
- **בעיה:** המודלים החדשים דוחים את `max_tokens` ב-`400 unsupported_parameter`. כל קריאות ה-chat (copy / agent / diagnose / bot) נכשלו.
- **תוצאה:** יצירת קופי, אבחון-הסוכן והבוט — כולם מתו ברגע שהמודל עודכן ל-gpt-5.2.
- **מקור:** `df2a767` (`max_completion_tokens`), `d32a05e` (seam מסתגל שמסיר פרמטר שנדחה ולומד פר-מודל), `8298aea` (allowlist — לא להסיר `response_format` שהשמטתו שוברת JSON-parsing), `6f03c0f` (החזרת `temperature` ל-fail-loud אחרי שהוסר בטעות בשקט)
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 19. Gemini החזיר טקסט במקום תמונה
- **בעיה א':** ה-payload של `generate_image`/`edit_image` לא כלל `generationConfig.responseModalities` → Nano Banana החזיר **תיאור מילולי של התמונה** במקום התמונה, בלי `inlineData`.
- **בעיה ב':** `image_generation.txt` הוא meta-prompt ("כתוב image-prompt, החזר רק טקסט"). gpt-image (image-only) סלחני ומצייר לפי ה-concept; Gemini (multimodal) **מציית** להוראה ומחזיר טקסט.
- **תוצאה:** מודעות ללא תמונה בכל הזרימה שעברה ל-Gemini.
- **מקור:** `939c596`, `6e4ebcc` (flow דו-שלבי: gemini-text מייצר image-prompt → Nano Banana מצייר)
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 20. connection flooding ל-Supabase (~75 חיבורים/שנייה)
- **בעיה:** `get_admin_client` ו-`get_user_client` קראו ל-`create_client` **חדש בכל קריאה** — אין singleton. כל קריאת DB (worker claim, cron tick, handler, service) פתחה client + חיבור TLS חדש.
- **תוצאה:** לוגי Postgres הראו עשרות "connection received/authenticated" בשנייה — סיכון ממשי להשעיית הפרויקט.
- **מקור:** `7c24085` (`@lru_cache` singleton ל-admin; user client נשאר per-request כי הוא מצמיד JWT)
- **דפוס:** ניהול מצב

#### 21. `/health` שרף 20–40GB egress בחודש
- **בעיה:** Render מריץ health-check כל ~5 שניות; `/health` קרא ל-`check_connection` שעושה `GET /rest/v1/` (root) — שמחזיר את **כל ה-OpenAPI schema** של PostgREST (עשרות KB) בכל קריאה.
- **תוצאה:** ~12–24 קריאות/דקה × schema כבד = חריגה מ-quota ה-free (5GB). liveness probe שבודק DB הוא גם שגוי מהותית — restart של ה-web לא מתקן Supabase down.
- **מקור:** `9dff809` (הפרדת liveness מ-readiness)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 22. Ad חי נמחק ב-rollback אחרי `record` מוצלח
- **בעיה:** אחרי המעבר ל-save-as-you-go, ברגע ש-`_record_published_ad` הצליח ה-Ad כבר חי ו-committed. כשל מאוחר ב-`_link_published_ad` הפעיל `_handle_publish_failure` → `_rollback_meta` — שמחק את ה-Ad. `published_ad_id` נשאר set.
- **תוצאה:** ה-resume ב-idempotent-return קישר Ad **מחוק**: הפרסום נראה מוצלח בעוד ה-Ad איננו, וה-asset נתקע.
- **מקור:** `6b17244` (invariant: `published_ad_id` set ⟹ ה-Ad חי)
- **דפוס:** ניהול מצב

#### 23. crash בין `create_ad` ל-`finalize` → חריגת-מכסה + Ad untracked
- **בעיה:** `published_ad_id` נכתב רק ב-`finalize` (RPC עם 3 פעולות, אחרי `create_ad`). crash בחלון ביניהם השאיר `published_ad_id=NULL` וה-Ad `ACTIVE` ב-Meta בלי record.
- **תוצאה:** `creative_quota_counts` (TTL) שחרר את ה-slot → חריגה מ-15 + Ad שלא נמצא בשום מעקב.
- **מקור:** `9ac222c` (פיצול ל-`_record_published_ad` מיד אחרי `create_ad` + `_link_published_ad`)
- **דפוס:** ניהול מצב

#### 24. TTL re-claim שכפל Ads
- **בעיה:** `reserve_creative_publish` ספר `published_at IS NOT NULL` כ-slot תפוס, וה-CAS תפס רק `published_at IS NULL`. crash בין reserve ל-create/release השאיר `published_at` set + `published_ad_id` NULL **לנצח**.
- **תוצאה:** ה-CAS לא יכול היה ל-re-claim, ה-count המשיך לספור, וה-API החזיר 409 לנצח. בגרסה מאוחרת יותר ה-TTL re-claim עצמו שכפל Ads.
- **מקור:** `3a24128` (TTL recovery, migration 0066), `aa9fabf` (ביטול ה-re-claim הכפול)
- **דפוס:** ניהול מצב

#### 25. חריגה ממכסות Creative (check-then-act)
- **בעיה:** `assert_quota` קרא את ה-COUNT פעם אחת לפני `generate`/`publish`; בקשות מקבילות של אותו user ראו את אותו headroom וכולן המשיכו.
- **תוצאה:** חריגה מ-15 יצירות/פרסומים בחלון — עלות OpenAI ו-Meta אמיתית מעבר למה שהלקוח שילם עליו.
- **מקור:** `121d78e` (2 RPCs אטומיים תחת advisory lock, migration 0064), `9580efd` (ה-COUNT סופר גם reserves in-flight)
- **דפוס:** ניהול מצב / concurrency

#### 26. מכסת צ'אט: לא נאכפה ב-trial + race
- **בעיה א':** basic/premium ב-trial (`current_period_start=NULL`) קיבלו `used=0` תמיד → מכסת ה-50 לא נאכפה כלל.
- **בעיה ב':** ה-quota נבדק ב-read לפני OpenAI וה-INSERT היה מאוחר, בלי guard אטומי.
- **תוצאה:** צריכת OpenAI בלתי-מוגבלת ב-trial; שליחות מקבילות ליד הגבול חרגו מ-50.
- **מקור:** `8222ed9` (ה-RPC `insert_user_and_assistant_messages` עושה advisory lock + COUNT)
- **דפוס:** ניהול מצב / concurrency

#### 27. Early-IPN → trial משולם נתקע בשקט
- **בעיה:** IPN של פלאקארד שמגיע לפני שמירת `confirmation_key`. שלוש גרסאות: (א) `session_data.get("confirmation_key","")` החזיר `None` (המפתח קיים עם ערך None) → `None.encode()` זרק `AttributeError` ושבר את חוזה ה-200 (`3723385`); (ב) ה-handler עשה `return` שקט וה-router החזיר 200 — פלאקארד לא עושה retry על 200 (`9231f7a` הוסיף Sentry); (ג) התיקון השורשי — reserve-before-fill: זריקת `BillingWebhookRetryError` → 500 → פלאקארד תשלח שוב (`461cb62`).
- **תוצאה:** לקוח **שילם**, ה-trial לא הופעל, ה-subscription נתקע ב-`trial` עם `billing_customer_id=NULL`.
- **מקור:** `3723385`, `9231f7a`, `461cb62` (0-2#11)
- **דפוס:** Terminal-state / re-pick

#### 28. גישה לפיצ'רים בתשלום בלי סליקה — 4 וריאנטים
- **בעיה:** `has_paid_access` החזיר True לכל `status='trial'` (`78a04f8`); התעלם מפקיעת `trial_ends_at` (`ccb47eb`); נתן גישה לכל `trial_ends_at` עתידי **בלי לבדוק status** — כך `expired`/`pending` קיבלו גישה (`d4a6911`); ו-`is_new_trial` בדק `status='trial'` בלי `trial_ends_at` → trial-legacy שפג קיבל גישה (`9fc73dd`).
- **תוצאה:** פיצ'רים בתשלום נפתחו למי שלא שילם, בכמה מסלולים שונים.
- **מקור:** `78a04f8`, `ccb47eb`, `d4a6911`, `9fc73dd`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 29. `start_trial_with_billing` בלי בדיקת status
- **בעיה:** הפונקציה בדקה `tier` ו-`billing_customer_id` אך לא `status`.
- **תוצאה:** משתמש `canceled`/`expired`/`active` יכול היה לפתוח iframe תשלום ו**לדרוס מנוי קיים**.
- **מקור:** `e1b17e4`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 30. חיוב אוטומטי במקום opt-in — סטייה מהאפיון
- **בעיה:** הקוד מימש auto-renew (חיוב אוטומטי כל 30 יום אחרי אשראי ראשון) בניגוד ל-`BILLING_MODEL_CHANGE_PLAN §4.3` שדורש **opt-in** — חיוב רק אחרי אישור מפורש.
- **תוצאה:** גביית כסף על תקופה שהלקוח לא אישר, בסתירה למסמך-האפיון המחייב.
- **מקור:** `d32fd67` (migration 0142: `renewal_approved_cycle_end` + RPC `approve_campaign_renewal`)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 31. המילה "מאשר" בצ'אט הפעילה חיוב
- **בעיה:** `_chatDispatch` ניתב `'מאשר'` → `runBudgetAction('approve')` לפי התאמת-**טקסט גולמית**, בלי לוודא ש-preview הוצג.
- **תוצאה:** הקלדה/הדבקה של מילה נפוצה בשיחה על קמפיין infeasible הייתה מעדכנת תקציב ב-Meta ורושמת הסכמה — בעקיפת ה-double-confirm.
- **מקור:** `a23838e` (דגל-אישור חד-פעמי `CHAT.budgetConfirm` שעולה רק כשהשרת מחזיר צ'יפ `confirm_raise`)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 32. IDOR — reuse של תמונה ממודעה של לקוח אחר
- **בעיה:** `push_rejection_fix` טען את המודעה הנדחית דרך `fetch_ad_by_meta_id` (admin, ללא סינון user) והשתמש ב-`image_url` שלה — בלי לאמת שהשורה שייכת לקמפיין/למשתמש של הסדרה. הבעלות נאכפה רק ב-webhook, לא ב-push.
- **תוצאה:** `starting_metric.ad_id` לא-תואם מאפשר להעלות תמונה וקופי של לקוח אחר תחת ה-page/account הנוכחי.
- **מקור:** `2f7cd4a`
- **דפוס:** בטיחות נתונים

#### 33. `ConfirmationKey` נחשף ל-client
- **בעיה:** `StartBillingResponse` החזיר את `confirmation_key` ללקוח. לפי SKILL של פלאקארד זהו סוד server-side לאימות ה-IPN בלבד.
- **תוצאה:** חשיפתו מאפשרת זיוף callback של תשלום.
- **מקור:** `16e4741`
- **דפוס:** בטיחות נתונים

#### 34. PKCE verifier אבד → חיבור יומן-גוגל מעולם לא עבד
- **בעיה:** `google-auth-oauthlib ≥1.0` מפעיל PKCE אוטומטית; הקוד בנה `Flow` **חדש בכל רגל** — ה-`code_verifier` של רגל ה-start נזרק עם ה-instance, וה-exchange שלח `verifier=None`.
- **תוצאה:** `invalid_grant` על **כל** ניסיון חיבור, מהיום הראשון. זה ההסבר ל"מעולם לא עבד" — ה-config היה תקין כל הזמן.
- **מקור:** `64f6a46` (ה-verifier נצרף ל-state cookie החתום)
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 35. scope חסר → "לא נמצא עמוד עסקי"
- **בעיה:** שלושה שורשים רצופים באותה זרימה: (א) `OAUTH_SCOPES` כלל `pages_manage_ads` — scope deprecated ש-Meta **דוחה** (`Invalid Scopes`) וחוסם את כל הדיאלוג (`3814a2e`); (ב) חסר `pages_show_list` הנדרש ל-`/me/accounts` → Meta החזירה רשימה **ריקה, לא שגיאה** (`adbe63f`); (ג) דפים תחת Business Portfolio דורשים `business_management`, ובלי `auth_type=rerequest` מטא מדלגת על מסך בחירת-הדפים בחיבור חוזר (`e5d5bb0`).
- **תוצאה:** משתמש עם דף עסקי תקין נחסם ב-onboarding עם הודעה מטעה.
- **מקור:** `3814a2e`, `adbe63f`, `e5d5bb0`
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 36. `GRANT` חסר — RLS לבד לא חושף ל-Data API
- **בעיה:** המיגרציה הפעילה RLS + policy SELECT אך לא נתנה `GRANT` ל-role `authenticated`. PostgREST בודק הרשאת **טבלה** לפני RLS, ו-Supabase כבר לא חושפת אוטומטית טבלאות `public` חדשות.
- **תוצאה:** `GET /me/subscription` היה נכשל ב-`permission denied` בפרודקשן, גם כשה-RLS היה מתיר את השורה.
- **מקור:** `618dcce`
- **דפוס:** סכימת DB / מיגרציות

#### 37. התנגשות constraint — ה-deploy הראשון נכשל
- **בעיה:** ב-`CREATE TABLE` של `bot_messages`, לעמודה `direction` היה inline check שמקבל שם אוטומטי `bot_messages_direction_check`, **וגם** named constraint מפורש באותו שם.
- **תוצאה:** כשל בכל ריצה ראשונה (לא רק re-run) — "check constraint already exists". הטסטים לא תפסו כי הם ממקקים את ה-DB ולא מריצים SQL.
- **מקור:** `2e452f1`
- **דפוס:** סכימת DB / מיגרציות

#### 38. הבוט לעולם לא פנה לליד Premium
- **בעיה:** ה-`enqueue` של job פתיחת-הבוט היה נפרד (best-effort) **אחרי** שמירת הליד. אם נכשל / התהליך נעצר — `webhook_events` כבר נרשם, ו-Meta redelivery יצאה מוקדם ב-`_already_processed`.
- **תוצאה:** ליד Premium שמור ב-DB, והבוט מעולם לא פנה אליו.
- **מקור:** `066db8f` (ה-job עבר לתוך `insert_lead_and_event` RPC — אטומי עם leads+event)
- **דפוס:** ניהול מצב / concurrency

#### 39. לידים נזרקו על טוקן יתום ב-Vault
- **בעיה:** ב-`lead_intake_service`, `except FbServiceError` יחיד תפס גם `FbTokenUnavailableError` (permanent — אנומליית integrity), גם `FbConnectionUnavailableError` (transient) וגם `UnexpectedFbConnectionError` (unknown).
- **תוצאה:** בגרסה אחת — 500 ו-Meta ניסתה שוב **לנצח** על מצב בלתי-הפיך; בגרסה אחרת — ליד אמיתי נזרק (200) על תקלה שאולי חולפת.
- **מקור:** `ae6ee77`, `af07a9f` (פיצול לשלושה ענפים מפורשים, subclass לפני base)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 40. `_is_transient` עם tuple ידני → rollback על תקלת DB חולפת
- **בעיה:** `execute_push` קורא בתוך ה-try גם ל-`quiz_service`/`lead_form_service`/`ad_generation` (LLM), אבל `_is_transient` השתמש ב-tuple ידני של 4 טיפוסים בלבד. אותו דפוס חזר ב-`optimization_push` (שגם `lead_form_push` מייבא ממנו).
- **תוצאה:** תקלת DB חולפת מ-quiz/lead_form סווגה permanent → `_handle_failure` עשה **rollback** ומחק entities תקינים ב-Meta במקום להישאר `pushing` ל-resume.
- **מקור:** `0403d9d`, `839bb48` — ובהמשך התיקון השורשי `df301ec`+`dba09e9` (mixin `TransientError` ל-46 מחלקות, `isinstance` במקום tuple)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 41. תמונות: signed URL של 7 ימים ב-3 אתרי-מיחזור
- **בעיה:** `image_url` שמר signed URL זמני. אחרי שפג: קישורי הגלריה נשברו, ו-`_download_image` ב-push הוריד את אותו URL שפג. `campaign_push` תוקן, אבל 3 אתרי-המיחזור (`optimization`/`lead_form`/`rejection`) נשארו עם הורדה גולמית.
- **תוצאה:** push שנדחה (transient retry / draft שהמתין) אחרי 7+ ימים קיבל 403 → **retry-loop נצחי**.
- **מקור:** `8c8cd81` (שמירת path + signing on-read), `4e3f425` (migration 0087), `69d622c` (`image_url_resolver` משותף)
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 42. per-ad Insights ריק לחלוטין
- **בעיה:** ה-push כתב את מזהי ה-Ads רק ל-`campaigns.meta_ad_ids[]`; ל-`ads.meta_ad_id` **מעולם לא** נכתב ערך. `_build_ads_insights` עושה iteration על DB ads ו-`continue` כש-`meta_ad_id` אינו str.
- **תוצאה:** דילוג על **כל** ה-ads → per-ad insights ריק לקמפיינים live, ו-`sum(per-ad)` שבור.
- **מקור:** `6fcdb42`, `92fba3a` (העברת ה-linkage לאחרי הלולאה כדי לא להגדיל את חלון ה-orphan)
- **דפוס:** עקביות DB

#### 43. Insights: `leads=0` כוזב
- **בעיה:** שלושה שורשים: (א) empty path (`raw_campaign=None` — עיכוב aggregation ב-Meta) החזיר `leads=0` ודילג על ספירה מ-DB, למרות שהליד כבר שם (`5813e00`); (ב) `_count_whatsapp_leads` ספר `action_type` יחיד מתוך שני ווריאנטים (`4e3f425`); (ג) `facebook-business` עלול להחזיר פריט action כ-`AbstractCrudObject` ולא `dict`, וה-counter מדלג על non-dicts (`ba83880`).
- **תוצאה:** קמפיין WhatsApp הציג 0 לידים למרות spend ולידים אמיתיים; ה-CPL של המוניטור חושב על נתון שגוי.
- **מקור:** `5813e00`, `4e3f425`, `ba83880`
- **דפוס:** עקביות DB + תאימות לחוזה ספק

#### 44. worker: 3 retries מלאים לכל exception
- **בעיה:** ה-runner נתן 3 retries גם ל-`ValueError` על payload פגום וגם ל-`MetaPermanentError` (token נמחק). ה-handlers **כבר** סיווגו שגיאות — ה-runner התעלם.
- **תוצאה:** רעש Sentry ×3, השהיה של 5+5 דקות לפני `failed`, והסתרה של באגים אמיתיים.
- **מקור:** `85640b3` (`HANDLER_TRANSIENT`), ובהמשך `dba09e9` (mixin)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 45. AsyncOpenAI בלי timeout → ה-worker נתקע
- **בעיה:** `AsyncOpenAI` נוצר בלי `timeout=`; קריאה שלא מסתיימת חוסמת את ה-worker היחיד 10–30 דקות.
- **תוצאה:** התור כולו נעצר. הבעיה החמירה כש-`_with_retry` תפס רק `RateLimitError` — `APIConnectionError`/`APITimeoutError` נכשלו מיד בלי backoff.
- **מקור:** `1d35a60`, `60ee35b` (הסיווג היה dead code — ה-seams תפסו את ה-exceptions לפני ש-`_with_retry` ראה אותם)
- **דפוס:** async / control flow

#### 46. `job` נתקע ב-`running` לנצח
- **בעיה:** אחרי סיום ה-handler, `process_job` כתב את ה-status הסופי דרך `_update_job` שהיה best-effort — רשם כשל DB ולא ניסה שוב. `claim_next_job` תופס רק `pending`.
- **תוצאה:** ה-job נשאר `running` לנצח — בלי retry, בלי השלמה, ובמקרה ההצלחה גם בלי שום עקבה; משתמש ב-polling רואה `running` עד אינסוף.
- **מקור:** `14b65af` (retry חסום + `capture_exception` על כשל מלא)
- **דפוס:** Terminal-state / re-pick

#### 47. `_enterAppShell` לא הסתיר את ה-hero
- **בעיה:** `_enterAppShell` הציג את `app-shell` אבל **לא** הסתיר את ה-hero (`position:fixed; z-index:9999`). הזרימה החדשה `_hydrateAndRoute→_enterAppShell` לא עברה דרך `selectAccess` שהוא היחיד שהסתיר.
- **תוצאה:** משתמש-מנוי שהתחבר או ריענן חזר למסך "כנס למערכת" ולא התקדם — ה-overlay כיסה את הדשבורד לגמרי. פגע גם בכל ה-deep-links.
- **מקור:** `d93f77f`
- **דפוס:** DOM / UI

#### 48. ניתוב ותצוגה לפי state מקומי במקום מצב-השרת
- **בעיה:** הממשק ניתב והציג לפי `APP` (in-memory, נמחק בכל load) ולא לפי `GET /me/subscription`.
- **תוצאה:** login/refresh של משתמש-מנוי → wizard מחדש (+ `PATCH /me/subscription` 409); "החבילה שלי" לא-עקבי; VIP תמיד כבוי; מחיר בבחירת-חבילה נתקע.
- **מקור:** `33b8a7b` (`_hydrateAndRoute`)
- **דפוס:** DOM / UI

#### 49. בחירת נכסי-Meta לא שרדה re-login
- **בעיה:** בחירת חשבון-המודעות/הדף/מספר-WA הייתה frontend-only (`APP.account`/`page`/`waNumberId`) ונמחקה בכל page-load; לא היה persistence server-side לפני יצירת קמפיין.
- **תוצאה:** משתמש שחיבר חשבון ודף, יצא וחזר — נחסם ב-wizard עם "יש להשלים חיבור Meta". פגע גם במסלול WhatsApp.
- **מקור:** `edf0dc0` (migration 0146 — הרחבת `onboarding_draft`)
- **דפוס:** DOM / UI

#### 50. `deep-link` של התורים התנגש עם ה-API route
- **בעיה:** הקישור `{frontend_url}/appointments` בהתראת-הבעלים התנגש עם `GET /appointments` (רשימת התורים), הרשום **לפני** ה-SPA mount.
- **תוצאה:** ניווט-דפדפן החזיר JSON/401 במקום את ה-SPA, ו-`_handleAppointmentDeepLink` מעולם לא רץ.
- **מקור:** `6a2987e` (מעבר ל-`/my-appointments`)
- **דפוס:** DOM / UI

---

### MEDIUM

#### 51. `classify_auth_error` — fallback ל-`SERVICE_DOWN` במקום `UNKNOWN`
- **בעיה:** ה-fallback של המסווג המרכזי החזיר `SERVICE_DOWN` ("ברירת מחדל בטוחה: transient") לשגיאה לא-מזוהה.
- **תוצאה:** transient הוא ברירת-מחדל **אקטיבית** — מפעיל retry אוטומטי ומסתיר bugs ותגובות לא-צפויות מ-Supabase מאחורי 503.
- **מקור:** `db361d9`
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 52. signup מיפה כל שגיאה ל-409 "email קיים"
- **בעיה:** אחרי בדיקות transient, כל `AuthError` שאינו weak-password מופה ל-409.
- **תוצאה:** `signup_disabled` / captcha / דומיין חסום כולם הופיעו כ"האימייל כבר רשום" — הודעה מטעה שמסתירה את התקלה האמיתית.
- **מקור:** `779eb56` (מיפוי לפי **קוד** Supabase בלבד; לא-מזוהה → 500)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 53. signup עם email קיים הציג "מייל נשלח" כוזב
- **בעיה:** Supabase מחזיר fake-success (הגנת user-enumeration): `session=None`, `user!=None`, אבל `identities=[]` — בלי לשלוח מייל.
- **תוצאה:** המשתמש קיבל "שלחנו מייל אישור" והמתין למייל שלא נשלח מעולם.
- **מקור:** `dd1d921`
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 54. `classify_meta_error` מיפה כל שגיאה ל-"חבר מחדש"
- **בעיה:** שני שלבים: (א) `classify_meta_request_error` העביר `has_err=True` תמיד → כל שגיאת SDK לא-transient הפכה ל-`MetaPermanentError` → `fb_token_invalid`; (ב) התיקון הראשון נשען על `type=="OAuthException"`, אבל Meta מחזירה אותו גם לשגיאות הרשאה/scope עם קודים לא-auth (200/294).
- **תוצאה:** שגיאת permissions/config הציגה למשתמש "חבר מחדש" בזמן שהטוקן תקין — מיפוי כוזב שמסתיר את הבעיה האמיתית.
- **מקור:** `e53c38c`, `67b58c6` (סיווג לפי `code` בלבד; כל השאר → UNKNOWN/500)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 55. `delete_entity` התייחס לכל `code 100` כ-not-found
- **בעיה:** code 100 ב-Meta הוא גנרי ("Invalid parameter" ועוד) ומשמש לשלל כשלים.
- **תוצאה:** כשל delete אמיתי נבלע כ-"success" → ה-rollback הניח בטעות שהמשאב הוסר, והשאיר entity חי ב-Meta.
- **מקור:** `9231f7a` (דורש `code 100 + subcode 33`)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 56. `mark_token_expired` זרק `APIError` גולמי במקום `TransientError`
- **בעיה:** `mark_token_expired(best_effort=False)` עשה bare raise של `APIError`/`httpx.HTTPError` על בליפ DB. ה-runner עושה retry רק על `isinstance(exc, TransientError)`.
- **תוצאה:** ה-job נכשל מיידית, `refresh_failed_at` נשאר NULL, וה-cron היומי ירה job חדש **לנצח** (re-enqueue אינסופי).
- **מקור:** `eac70b1` (6.1#2)
- **דפוס:** Terminal-state / re-pick

#### 57. `TransientError` mixin סומן בעיוורון לפי שם
- **בעיה:** שתי מחלקות סומנו כ-transient לפי קונבנציית `*UnavailableError` למרות שהן permanent: `CalendarUnavailableError` ("יומן לא מחובר" — דורש פעולת משתמש) ו-`BillingTokenUnavailableError` (Vault token יתום).
- **תוצאה:** retry אוטומטי על מצב שדורש פעולת-אדם — בדיוק הסיכון שכלל 11 מצביע עליו.
- **מקור:** `8236fb0`
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 58. קלאס SQLSTATE 40 סווג כולו transient
- **בעיה:** נוסף prefix `"40"` ל-`_TRANSIENT_SQLSTATE_PREFIXES`, אבל רק `40001` (serialization_failure) ו-`40P01` (deadlock) הם transient. `40003` (statement_completion_unknown) במיוחד מסוכן — התוצאה לא ידועה, retry עלול לכפול פעולה.
- **תוצאה:** 503 + retry על טרנזקציה שנכשלה לצמיתות, בכל השירותים שנשענים על `is_transient_apierror`.
- **מקור:** `f2b866d` (allowlist מפורש `{"40001","40P01"}`)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 59. `get_user_email_by_id` בלע כל שגיאה ל-`None`
- **בעיה:** תקלת Supabase auth חולפת נראתה זהה ל"אין email". `handle_send_notification` התייחס ל-`None` ככשל סופי (`mark_failed`).
- **תוצאה:** תקלה חולפת **איבדה את ההתראה לצמיתות** בלי retry.
- **מקור:** `b21ae92` (סיווג דרך `classify_auth_error` המרכזי)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 60. `send_notification` — permanent סווג כ-transient
- **בעיה:** `handle_send_notification` זרק `ValueError` על type לא מוכר / `user_id` חסר; ה-runner מתייחס לכל זריקה כ-transient.
- **תוצאה:** retries מיותרים, ובסוף `job=failed` בזמן ש-`sent_notifications` נשאר `pending` **לנצח** — אף אחד לא קרא ל-`mark_notification_failed`.
- **מקור:** `36b433a`
- **דפוס:** Terminal-state / re-pick

#### 61. בוט: `NotConfigured` גרר retry אינסופי
- **בעיה:** `MetaWhatsAppNotConfiguredError` (חסר `META_WABA_ID`/`ACCESS_TOKEN`) נתפס ב-`except` הבסיסי → `BotSendTransientError` → retry עד מיצוי. אבל retry לא יכול לתקן config גלובלי חסר.
- **תוצאה:** מיצוי retries, ואז `send_failed` — הריגת שיחה עם ליד אמיתי בגלל misconfig בר-תיקון.
- **מקור:** `ecddc26` (skipped + `capture_alert`), `7892036` (guard מרוכז `_whatsapp_sends_enabled` + alert edge-triggered)
- **דפוס:** Terminal-state / re-pick

#### 62. שיחות בוט נתקעו `active` בלי terminal — 3 וריאנטים
- **בעיה:** (א) query ה-abandon סינן `followup_sent_at IS NOT NULL` → שיחה שה-follow-up שלה דולג/נכשל לא הגיעה ל-abandon; (ב) pending-init permanent קרא `clear_pending_initial` אך לא `mark_send_failed`; (ג) pending-init רץ רק כשה-flag דלוק.
- **תוצאה:** שיחות תקועות `active` **לנצח** + re-select בכל tick של ה-cron.
- **מקור:** `24c64b5`
- **דפוס:** Terminal-state / re-pick

#### 63. `run_tick` נפל כולו על כשל guard → abandon לא רץ
- **בעיה:** `run_tick` קרא ל-`_whatsapp_sends_enabled()` (שיכול לזרוק transient) **לפני** `_run_abandons`.
- **תוצאה:** כשל ה-guard הפיל את כל ה-tick, ו-abandon (safety-net של DB בלבד) לא רץ → שיחה תקועה 48h חוסמת contact לנצח.
- **מקור:** `9aefb1b`
- **דפוס:** Terminal-state / re-pick

#### 64. מוניטור אופטימיזציה — "skipped" בלי לסגור action
- **בעיה:** שגיאה permanent/unknown במדידה הוחזרה כ-"skipped" וה-action נשאר `due`.
- **תוצאה:** ה-fetch בחר אותו **כל שעה**, ו-`capture_exception` ירה כל שעה — re-pick אינסופי + רעש Sentry.
- **מקור:** `095f8f9` (7.4#3 — permanent/unknown → terminal `escalated`)
- **דפוס:** Terminal-state / re-pick

#### 65. `push` תקוע ב-`pushing` → over-spend בלי חלון מדידה
- **בעיה:** כשל transient באמצע ה-push השאיר את ה-action ב-`push_status='pushing'` בלי מנגנון שיחזור אליו אם ה-client ויתר.
- **תוצאה:** מודעות חדשות + ישנות חיות יחד, בלי חלון מדידה — over-spend שקט.
- **מקור:** `095f8f9` (7.4#7 — `reconcile_stuck_pushes` שעתי)
- **דפוס:** Terminal-state / re-pick

#### 66. `reconcile_stuck_pushes` — CAS לפני escalate
- **בעיה:** ה-CAS ל-`push_failed` (ה-marker שמוציא את השורה מה-re-selection) רץ **לפני** `escalate_session`. אם escalate זרק — ה-exception הפיל את הלולאה.
- **תוצאה:** ה-action כבר `push_failed` (לא ייבחר שוב לעולם), ה-session לא escalated → ה-swap החי ב-Meta ממשיך לשרוף תקציב **בשקט**, בלי manual-review ובלי alert.
- **מקור:** `a75ab3b` (reserve-first / commit-last + per-row try/except)
- **דפוס:** Terminal-state / re-pick

#### 67. GCal reconciler — permanent/unknown → re-pick אינסופי
- **בעיה:** `_reconcile_forward`/`_reconcile_reverse` תפסו רק `_RECONCILER_TRANSIENT`. permanent/unknown התפשטו ל-`reconcile_orphans` → `capture_exception` per-row בכל tick, וה-row לא השתנה.
- **תוצאה:** אותו orphan נבחר שוב כל שעה — re-pick אינסופי + רעש Sentry.
- **מקור:** `b64ff5c` (tuple `_RECONCILER_PERMANENT` מקביל + alert מצרפי אחד ל-tick)
- **דפוס:** Terminal-state / re-pick

#### 68. GCal reconciler — env חסר גלובלית טופל per-row
- **בעיה:** כש-env של Google חסר, `get_credentials` זורקת `GoogleNotConfiguredError` על **כל** appointment → נפילה ל-outer except → `capture_exception` per-row בכל tick.
- **תוצאה:** הצפת Sentry על תנאי גלובלי (פיצ'ר כבוי לכולם), שהיה צריך להיות skip שקט של ה-tick כולו.
- **מקור:** `1c713a9` (guard `is_configured()` בראש ה-tick)
- **דפוס:** Terminal-state / re-pick

#### 69. GCal — `delete_event` שדולג נחשב כהצלחה
- **בעיה:** `delete_event` עשה no-op כש-`get_credentials` מחזיר `None` (אין חיבור), אבל ה-reconciler התייחס לזה כהצלחה **וניקה** את `google_event_id` ב-DB.
- **תוצאה:** לקוח שניתק את Google — ה-orphan נשאר חי ביומן **בלי קישור ב-DB**, בלתי-ניתן לאיתור עתידי.
- **מקור:** `5deee2f` (`delete_event → bool`)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 70. GCal — `[]` פורש כ"אין event" גם כשאין credentials
- **בעיה:** האסימטריה המשלימה ל-#69: `list_events_by_appointment_id` החזיר `[]` גם כש-`get_credentials` הוא `None`, וה-reconciler פירש זאת כ-`forward_lost`.
- **תוצאה:** כל לקוח מנותק קיבל alerts כוזבים על "orphans unresolved".
- **מקור:** `c0ac42c` (`list[dict] | None`; `None` = skipped)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 71. GCal — reverse query על ענף מת
- **בעיה:** ה-query כלל `'rejected'` ב-status filter אבל דרש `cancelled_at < cutoff`; `reject_appointment` הוא CAS ל-`rejected` שמגדיר `rejection_reason` בלבד. עומק נוסף: ל-`rejected` אין `google_event_id` כלל (הוא נוצר רק ב-approve).
- **תוצאה:** שום שורת `rejected` לא עברה את ה-cutoff — הכללתה הסוותה את הכוונה בלי להוסיף שורות.
- **מקור:** `8c418bf`
- **דפוס:** API design / dead code

#### 72. Google refresh token מסובב נזרק
- **בעיה:** `refresh_access_token` החזיר רק `(access, expiry)` והתעלם מ-`creds.refresh_token` (ש-google-auth מעדכן ל-refresh המסובב); ה-RPC עדכן access בלבד.
- **תוצאה:** rotation אבודה → הקריאה הבאה עם refresh ישן שבוטל → `invalid_grant` → ניתוק כוזב.
- **מקור:** `2443fe6` (RPC `update_google_tokens` — access+refresh+expiry באותה טרנזקציה)
- **דפוס:** ניהול מצב

#### 73. `has_open_session` — dedup דחיות על `ad_id` קבוע
- **בעיה:** ה-dedup היה על `webhook_events(ad_id)` — אבל `ad_id` אינו מזהה ייחודי פר-אירוע-דחייה (מודעה נדחית, מתוקנת, ונדחית שוב עם אותו id). בנוסף `check_lock` הוא no-op ל-`meta_rejection` (אין חלון מדידה).
- **תוצאה:** דחייה חוזרת של אותה מודעה אחרי סגירת הסדרה הקודמת נחשבה כפילות ולא פתחה תיקון חדש.
- **מקור:** `d197c27`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 74. סדרת rejection לא נסגרה לעולם
- **בעיה:** אחרי `push_rejection_fix` מוצלח הסדרה נשארה `in_progress`. ל-rejection אין מחזור מדידה (`window_ends_at=NULL`), אז ה-cron שסוגר סדרות לא קלט אותה.
- **תוצאה:** `has_open_session` חסם דחיות עתידיות לאותו קמפיין **לנצח**.
- **מקור:** `d929ce3`
- **דפוס:** Terminal-state / re-pick

#### 75. `resume-after-pushed` נחסם ע"י ה-gates
- **בעיה:** ה-pushed-branch (resume אחרי finalize מוצלח) הוא DB-only, אבל רץ **אחרי** ה-gates (`_gate_campaign` דורש `status='live'`, `_gate_token` דורש טוקן תקף). טוקן שפג / קמפיין שהושהה בין ה-push ל-resume חסם את ה-sync.
- **תוצאה:** `campaigns.meta_ad_ids` נשאר stale → ליד אבוד; ב-rejection — ה-session נשאר פתוח וחסם דחיות עתידיות.
- **מקור:** `b06ad65` (בשלושת שירותי ה-push), `aa9fabf` (resume לפני `assert_quota`), `278b66f` (resume נשען על `asset.campaign_id` השמור, לא על הקמפיין ה-live)
- **דפוס:** ניהול מצב

#### 76. `claim_offer_generation` — `.or_()` עם ISO timestamp שבר את ה-TTL recovery
- **בעיה:** ה-TTL recovery נבנה כ-`.or_()` של PostgREST עם cutoff ISO-8601 גולמי. הנקודתיים, ה-`T` וה-`+` של ה-offset (שהופך לרווח ב-URL-encoding) שוברים את דקדוק `column.operator.value`.
- **תוצאה:** ענף ה-stale לא התאים אף פעם — ה-recovery **לעולם לא קרה**, וה-lock נשאר תקוע (`offer_generating=true` לנצח) → המשתמש תקוע ב"כבר מכין".
- **מקור:** `98baba9` (RPC `claim_offer_generation`, migration 0062)
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 77. `offer_generating` בלי TTL = stuck lock
- **בעיה:** הדגל נקבע ב-claim בלי timestamp; כל כשל אחרי ה-claim (finish best-effort שנכשל, crash של worker, network glitch) נעל אותו לצמיתות.
- **תוצאה:** ה-claim הבא תמיד החזיר False — המשתמש תקוע ב"כבר מכין" בלי generation חדש ובלי unlock אוטומטי.
- **מקור:** `ef7933c` (migration 0060)
- **דפוס:** ניהול מצב

#### 78. `awaiting_offer` — check-then-act לא-אטומי
- **בעיה:** `_handle_offer_message` עשה `get_awaiting_offer_session` (read) → `generate_solution` → `set_awaiting_offer(false)`.
- **תוצאה:** שני requests מקבילים (double-submit/retry) → שניהם ייצרו offer copy מלאה = 2× קריאת LLM בתשלום.
- **מקור:** `df1941b` (CAS `claim_awaiting_offer`)
- **דפוס:** ניהול מצב / concurrency

#### 79. מיזוג routing flag עם generation lock
- **בעיה:** התיקון של #78 שבר את ה-routing: `awaiting_offer=false` בזמן ה-generate → הודעה מקבילית לא תאמה ונפלה ל-free-chat.
- **תוצאה:** שני ה-Cursor findings היו סותרים — התיקון של האחד שבר את השני, כי שני states שונים מוזגו לדגל אחד.
- **מקור:** `67366bc` (הפרדה: `awaiting_offer` = routing, `offer_generating` = lock; migration 0058)
- **דפוס:** API design / כפילות לוגיקה

#### 80. `awaiting_offer` נשאר פעיל אחרי סיום
- **בעיה:** אחרי שהשלב ייצר 3 וריאציות, הדגל נשאר פעיל עד `approve`.
- **תוצאה:** כל הודעה חופשית — כולל שאלה רגילה על הוריאציות — נותבה שוב לשלב-ההצעה והתפרשה כהטבה חדשה.
- **מקור:** `b95c9f9`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 81. `refresh` על `offer_change` שיבש את ה-state
- **בעיה:** refresh על שלב-4 קרא ל-`generate_solution` בלי `chosen_offer` → נפל למסלול שמבצע `set_awaiting_offer(True)` והחזיר וריאציות ישנות עם 200 (ה-binding check לא תפס — `step=4` בשני הצדדים).
- **תוצאה:** שחיתות ה-state של ניתוב-הצ'אט.
- **מקור:** `2a6de83`
- **דפוס:** ניהול מצב

#### 82. `propose`↔`approve` בלי binding של step
- **בעיה:** כל אחד קרא ל-`advance_to_next_step` בנפרד ובזמן שונה. אם בין הקריאות ה-cron של 120 שעות סגר action — הקופי שנוצר ל-step N נדחף מול step M.
- **תוצאה:** 422 מטעה ("הוריאציות אינן תואמות") או דחיפה לשלב הלא-נכון.
- **מקור:** `b6f7a84` (optimistic concurrency — `step_number` הלוך ושוב)
- **דפוס:** ניהול מצב / concurrency

#### 83. `ads` מקומי נשאר stale אחרי creative-swap
- **בעיה:** אחרי push מוצלח, טבלת `ads` עדיין הצביעה ל-`meta_ad_id` הישן (paused) עם `status='live'`.
- **תוצאה:** (א) Insights misattribution שקט — spend של המודעה המושהית יוחס לשורה המקומית; (ב) **double-spend אמיתי**: קריאת `approve` שנייה החזירה את אותן 3 שורות → 3 מודעות נוספות = 6 active ads.
- **מקור:** `68b3e21` (migration 0054 — `local_ad_ids` לזיווג פוזיציוני)
- **דפוס:** עקביות DB

#### 84. `starting_metric` לא רוענן — baseline מרחף
- **בעיה:** `open_optimization_session` החזיר סדרה פתוחה קיימת בלי לעדכן את `starting_metric` ל-CPL החדש.
- **תוצאה:** ה-monitor של 120h וניתוח ה-mixed המשיכו להשוות מול ה-X של האבחון הראשון, גם אחרי שהלקוח איבחן מחדש עם CPL עדכני.
- **מקור:** `698305a` (migration 0055 — רענון כל עוד אין actions, נעילה אחרי action ראשון)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 85. מדד איכות מול חלון מתגלגל במקום baseline קבוע
- **בעיה:** ב-`_measure_low_quality`, `change_t=now-120h` זז עם כל tick; בחלון השני זה חישב `before` = החלון שאחרי השינוי, ולא ה-baseline שלפניו.
- **תוצאה:** שיפור יציב נמדד מול חלון קודם ופורש כ**רגרסיה כוזבת** → הסדרה חזרה ל-`in_progress` וביצעה swap נוסף בתשלום.
- **מקור:** `b0417e7`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 86. סדרה סגורה נחשבה "תהליך פתוח"
- **בעיה:** `has_prior_session` היה true לכל סדרה ב-30 יום, כולל `done`/`failed`/`escalated`.
- **תוצאה:** ה-LLM קיבל "תהליך כבר פתוח, ממשיך" — שגוי, כי `open_session` בדיוק פתח סדרה חדשה.
- **מקור:** `164ecb3` (`has_open_session` — רק `in_progress`/`success_monitoring`)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 87. `round` במקום `ceil` בהעלאת תקציב
- **בעיה:** `approve_budget` השתמש ב-`round(required, 2)`. עיגול **למטה** (11.3333 → 11.33) גורם ל-`(new_daily×30)/market_cpl` ליפול מתחת ל-`monthly_lead_goal`.
- **תוצאה:** הקמפיין נשאר infeasible למרות שהתקציב עלה — בדיוק מה שהלקוח ניסה לתקן, וכסף נוסף יצא לחינם.
- **מקור:** `ccb5098` (`math.ceil(required*100 - 1e-9)`)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 88. `approve_budget` — חסרו שני guards
- **בעיה:** (א) `lifetime` ad_set — ה-ad_set נוצר עם `lifetime_budget`; עדכון `daily_budget` עליו ייכשל/יסתור; (ב) אם המצב הפך feasible בין האבחון ל-approve, `required_budget` קטן מהנוכחי.
- **תוצאה:** בענף (ב) — ה-approve היה **מוריד** spend ומתעד "approved" כוזב.
- **מקור:** `72d6951`, `5971411` (סימטריה: `diagnose` הפסיק להציע "הגדל" ל-lifetime)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 89. `_measure_high_cpl` — סתירה בין payload להוראה
- **בעיה:** ה-`SYSTEM_PAYLOAD` הציג `market_classification` נכון (AMAZING/AVERAGE/UNKNOWN), אבל ההוראה שנבחרה תמיד קידדה "עלות גבוהה"; `_high_cpl_state_key` בחר state לפי `mixed`/`has_open_session` בלבד — לא לפי ה-level.
- **תוצאה:** הסוכן טען "העלות שלך גבוהה" על קמפיין עם CPL מצוין.
- **מקור:** `f4c1003` (state_key חדש `optimize_not_high`)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 90. `cost_now` כפול ומיושן
- **בעיה:** ה-payload הציג גם `cost_now` (צילום מאוחסן) וגם `current_cost_per_lead` (חי) — אותו CPL מרגעים שונים.
- **תוצאה:** הסוכן ניסח "ועכשיו X" עם ערך ישן הסותר את הערך החי שהוצג לידו.
- **מקור:** `fea0e03`
- **דפוס:** API design / כפילות לוגיקה

#### 91. `israel_today_end_utc` — שני חישובי `now`
- **בעיה:** `israel_today_end_utc()` קרא **שוב** ל-`israel_today_start_utc()` שמחשב `datetime.now(IL)` מחדש; ה-caller קרא לשתיהן בנפרד.
- **תוצאה:** אם חצות ישראלית עוברת בין הקריאות, `[start, end)` פורש על שני ימים שונים → "פניות היום" שגוי.
- **מקור:** `3e11318` (`israel_today_range_utc()` — `now` פעם אחת)
- **דפוס:** ניהול מצב / concurrency

#### 92. `_today_count` הפיל את כל הצ'אט
- **בעיה:** ענף ה-lead קרא ל-`count_leads_in_range` בלי try/except, בעוד ענף ה-whatsapp היה best-effort.
- **תוצאה:** תקלת DB חולפת במטריקה **משנית אחת מתוך ארבע** הפילה ב-500 גם את `GET /status` וגם את `send_user_message` — כל הצ'אט נשבר.
- **מקור:** `beee243`
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 93. שליחת הודעות בוט — ייחוס שגוי ב-retry
- **בעיה:** כש-`advance_state` נכתב ב-DB אך ה-client קיבל שגיאה חולפת, ה-runner הריץ את ה-handler שוב; הוא קרא state שכבר התקדם, חישב צעד אחר, אבל השתמש באותו `reply:{wamid}` key.
- **תוצאה:** תשובה מיוחסת לשאלה הלא-נכונה + הליד **מפספס** את ההודעה (שאלה/Calendly/handoff).
- **מקור:** `4b1e38c` (השוואת body של שורת ה-'sent' הקיימת)
- **דפוס:** ניהול מצב / concurrency

#### 94. תיאום תור — התראת בעלים ו-terminal לא הובטחו
- **בעיה:** `create_appointment` (בלתי-הפיך) רץ לפני הודעת הליד; כשל בהודעה גרם ל-early return.
- **תוצאה:** תור `pending` נוצר בלי שבעל העסק קיבל התראה, והשיחה נתקעה או הפכה ל-`send_failed` כוזב.
- **מקור:** `0423e7b`
- **דפוס:** ניהול מצב

#### 95. handoff — כשל בהתראת הבעלים הרג את השיחה
- **בעיה:** אחרי שהליד כבר קיבל "נציג יחזור אליך", כשל permanent בשליחת ה-template לבעל העסק קרא ל-`mark_send_failed` וסיים בלי `completed_handoff`.
- **תוצאה:** הליד הובטח חזרה, השיחה סומנה `send_failed`, והבעלים לא קיבל סיכום.
- **מקור:** `0a43e04`, `469d2d6` (אותו טיפול ל-outcome `stale`)
- **דפוס:** Terminal-state / re-pick

#### 96. אישור "התור בוטל" נשלח גם כש-CAS לא תפס
- **בעיה:** אישור הביטול לליד נשלח **תמיד**, בעוד שאר ה-side-effects (מחיקת אירוע, התראת בעלים) היו מותנים ב-CAS.
- **תוצאה:** בעל העסק ביטל/דחה בפאנל בזמן שהליד היסס → הליד קיבל אישור "בוטל" שני ומטעה.
- **מקור:** `4b03ee9`
- **דפוס:** ניהול מצב / concurrency

#### 97. ביטול תור — 5 באגי state machine
- **בעיה:** (א) לחיצה חוזרת על כפתור ישן ב-`completed_appointment_scheduled` — מזהה הכפתור הועבר ל-`classify_intent` שסיווג אותו `other` → הביטול אבד; (ב) טקסט חופשי כש-`get_appointment_by_id` מחזיר None השאיר את הליד תקוע; (ג) תורים שעברו הוחזרו כ"פעילים"; (ד) שיחה שעברה ל-`abandoned` הפכה את התור ל-uncancellable; (ה) `exit` חזר תמיד ל-`scheduled` גם כשהמקור היה `abandoned`.
- **תוצאה:** לידים תקועים, אישורים מטעים, ו-DB שלא תואם למה שהמשתמש ראה.
- **מקור:** `05c8024`, `d04d54b`, `70e7cb7`, `472bf66`, `da0f719`
- **דפוס:** ניהול מצב

#### 98. `completed_at` נשאר על שיחה שהתעוררה
- **בעיה:** שיחה terminal שעברה ל-`awaiting_cancellation_confirm` (reactivation) נשארה עם `completed_at` ישן.
- **תוצאה:** שורה פעילה עם חותמת completion — סתירה ל-lifecycle ומטעה כל reporting.
- **מקור:** `40a82a8` (invariant: `completed_at IS NOT NULL ⟺ terminal`)
- **דפוס:** עקביות DB

#### 99. `followup` נשלח ל-states אינטראקטיביים
- **בעיה:** `fetch_followup_candidates` סינן את כל ה-active states.
- **תוצאה:** `awaiting_cancellation_confirm` ו-`scheduling_*` קיבלו "תכתוב בחזרה" אחרי 23.5h — שגוי ל-state שבו הליד אמור ללחוץ כפתור.
- **מקור:** `0140e75` (whitelist מפורש)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 100. `pending_initial_send` לא נוקה ב-inbound
- **בעיה:** הדגל סומן `true` כש-opening דולג ב-soft-disable, אבל `handle_inbound` לא ניקה אותו כשהליד הגיב.
- **תוצאה:** שני מסלולי cron נשברו — `fetch_pending_initial` שלח opening שני **מחוץ-לסדר** לליד שכבר באמצע שיחה, ו-`fetch_followup_candidates` (שמסנן `pending=false`) דילג על השיחה לנצח.
- **מקור:** `b3caa6e` (5.4#1)
- **דפוס:** Terminal-state / re-pick

#### 101. `send` לא בדק שהקמפיין עדיין active
- **בעיה:** `get_or_create` דורש קמפיין live/paused, אבל `send_user_message` בדק רק בעלות + quota.
- **תוצאה:** לקוח עם `conversation_id` קיים המשיך לצ'וטט (ולצרוך OpenAI) אחרי שהקמפיין יצא מ-active.
- **מקור:** `4b82609`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 102. דגל free-chat שינה authorization
- **בעיה:** `send_user_message` עם `agent_free_chat_enabled=false` החזיר את הפניית הצ'יפים **מיד**, לפני `_assert_conversation_owner` ובדיקת קמפיין active.
- **תוצאה:** שיחה לא-קיימת / לא-שלך / קמפיין מאורכב קיבלו 200 הפניה במקום 404/409 — דגל שאמור להשפיע רק על LLM/מכסה שינה גם הרשאות.
- **מקור:** `e3b2b41`
- **דפוס:** בטיחות נתונים

#### 103. בלוק ה-prompt המשותף סתר את מצב ה-free-chat
- **בעיה:** `core.txt` בלוק א' (משותף ל-chip ול-free) נכתב chip-centric: "מה שלא ב-SYSTEM_PAYLOAD לא קיים", "תמיד מודול פעיל אחד". בשיחה חופשית ה-payload הוא `[GENERAL_STATUS]` ואין מודול.
- **תוצאה:** הכללים סתרו את המציאות — המודל עלול היה להתעלם מהמטריקות המוזרקות או לנהוג כאילו הוא בפרוטוקול צ'יפ.
- **מקור:** `0f08fa0` (פיצול ל-shared/chip_extra/free_extra)
- **דפוס:** API design / כפילות לוגיקה

#### 104. `insights` — stale לא עודכן ב-cache
- **בעיה:** על stale, `get_campaign_insights` החזיר `is_stale=True` אך **לא** עדכן את ה-cache.
- **תוצאה:** caller עוקב עם `max_age_seconds` גדול יותר קיבל cache-hit עם `is_stale=False` בזמן ש-upstream עדיין נכשל.
- **מקור:** `469d2d6`
- **דפוס:** עקביות DB

#### 105. `insights` — stale fallback רק ל-`MetaTransientError`
- **בעיה:** ה-stale-while-error חל רק על `MetaTransientError`, אבל `get_campaign_insights` מושך מ-5 מקורות (Meta + campaign + fb + lead_stats + ads).
- **תוצאה:** תקלת DB חולפת מאחד מהאחרים ברחה בלי fallback, למרות שזו אותה משפחת-תקלה.
- **מקור:** `3b52acc`
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 106. `count_leads_per_ad` נחתך בשקט ב-1000 שורות
- **בעיה:** הפונקציה שלפה את כל שורות הלידים וקיבצה ב-Python — ונחתכה בשקט בתקרת השורות של PostgREST.
- **תוצאה:** בקמפיין שחוצה 1000 לידים, `sum(per-ad)` נפל מתחת ל-count המדויק ושבר את ה-invariant.
- **מקור:** `3b52acc` (RPC עם `GROUP BY`, migration 0031)
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 107. `count_leads_per_ad` התעלם מטווח התאריכים
- **בעיה:** ספר את כל לידי הקמפיין בלי date filter, בעוד campaign-level leads ו-per-ad spend/ctr עוקבים אחרי `date_preset`.
- **תוצאה:** `sum(per-ad)` סותר את ה-campaign total ו-CPL per-ad שגוי לכל `date_preset ≠ lifetime`.
- **מקור:** `06e7609`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 108. `date_range_end` נחשף exclusive
- **בעיה:** נחשף כ-`date_stop+1` במקום היום האחרון ה-inclusive.
- **תוצאה:** צרכן שמפרמט אותו כתאריך calendar הציג יום אחרי התקופה.
- **מקור:** `06e7609`
- **דפוס:** API design

#### 109. `bool` עבר כ-`int` ב-4 מקומות
- **בעיה:** `bool` הוא subclass של `int` ב-Python. `DebitTotal=true` ב-JSON עבר את `isinstance(int)` ושימש כסכום 1 אגורה (`09d397c`); `code=true` ב-Meta נמצא ב-`_META_TRANSIENT_CODES` (`414fb82`); `count=True` חזר כליד אחד (`066db8f`).
- **תוצאה:** בענף הראשון — סכום כספי שגוי בחשבונית; בשני — סיווג transient שגוי; בשלישי — ספירת לידים שגויה.
- **מקור:** `09d397c`, `414fb82`, `066db8f`
- **דפוס:** ולידציית קלט

#### 110. `PelecardStatusCode` — בדיקה strict + drop לפני audit
- **בעיה:** נדרש `isinstance(str) and == "000"`. `int 0` או `"000 "` → silent drop **לפני** ה-reserve ל-`webhook_events`.
- **תוצאה:** אין audit trail ל-IPN שנדחה; פלאקארד לא תנסה שוב (200).
- **מקור:** `ebb7f92` #2 (normalize + reserve לפני בדיקת status)
- **דפוס:** ולידציית קלט

#### 111. טוקן של רווחים-בלבד עבר את הבדיקה
- **בעיה:** `not token` תפס `""` אבל לא `"   "` (מחרוזת רווחים truthy ב-Python).
- **תוצאה:** טוקן בלתי-שמיש נשלח ל-Meta במקום לשקף "סוד חסר ב-Vault".
- **מקור:** `db3ec53`
- **דפוס:** ולידציית קלט

#### 112. `error=""` חסם code תקף ב-OAuth callback
- **בעיה:** התנאי `error is not None` תפס גם `error=""` — מחרוזת ריקה שספקים/proxies עלולים לצרף לצד code תקף.
- **תוצאה:** login תקין נשלח למסלול כשל גנרי.
- **מקור:** `b110299`
- **דפוס:** ולידציית קלט

#### 113. `get_fb_token` לא הבחין "לא מחובר" מ"סוד חסר"
- **בעיה:** ה-RPC החזיר NULL בשני המצבים, ושניהם נבלעו ל-`fb_not_connected` (409).
- **תוצאה:** משתמש שרואה חיבור פעיל ב-`GET /me/fb-connection` קיבל "לא מחובר" — הודעה מטעה שמסתירה אנומליית integrity.
- **מקור:** `ba5709c` (RPC מחזיר `(connection_exists, token)`)
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 114. `hmac.compare_digest` על str לא-ASCII → 500
- **בעיה:** `compare_digest` על `str` עם תווים שאינם ASCII זורק `TypeError`. שלושה מקומות: `verify_meta_signature`, cookie של OAuth state, ו-`meta_leads_challenge`. אחר-כך נמצא רביעי: `_verify_state`.
- **תוצאה:** חתימה/state פגומים החזירו 500 במקום 403 — דליפת מידע פנימי + סימן היכר לתוקף.
- **מקור:** `3217a85`, `3fb7936`, `43aeedf` (`safe_compare` ציבורי)
- **דפוס:** בטיחות נתונים

#### 115. `_parse_campaign_row` — שדות חסרים קרסו כ-500 לא-מטופל
- **בעיה:** `created_at`/`updated_at` נקראו באינדוקס ישיר; `type`/`status`/`fb_*` השתמשו ב-`row.get("...", "")`.
- **תוצאה:** `KeyError`/`ValidationError` שאינם יורשים מ-`CampaignServiceError` עקפו את מיפוי השגיאות של ה-router → 500 לא-מטופל; ובענף השני — 201 עם ערכים ריקים במקום שגיאה.
- **מקור:** `e54bbe4`, `98cb919`
- **דפוס:** ולידציית קלט

#### 116. `maybe_single`/`single` — צורת תגובה `list` שברה 8 מקומות
- **בעיה:** PostgREST עלול להחזיר `list` בן-איבר-אחד. `if not data` עובר (list לא-ריק = truthy) ואז `.get()` זורק `AttributeError`; `**data` על list זורק `TypeError`.
- **תוצאה:** `start_trial` שבור, חוזה ה-200 של ה-IPN שבור (פלאקארד עשתה retry), `GET /me/billing-profile` → 500, `GET /me/subscription` → 500, ו-IPN כפול לא נדחה בשער ה-idempotency.
- **מקור:** `b38bf8e`, `42f30ca`, `e46f658`, `7c06aef`, `781a041` (הכל דרך `first_row`)
- **דפוס:** עקביות DB

#### 117. `UPDATE` שתפס 0 שורות דווח כהצלחה
- **בעיה:** `_finalize`/`_finalize_invoice_row` התייחסו ל-200 של PostgREST כהצלחה בלי לבדוק rowcount. אותו דפוס ב-`_charge_subscription` CAS→charging, ב-`update_tier` וב-`start_trial` CAS→reserved.
- **תוצאה:** `provider_document_id` נשאר NULL והמסמך "אבד" מהמעקב → שתי ריצות cron "מצליחות" ויוצרות מסמך כפול. במקרה ה-CAS — מנוי נתקע ב-`charging`, או 409 כוזב אחרי שהשורה כבר עודכנה.
- **מקור:** `9e69ce9`, `d1a9785`, `ee4945c`, `bd97a94`, `5c34a50`
- **דפוס:** עקביות DB

#### 118. `always-200` של ה-webhooks לא נאכף בגבול ה-HTTP
- **בעיה:** שני ה-webhooks (Pelecard IPN, Green Invoice) מתעדים "תמיד 200", אך הקריאה ל-service לא הייתה עטופה ב-try/except — החוזה נאכף רק "במאמץ מיטבי" בעומק עץ הקריאה.
- **תוצאה:** כל חריגה לא-צפויה (באג, KeyError, TypeError) דלפה כ-500 → retry storm + עיבוד כפול. ההוכחה: ה-`AttributeError` מ-`maybe_single` (#116) חמק מכל ה-except הפנימיים.
- **מקור:** `08269d1`
- **דפוס:** API design

#### 119. Green Invoice webhook סימן `processed` בלי PDF
- **בעיה:** השורה סומנה `processed` גם כשלא נמצא קישור PDF וגם כשה-UPDATE לא תפס שורה (ה-webhook הקדים את ה-finalize).
- **תוצאה:** משלוח חוזר של GI נדלג → `pdf_url_he` נשאר ריק לצמיתות.
- **מקור:** `7440705`
- **דפוס:** Terminal-state / re-pick

#### 120. `pending session` לא נוקה בכשל webhook
- **בעיה:** כשל אחרי שה-session קיים החזיר בלי למחוק אותו; ה-UNIQUE על `user_id` חוסם.
- **תוצאה:** `start_trial` נחסם ל-30 דקות. התיקון דרש סיווג — מחיקה רק על כשל **terminal**.
- **מקור:** `f39a37f`
- **דפוס:** Terminal-state / re-pick

#### 121. `_is_webhook_already_processed` נכשל closed על תקלת DB
- **בעיה:** החזיר `True` בכשל DB כ"fail-closed".
- **תוצאה:** חסם הפעלת trial **לצמיתות** אם ניסיון קודם נכשל באמצע. (ה-CAS על `billing_customer_id IS NULL` הוא ההגנה האמיתית מכפילות.)
- **מקור:** `f3286ce`
- **דפוס:** סיווג שגיאות מספק חיצוני

#### 122. `charge_past_due` שיבש את לוח החיובים
- **בעיה:** retry מוצלח ב-`past_due` קבע `current_period_start = now`.
- **תוצאה:** כשל ביום 38 והצלחה ב-retry ביום 41 → החיוב הבא ביום 71 במקום 68 — הלוח נדחה בכל כשל.
- **מקור:** `080d2ee` (עוגן קלנדרי)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 123. `past_due` retry לא חייב כלל
- **בעיה:** `process_past_due_retries` קרא ל-`charge_monthly` שמסנן `status='active'`.
- **תוצאה:** לקוחות ב-`past_due` לא חויבו לעולם. בנוסף: 30 ימים במקום חודש קלנדרי, ו-`card_last_four="0000"` קבוע.
- **מקור:** `4351557` (migration 0008)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 124. `cron` יום-8 השווה למחרוזת `"now()"`
- **בעיה:** `.lt("trial_ends_at", "now()")` — ב-PostgREST זהו ליטרל מחרוזת, לא פונקציית DB.
- **תוצאה:** ה-cron של סוף-trial לא בחר אף שורה.
- **מקור:** `7968842`
- **דפוס:** תאימות לחוזה ספק חיצוני

#### 125. `webhook` re-entrant נחסם לנצח
- **בעיה:** UNIQUE conflict דילג בלי לבדוק `processed_at`.
- **תוצאה:** ניסיון קודם שלא הושלם נחסם לצמיתות במקום להמשיך לעבד.
- **מקור:** `7968842`
- **דפוס:** Terminal-state / re-pick

#### 126. ביטול חסום מ-`charge_unknown`
- **בעיה:** `cancel_subscription` עדכן רק `status IN (trial, active, past_due)`; `charge_unknown` הושמט למרות שהוא state פעיל (`has_paid_access=True`).
- **תוצאה:** משתמש ב-`charge_unknown` קיבל 409 על ביטול ונתקע.
- **מקור:** `a8907de`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 127. `update_tier` CAS בלי בדיקת status
- **בעיה:** משתמש שביטל בזמן trial (`canceled` + `pending`) עדיין יכול היה לעשות `PATCH /me/subscription`.
- **תוצאה:** `tier='basic'`, `lead_quota=500`, ו-`tos_accepted_at=now` נרשמו על חשבון מת — הסכמת ToS משפטית על מצב שאין מאחוריו.
- **מקור:** `ebb7f92` #1 (0-2#10)
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 128. `_DEFAULT_CONFIG` — עותק רדוד
- **בעיה:** `dict(_DEFAULT_CONFIG)` הוא shallow copy; ה-dicts המקוננים וה-list `screening_questions` נשארו משותפים עם הקבוע ברמת המודול.
- **תוצאה:** מוטציה על התוצאה **דרסה את ברירת המחדל לכל המשתמשים ולכל הבקשות**.
- **מקור:** `695333f` (`copy.deepcopy`)
- **דפוס:** ניהול מצב

#### 129. `get_lead_form` לא אכף `type='lead'`
- **בעיה:** GET אימת בעלות אך לא type, בניגוד ל-POST.
- **תוצאה:** קמפיין whatsapp קיבל 200 עם קונפיגורציית ברירת-מחדל מטעה במקום 400.
- **מקור:** `23618d4`
- **דפוס:** לוגיקה עסקית / מקרי קצה

#### 130. `business context` מה-cache עקף ולידציה
- **בעיה:** `get_or_extract_business_context` בנה `BusinessContext` מה-cache ישירות (dataclass — לא מוולידט), בעוד ה-extract פוסל מחרוזות ריקות.
- **תוצאה:** שדה ריק/None/לא-str הגיע ליצירת קופי → מודעות גרועות.
- **מקור:** `bf8bb31`
- **דפוס:** ולידציית קלט

#### 131. `GREEN_INVOICE_ENV` נפל בשקט ל-production
- **בעיה:** `_base_url` נפל ל-production על **כל** ערך לא-מובהק (typo/לא-מוכר).
- **תוצאה:** typo ב-env → הנפקת מסמך מס **אמיתי** בסביבה שהייתה אמורה להיות sandbox.
- **מקור:** `bf8bb31`
- **דפוס:** ולידציית קלט

#### 132. LLM לפני שער ה-idempotency — 3 מופעים
- **בעיה:** קריאת LLM יקרה רצה לפני ה-marker האידמפוטנטי ב-`_advance_text` (bot), `handle_meta_rejection` ו-`_handle_terminal_appointment_message`.
- **תוצאה:** job שקורס/נכשל transient אחרי ה-LLM אך לפני ה-persist → ה-runner מריץ retry שסופר-מחדש את קריאת ה-LLM.
- **מקור:** `2462110` (PR12 — search-before-write)
- **דפוס:** ניהול מצב

#### 133. `_metaEpoch` — counter גלובלי משותף לשתי רשימות
- **בעיה:** counter יחיד שימש כ-race guard לשתי זרימות עצמאיות (`runLeadsScan`→`leads-acc-list`, `runWAScan`→`fb-acc-list`).
- **תוצאה:** ה-increment של הסריקה השנייה ביטל את ה-epoch של הראשונה → היא לא אכלסה את רשימתה → המשתמש נתקע על "טוען נכסים..." בלי דרך להמשיך.
- **מקור:** `351c5fb` (map לפי `listId`)
- **דפוס:** DOM / UI

#### 134. `id` מוזרק מ-`asset.id` ב-`renderGalleryAsset`
- **בעיה:** `id="${uid}"` ו-`getElementById('pub-${uid}')` בתוך `onchange` — `asset.id` מוזרק raw. escape לבדו לא פותר: `_esc` מכסה HTML-attribute אך לא JS-string context.
- **תוצאה:** מרכאה/תו-מיוחד ב-`asset.id` שובר את ה-DOM או מאפשר injection.
- **מקור:** `012fc8f` (מחיקת ה-id הנגזר; מעבר ל-class + `closest('[data-asset-id]')`)
- **דפוס:** בטיחות נתונים

#### 135. `pending` tier הוצב כ-`APP.plan`
- **בעיה:** `_hydrateAndRoute` הציב `APP.plan=sub.tier` גם ל-`tier='pending'`; המחרוזת truthy.
- **תוצאה:** הדליקה את שער ה-`ob-finish`, הציגה מחיר Basic כוזב, ו-`choosePackage` היה שולח `tier='pending'` → 422.
- **מקור:** `39a461c`
- **דפוס:** DOM / UI

#### 136. `scanned` סומן גם בכשל
- **בעיה:** `runLeadsScan`/`runWAScan` סימנו `APP.scannedLeads=true` תמיד אחרי `loadMetaAssets` — גם ב-409/שגיאת רשת/רשימה ריקה.
- **תוצאה:** ה-lock ("never re-scan") נעל **מצב שגיאה**: ניווט חוזר דילג על fetch והשאיר UI שגוי תקוע עד רענון ידני.
- **מקור:** `2db2dcd`, `c954f63`, `7bc367f`
- **דפוס:** DOM / UI

#### 137. render אופטימי חסר → הצלחה הוסתרה
- **בעיה:** `generate`/`upgrade`/`revise`/`publish` הסתמכו על `loadCreativeView` (best-effort) להצגת התוצאה; `loadGallery` יוצא בשקט על תגובה לא-OK.
- **תוצאה:** ה-prompt נוקה אחרי `res.ok`, אז רענון כושל **הסתיר את ההצלחה** → המשתמש חשב שנכשל → יצר שוב → שימוש כפול במכסה (כסף אמיתי).
- **מקור:** `b0d3816` (`_showNewAsset` + `_bumpQuota`), `67462a3`
- **דפוס:** DOM / UI

#### 138. בקרות פרסום הוצגו ל-asset שלא ניתן לפרסום
- **בעיה:** `renderGalleryAsset` הציג את זרימת הפרסום לכל פריט לא-מפורסם, אבל `publish_creative` מקבל רק `asset_type='generated'`.
- **תוצאה:** תוצרי `upgraded`/`revised` קיבלו בקרות פרסום ונכשלו ב-404 בלחיצה.
- **מקור:** `202c6a1`
- **דפוס:** DOM / UI

#### 139. drop ללא קובץ + מונה כפול + consent קבוע
- **בעיה:** (א) `handleStudioDrop` הציג preview אך לא הזין את ה-file-input; (ב) ה-HTML הוסיף `/15` קבוע אחרי span שכבר מכיל `remaining/quota`; (ג) `submitPublish` שלח `responsibility_accepted:true` בלי לקרוא את ה-checkbox.
- **תוצאה:** העלאה ריקה בזמן שה-UI מראה קובץ מוכן; "עוד 5/15/15 נותרו"; אישור-אחריות שנרשם בלי שהמשתמש סימן.
- **מקור:** `14bcc7a`
- **דפוס:** DOM / UI

#### 140. double-submit במסך התמיכה
- **בעיה:** `sendReply` נקרא ישירות מ-`keydown` אבל רק הכפתור ננעל (לא ה-textarea) — אסימטריה מול `sendSupport` שכבר ננעל.
- **תוצאה:** Enter כפול שלח תשובת-צוות כפולה. בנוסף: שליחה תוך-כדי `loadSupport` מחקה את הודעת המשתמש מה-UI.
- **מקור:** `3699cb0`, `5e20106`
- **דפוס:** DOM / UI

#### 141. `frontend stale` — אין `Cache-Control`
- **בעיה:** `SPAStaticFiles` הגיש את הפרונטד בלי `Cache-Control` (רק ETag/Last-Modified), והפרונטד מוגש בלי hashing בשם הקובץ.
- **תוצאה:** אחרי כל merge הדפדפן המשיך להציג `index.html` ישן בלי revalidation.
- **מקור:** `c3b2482`
- **דפוס:** DOM / UI

---

### LOW

| # | באג | בעיה → תוצאה | מקור | דפוס |
|---|---|---|---|---|
| 142 | `_normalize_id` חסר בגבול ה-SDK | מזהה numeric/whitespace עבר ל-assets ונכשל מאוחר ביצירת קמפיין | `3ae84e8`, `0895f38` | ולידציית קלט |
| 143 | `identity_already_exists` לא מופה ל-409 | שני מסלולי-זיהוי לא הסכימו על אותו מקרה → redirect שגיאה גנרי במקום 409 | `d21c3f8` | API design |
| 144 | callback לא כפוף ל-gate התצורה | signing secret חסר → `RuntimeError` → 500; ובלי `redirect_uri` ה-callback הנפיק session בסתירה ל-degradation של `/start` | `fee5dba` | סיווג שגיאות |
| 145 | `delete_cookie` בלי אותם attributes | דפדפנים עלולים לא לזהות אותו cookie → state מיושן נשאר | `0ea795f` | ולידציית קלט |
| 146 | `auto_refresh_token=True` בשרת | טיימר refresh ברקע על clients קצרי-חיים → race מול `refresh_session` → "refresh token already used" כוזב תחת עומס | `d92d186` | ניהול מצב |
| 147 | PostgREST 5xx/429 → 500 במקום 503 | outage של Supabase הוצג ללקוח כשגיאת-שרת לא-retryable | `c2f46ed` | סיווג שגיאות |
| 148 | `_access_token_is_fresh` עם bare `except` | כל בעיה נבלעת כ-False | `0-2#26` (מתועד, נסגר בשרשרת P0-2-S) | סיווג שגיאות |
| 149 | `screening_question` answers לא dedup | `["כן","כן "]` → Meta דוחה ב-push, המשתמש רואה שגיאה מאוחר | `3#25` → `f3d6048` | ולידציית קלט |
| 150 | `_split_copy` ב-resume השתמש ב-request | retry עם טקסט שונה כתב ל-`ads` copy שלא תואם ל-Ad החי ב-Meta | `08d6bf4` | ניהול מצב |
| 151 | `image_url` נדרש ב-`CreativeAsset` | `_sign_asset` best-effort החזיר None → 500 על כל הגלריה במקום דילוג על asset בודד | `56eb671`, `2e5adc3` | ולידציית קלט |
| 152 | תמונה יתומה ב-storage | כשל אחרי upload (billing/insert/payload) השאיר קובץ בלי שורת DB | `c0f2ef8`, `9fb15dc` | עקביות DB |
| 153 | `_gate_live_old_ads` ספר גם את ה-Ad הרביעי | `len(live)=4≠3` → equality gate נכשל → optimization לא רצה אחרי VIP publish | `dfa2953` | לוגיקה עסקית |
| 154 | `_sync_local_ads_best_effort` — שינוי חתימה שבר 2 call-sites | `TypeError` ב-screening push; הטסטים לא תפסו כי ה-mock הוא `f_sync(*a, **k)` גמיש | `9b6712c` | API design |
| 155 | `capture_exception` אחרי `escalate_session` | כשל escalate (DB חולף) השתיק את ה-Sentry של כשל ה-rollback | `25ca676` | Terminal-state |
| 156 | `capture_alert` לפני `set_value(flag)` | כשל `set_value` → ה-flag נשאר false → alert חוזר בכל tick (שובר edge-triggered-once) | `9aefb1b` | Terminal-state |
| 157 | `idx_jobs_claim` חסר `id` ב-tail | resort מאולץ + tiebreaker לא דטרמיניסטי כש-`created_at` שווה | `3ef2b4b` | סכימת DB |
| 158 | `enqueue` בלי validation מקומית | typo ב-`job_type` נתפס רק ע"י CHECK constraint, אחרי round-trip ל-DB | `bc7269b` | API design |
| 159 | keyset cursor בלי tiebreaker | לידים עם `created_at` זהה (batch webhook) → העמוד הבא דילג על שורות | `789a8bd` | לוגיקה עסקית |
| 160 | `SpecialDayInput` השתמש ב-`date.today()` | שעון השרת (UTC ב-Render) ולא tz עסקי → תאריך ישראלי תקף נדחה ליד חצות | `ba83880` | לוגיקה עסקית |
| 161 | `whatsapp today` לפי tz של חשבון המודעות | מגבלת Meta — תועדה במפורש במקום להסתיר | `5472618` | תאימות לחוזה ספק |
| 162 | `prefill` של טלפון הדליק ערוץ שכובה | מעבר-בלי-הזנה הדליק עדכוני WhatsApp בשקט — הפרת בחירת כיבוי מפורשת | `f47d1f3` | לוגיקה עסקית |
| 163 | טלפון ריק בשאלון **מחק** מספר שמור | `WIZ._contactPrefilled` נדלק לפני שה-fetch הסתיים → איבוד נתונים | `1be66d7` | DOM / UI |
| 164 | מונה מכסת-WhatsApp ספר 5 סוגים מתוך 6 | הרשימה שוכפלה Python↔SQL → ה-`used` בדשבורד סטה מהאכיפה בפועל | `8ceaf0b` | API design |
| 165 | `action_type` מקודד כ-literal ב-7 מקומות | `action_type` הוא text חופשי בלי CHECK → drift שקט בשינוי `_STEP_PLANS` | `9278160` | API design |
| 166 | סריקת-רקע לא סיננה `is_sandbox` | ה-cron היומי הריץ LLM + 3 תמונות (כסף) על קמפיין-דמה ושלח התראות אמיתיות | `0fe2594` | לוגיקה עסקית |
| 167 | `approve` בסנדבוקס שלח התראות אמיתיות | בדיקות QA שלחו מיילים אמיתיים + jobs נספרי-מכסה | `6839cbe` | לוגיקה עסקית |
| 168 | סנדבוקס יצר job כפול | `run_propose` קרא `generate_solution` עם eager **וגם** הריץ inline → עלות כפולה | `12c7e7c` | ניהול מצב |
| 169 | `force_creative` ציפה לתמונות שטרם נוצרו | ה-push הסינכרוני רץ לפני ה-worker ה-eager → `generated_image_paths` ריק | `7185b83` | async / control flow |
| 170 | `generated_image_paths` — read-modify-write | eager propose + push שניהם כותבים את המערך המלא → lost-update שמפיל slots | `6c0d374` (RPC `set_optimization_image_path`, migration 0109) | ניהול מצב |
| 171 | `images_generating` נתקע `true` | slot שנכשל permanent הציג "בייצור..." נצחי; polling לא נוקה ב-timeout | `39e801c` (migration 0108) | DOM / UI |
| 172 | polling עצר על שגיאה חולפת | `_pollActionImages` עצר לגמרי על כל כשל `getAction` → ספינר תקוע | `12c7e7c` | DOM / UI |
| 173 | `onChip` בסנדבוקס בדק ערך שגוי | `value==="override"` מול הערך האמיתי `"override_change"` → רק 4 subcategories עבדו | `069f24b` | לוגיקה עסקית |
| 174 | router השמיט `value` ב-diagnose | `diagnose_problem_2` קיבל `value=None` ולעולם לא הגיע לשלב הניתוח | `40c9a18` | API design |
| 175 | quiz-דמה חלקי → 500 ב-propose | `get_or_extract_business_context` דורש 3 שדות; הדמה נתן אחד | `bff781c` | ולידציית קלט |
| 176 | `via.placeholder.com` נסגר | ההורדה נכשלה → transient → 503 ב-approve של הסנדבוקס | `90007e5` | תאימות לחוזה ספק |
| 177 | `SYSTEM_PAYLOAD` keys לא מובנים ל-AI | `industry_he`/`market_range_he` — סיומת פנימית וערך גולמי בלי משמעות | `072bb07` | API design |
| 178 | תבניות WhatsApp לא תאמו ל-Meta | 3 אי-התאמות ב-placeholders → Meta הייתה דוחה ב-`error 132000` כשה-WABA יופעל | `8b1342f` | תאימות לחוזה ספק |
| 179 | "לא יפעל בשבת" לא חוּוט ל-Meta | ה-checkbox נשמר ושימש רמז-קופי בלבד; `adsest_schedule` לא נשלח → הקמפיין רץ בשבת בפועל | `4c21367` | API design |
| 180 | הטונים — שכבת תרגום שסטתה | הפרונטד חשף 4 מתוך 5 טונים ותרגם עברית→אנגלית בערכים לא-תואמים | `eb09353` | API design |
| 181 | `offer` נכלל ב-`_check_free_text` | לחיצת "דלג" שלחה `offer=''` → 422 בפרודקשן (סטיית frontend↔backend) | `af3f836` | ולידציית קלט |
| 182 | `CreativeNoCampaignError` (409) לפני קמפיין חי | ה-frontend עשה `if(!res.ok)return` → כרטיסי המכסה נשארו על "—" | `54278bf` | API design |
| 183 | מצב VIP נקרא מ-`campaigns` והמחיר מ-`subscription` | "VIP: ללא" לצד מחיר שכולל VIP — סתירה על אותו מסך | `3d3d785`, `8c76cd2` | DOM / UI |
| 184 | `loadHome` לא רץ בכניסה הראשונה | KPI "לידים החודש" נשאר "—" עד ניווט החוצה וחזרה | `1f2c055`, `81943e8` | DOM / UI |
| 185 | הורדת PDF cross-origin | `fetch` ל-`/download` שמחזיר 302 ל-URL חתום → תגובה opaque → "עדיין בהכנה" כוזב | `4a4eb81` | API design |
| 186 | כפתור ביטול נתקע ב-"⏳ מבטל..." | שחזור רק בנתיבי שגיאה, לא ב-`finally` | `ac8ce18` | DOM / UI |
| 187 | `revise` נגע בכפתור הפרסום | ה-`finally` שחזר `button:first-child` שהוא כפתור הפרסום → נראה פעיל בלי אישור-אחריות | `c6ac04f` | DOM / UI |
| 188 | `continue` תקוע אחרי כשל סריקה | הכפתור הושבת בתחילת הסריקה ושום דבר לא הפעיל אותו מחדש בכשל | `c954f63` | DOM / UI |
| 189 | `connectGcal` עשה redirect מלא-דף | ה-reload מחק את `WIZ`/`APP` → המשתמש נזרק מיצירת הקמפיין | `38efde1` (popup) | DOM / UI |
| 190 | הפניות JS לא-מוגנות לאלמנטים שהוסרו | קריסה על מחיקת המיקום האחרון / על אלמנט חסר בהגדרות | `ee07cc5`, `c978458` | DOM / UI |
| 191 | `setKb` coupling גלובלי | שדה-קלט חסר במסך התמיכה | `c79af7b` | DOM / UI |
| 192 | `_dev_bypass_user` זייף רק `status` | QA שניצל trial נחסם בשער-תשלום אמיתי (נכשל ב-503 בלי Pelecard) | `5d18766` | לוגיקה עסקית |
| 193 | `_generate_filtering` — זנב לא-reachable | dead code | `d23bc21` | API design |
| 194 | `system_v1/v2.txt`, `problem_1.txt` — פרומפטים מתים | קוד ופרומפטים שאינם נטענים בזרימה | `7.4.X#dead` (מתועד) | API design |
| 195 | `_charge_subscription` — `KeyError` לא-תפוס | whatsapp + `vip_owner_alerts=true` → KeyError אחרי CAS+attempt → מנוי תקוע | `c2ff034` | לוגיקה עסקית |
| 196 | `create_agent_notification` קרא את הטלפון השגוי | `vip_alert_phone` במקום `agent_alert_phone` — הקוד וה-RPC סטו מה-docstring | `c28cd52` (migration 0127) | עקביות DB |
| 197 | `charge_campaign` — `SKIPPED` בלי מעבר terminal | ה-crons בררו את הקמפיין בכל tick → `capture_alert` 1440×/יום/קמפיין | `283a3ca` | Terminal-state |
| 198 | `premium gates` עברו ל-campaign-level | features שמוגדרים **לפני** go-live החזירו 402/409 למשתמש Premium | `4448e7d` | לוגיקה עסקית |
| 199 | `storage` — HTTP/2 GOAWAY הפיל 2/3 העלאות | חיבור משותף שנסגר בצד השרת; ההתאוששות הגיעה רק מה-retry של ה-runner (+81s) | `c029969` | תאימות לחוזה ספק |
| 200 | `JSONDecodeError` מ-storage3 לא סווג | מסלול-בריחה שלא מופה ל-transient | `471ae5e` | סיווג שגיאות |
| 201 | כפל דיווח ל-Sentry | אותה שגיאה נרשמה פעמיים (logger + capture) | `7fee238` | API design |
| 202 | `/health` הציף את uvicorn access-log | liveness-probe של Render הצפה את הלוגים | `3d0f4a4` | לוגיקה עסקית |
| 203 | `insights` של סנדבוקס נשלח ל-Graph האמיתי | `dashboard_service` עקף את ה-MetaClient seam → `code=100/33` → unknown → 500 | `e7b046a` | API design |
| 204 | 503 של ספק-תמונות בכל 3 הניסיונות | ads נשארו בלי תמונה; הלוג רץ על gemini אך נקרא "openai" (שמות מטעים) | `73ec872` | סיווג שגיאות |
| 205 | `thinkingBudget` דלוק כברירת-מחדל ב-Gemini | ה-thinking צרך את כל `maxOutputTokens` בקריאות קצרות → candidate ריק → "תגובה פגומה" | `b3ceb3e` | תאימות לחוזה ספק |
| 206 | `regenerate_slot_image` לא נותב לספק הנכון | רענון-ידני חזר ל-openai בעוד ה-batch רץ אצל ספק הלקוח | `a9159cb` | סיווג שגיאות |
| 207 | טסטים ביצעו חיבור-רשת אמיתי | כל טסט-flow ניסה להתחבר ל-`SUPABASE_URL` פיקטיבי; suite 66s→26s אחרי התיקון | `a9159cb` | API design |
| 208 | `pip-tools` שבר את ה-lockfile | כשל CI מול pip 26.2.x | `e37b3b8` | תאימות לחוזה ספק |
| 209 | `ruff` rule-set לא מקובע | dependabot נחסם | `a655a78` | API design |
| 210 | `.github` נמחק בטעות | ה-CI workflow ובדיקת ה-inline-JS נעלמו | `3a8af5f` → `890d53a` | API design |

---

## דפוסים שקלאוד קוד פספס (ותוקנו בדרך אחרת)

זה החלק המעניין ביותר בהיסטוריה הזו. הפרויקט פותח כמעט כולו עם Claude Code, **ובמקביל** רץ עליו סוקר-אוטומטי שני
(Cursor Bugbot). התוצאה מדידה:

| מדד | ערך |
|---|---|
| commits שנושאים בכותרת ייחוס ל-Cursor / Bugbot | **130** |
| commits שמזכירים Cursor/Bugbot בכותרת או בגוף | **212** |
| commits של "תיקון-של-תיקון" (follow-up / רגרסיה / סבב n) | **45** |

כלומר: **רוב מוחלט של הבאגים בפרויקט הזה לא נתפסו ע"י מי שכתב את הקוד, אלא ע"י סוקר חיצוני.**
חמישה דפוסים חוזרים מסבירים כמעט את כולם:

### א. הנחה על מצב חיצוני מתוך אינדיקטור עקיף
הדפוס הכי נפוץ, ובעל הנזק הגבוה ביותר. הקוד ראה סימן אחד והסיק ממנו מסקנה על סימן אחר:
"אין refresh cookie ⟹ אין session" (`944b45c`), "לא transient ⟹ הטוקן מת" (`bc71425`),
"`[]` מ-Google ⟹ אין אירוע" (`c0ac42c`), "`busy` חסר ⟹ היום פנוי" (`760c84f`),
"`delete` no-op ⟹ נמחק" (`5deee2f`), "`raw_campaign=None` ⟹ `leads=0`" (`5813e00`),
"`trial_ends_at` עתידי ⟹ שילם" (`d4a6911`).
**מדוע פוספס:** כל אחד מהם נראה סביר בקריאה מקומית של הפונקציה. רק מי שבודק את ה-flow מקצה-לקצה
ושואל "מה עוד יכול לגרום לסימן הזה?" תופס אותם.

### ב. אסימטריה בין flows מקבילים
הקוד נכתב ל-flow אחד, טופלו ה-edge-cases שלו, ואז הועתק לשני — בלי ה-edges.
`delete_event` קיבל טיפול ב-no-credentials אבל `list_events` לא (`c0ac42c`);
`optimization_push` קיבל את ה-guard על `step=='finalize'` אבל `lead_form_push` לא (`839bb48`);
ענף whatsapp ב-`_today_count` היה best-effort והענף המקביל לא (`beee243`);
`campaign_push` עבר ל-mixin ו-`optimization_push` נשאר עם tuple ידני (`0403d9d`).
**מדוע פוספס:** בקריאת ה-diff של ה-flow שתוקן הכול נראה נכון. ה-flow המקביל לא בדיפ.
זו בדיוק הסיבה שכלל 12 נוסף ל-`CLAUDE.md` — **אחרי** שבעה findings רצופים.

### ג. תיקון שמייצר את הבאג הבא
45 commits הם תיקון-של-תיקון:
`92fba3a` — ה-linkage שהוסף בתוך הלולאה הגדיל את חלון ה-orphan;
`67366bc` — התיקון ל-race שבר את ה-routing, ושני findings של Cursor היו סותרים;
`60ee35b` — ההרחבה של `_with_retry` הייתה **dead code** כי ה-seams תפסו קודם;
`c6ac04f` — התיקון ל-`finally` הפעיל את כפתור הפרסום בלי consent;
`56eb671` — best-effort שהחליף 503 ב-500;
`98baba9` — ה-TTL recovery שנוסף בתיקון קודם לא עבד כלל בגלל דקדוק PostgREST;
`5c34a50` — בדיקת ה-rowcount שנוספה דחתה `dict` שהוא הצלחה תקינה.
**מדוע פוספס:** התיקון נבדק מול התסמין שדווח, לא מול ההשלכות שלו על שאר המערכת.

### ד. שינוי סמנטי בשקט בשכבת ה-boundary
`maybe_single`/`single` של PostgREST מחזירים לפעמים `dict` ולפעמים `list` בן-איבר-אחד;
8 מקומות נשברו על זה (`b38bf8e`, `42f30ca`, `e46f658`, `7c06aef`, `781a041`).
`facebook-business` מחזיר `AbstractCrudObject` ולא `dict` (`ba83880`).
`bool` הוא subclass של `int` (`09d397c`, `414fb82`, `066db8f`).
`PostgREST` חותך ב-1000 שורות בשקט (`3b52acc`).
`.or_()` נשבר על ISO timestamp (`98baba9`).
**מדוע פוספס:** אלו התנהגויות של ספרייה שלא מתועדות בחתימת הפונקציה. הטסטים ממקקים את ה-DB
ומחזירים את הצורה ה"נכונה" — כך שהצורה השנייה **מעולם לא נבדקה**.

### ה. הטסט לא יכול היה להיכשל
`2e452f1` — התנגשות constraint במיגרציה: "הטסטים לא תפסו כי הם ממקקים את ה-DB (לא מריצים SQL migrations)".
`9b6712c` — שינוי חתימה שבר 2 call-sites: "הטסטים לא תפסו כי ה-mock הוא `f_sync(*a, **k)` גמיש".
`8ceaf0b` — רשימה משוכפלת Python↔SQL; התיקון הוסיף טסט ש**מפרסר את המיגרציה** ומשווה.
**מדוע פוספס:** יש 108 קבצי טסט ואלפי טסטים ירוקים — אבל הם בודקים את הקוד מול mock שכתב אותו מפתח,
לא מול המערכת האמיתית.

---

## המלצות ל-CLAUDE.md

חמישה כללים קונקרטיים שהיו מונעים את רוב הבאגים ברשימה. שלושה מהם משלימים כללים קיימים
(11 ו-12 כבר קיימים וכיסו חלק) — השאר חדשים.

### כלל א' — סנטינל מפורש: `[]` / `None` / `0` חייבים משמעות אחת
> פונקציה שיכולה גם "לא למצוא" וגם "לא לרוץ בכלל" (אין credentials, פיצ'ר כבוי, קלט חסר)
> **אסור** שתחזיר את אותו ערך בשני המקרים. `[] ≠ "אין"`; `0 ≠ "לא נמדד"`; `None ≠ "ריק"`.
> החזר `list | None`, `int | None`, או tuple `(found, value)`, ותעד בחתימה איזה ערך אומר מה.
> **פר-flow:** אם flow אחד קיבל סנטינל, ה-flow המקביל חייב אותו (זה כלל 12ה, שנשבר שוב ושוב).
> *היה מונע:* `c0ac42c`, `5deee2f`, `760c84f`, `5813e00`, `ba5709c`, `03be86b`, `7.1#4`.

### כלל ב' — `boundary shape guard`: כל תגובה של ספרייה חיצונית עוברת normalizer יחיד
> **אסור** לגעת ב-`response.data` של PostgREST, ב-payload של SDK, או ב-JSON של ספק — ישירות.
> כל קריאה עוברת דרך helper של הפרויקט (`first_row` / `has_returning_rows` / `_normalize_id` /
> `_normalize_actions`) שמטפל בכל הצורות האפשריות. **הטסט חייב לכסות את כל הצורות**, לא רק את זו
> שה-mock מחזיר: `dict`, `list` בן-איבר, `list` ריק, `None`, ו-`bool` במקום `int`.
> *היה מונע:* `b38bf8e`, `42f30ca`, `e46f658`, `7c06aef`, `781a041`, `ba83880`, `09d397c`, `414fb82`, `066db8f`, `ee4945c`, `5c34a50`.

### כלל ג' — כל timeout חייב להיות ברמת ה-I/O, וכל write חייב `search-before-create`
> (א) `asyncio.wait_for` סביב `to_thread` **לא מבטל את ה-thread** — ה-write ירוץ פעמיים.
> timeout חייב להיות ברמת ה-client (`requests` `timeout=` דרך ה-session, `httpx`, `AsyncOpenAI(timeout=)`),
> ו-`wait_for` נשאר watchdog בלבד עם ערך **גבוה** מה-socket.
> (ב) לפני כל `create` בלתי-הפיך אצל ספק חיצוני — חפש קודם לפי identifier יציב, או כתוב שורה מקומית
> עם UNIQUE **לפני** הקריאה. אחרי ה-`create` — persist מיד (save-as-you-go), לא ב-`finalize` מרוכז.
> *היה מונע:* `a8e02bf`, `9ac222c`, `6b17244`, `92fba3a`, `3a24128`, `20ee07c`, `3#3`.

### כלל ד' — כל מסלול-סיום כותב terminal-state עמיד; reserve-first על האות
> כל handler/cron: `except TransientError: raise` → retry. **כל השאר** (permanent + unknown) →
> כתיבת terminal-state על ה-**entity** (לא רק על ה-job) + Sentry + `return`. אין מסלול שלישי.
> **סדר הכתיבות:** ה-signal לאדם (escalate / alert / capture) קודם ל-CAS שמוציא את השורה מה-re-selection.
> **בדיקת self-check לפני commit:** לכל query של cron — "כשהפעולה מצליחה, איזה תנאי ב-`WHERE` הופך False?"
> אם התשובה "אף אחד לא מובטח" — חסרה עמודה.
> *היה מונע:* `20ee07c`, `38f402a`, `eac70b1`, `095f8f9`, `a75ab3b`, `b64ff5c`, `24c64b5`, `36b433a`, `14b65af`, `283a3ca`, `b3caa6e`, `9aefb1b`, `25ca676`.

### כלל ה' — טסט שלא יכול להיכשל אינו טסט
> לפני שמסמנים תיקון כ"מכוסה בטסט", חובה **לאמת שהטסט נכשל בלי התיקון** (הרבה מה-commits כאן כבר עושים
> זאת ומציינים "אומת שנכשל בלי התיקון" — זה צריך להיות הכלל, לא היוצא-מן-הכלל). בנוסף:
> - **mock גמיש (`*args, **kwargs`) אסור** ל-helper פנימי — הוא מסתיר שינויי חתימה (`9b6712c`).
> - **ערך שמקודד בשני מקומות** (Python + SQL, enum + CHECK, frontend + backend) חייב טסט-CI
>   ש**מפרסר את שני המקורות ומשווה** (הדפוס של `8ceaf0b` ו-`4e3f425`).
> - **מיגרציות SQL אינן מכוסות** ע"י טסטים שממקקים את ה-DB. כל מיגרציה חדשה דורשת בדיקת syntax/
>   התנגשות-שמות לפני merge (`2e452f1` הפיל deploy).
> *היה מונע:* `2e452f1`, `9b6712c`, `8ceaf0b`, `4e3f425` (4#5), וכל מחלקת ה-drift בין Python ל-SQL.

---

## נספח — מתודולוגיה

- ההיסטוריה שהתקבלה בסשן הייתה **shallow** (304 commits). `git fetch --unshallow` חשף **935**.
  כל הניתוח נעשה על ההיסטוריה המלאה.
- סינון מועמדים: `git log --no-merges` + grep על `fix|תיקון|באג|bug|race|regression|hardening|Cursor|Bugbot`
  → 256 commits בכותרת + 73 נוספים שהוזכרו רק בגוף.
- לכל מועמד נקרא גוף ה-commit המלא (הודעות ה-commit בפרויקט מתעדות במפורש: הקוד הישן, השורש, והתיקון).
  מדגם של diffs אומת ישירות (`de1507d`, `db3ec53`, `09d397c`) והתאים במדויק לתיאור.
- באגים שהופיעו במסמכי `docs/code-reviews/` אך **לא** נמצא להם commit-תיקון — סומנו כמתועדים בלבד
  (מופיעים ברשימה רק כשצוין "מתועד") ולא נספרו כבאגים שתוקנו.
