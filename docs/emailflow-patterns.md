# דפוסי באגים חוזרים — EmailFlow

> **מקור**: ניתוח 49 commits של "fix" בענף `claude/add-whatsapp-docs-39NRr`
> ב-3 חודשים אחרונים (Sprint 4-8), בשילוב 11 הכללים הקיימים ב-CLAUDE.md.
>
> **מטרה**: custom rules ל-bug-bot חדש. כל rule מנוסח כ-positive instruction
> ("ודא ש-X") ולא כ-negative ("אל תעשה Y") — pattern matching יציב יותר.
>
> **דירוג**: priority = frequency × severity. P1 = critical & recurring.
> P2 = recurring חמור. P3 = מתחזק. P4 = nice-to-have.

---

## Pattern 1 — Reserve-Then-Fill: רישום DB לפני פעולה חיצונית בלתי-הפיכה

**Priority:** P1 — **HIGH** severity × **6+** הופעות.

**תדירות:** 6 commits ישירים + 4 commits שתיקנו variants.

**דוגמאות:**
- `f847a44` — drafter race: Pub/Sub at-least-once → 9 webhooks מקבילים יצרו
  drafts ב-Gmail לפני שאחד הצליח commit → 9 טיוטות יתומות.
- `401f179` — rate-limit pre-acquire: slot נתפס בlimiter לפני verify של
  הwork; אם אין messages אמיתיות (Green API noise) → quota מבוזבזת.
- `cc7e81a` — Meta webhook partial state: acquire-per-entry בלולאה →
  rollback של DB אבל slots ב-limiter נשארו תפוסים → 429 לא-מוצדק.
- `75c0a47` — audit לפני send: ה-row של "send happened" נכתב לפני
  `client.send_draft()`; כשsend נכשל → compliance trail שיקר.
- `0fdd247` — webhook URL: send-then-update-DB → אם DB נופל אחרי send,
  status לא משקף את מה שיצא.

**הסיבה השורשית:**
"check → external call → DB write" הוא pattern נפוץ אבל פגיע ל-3 כשלים:
1. **at-least-once delivery** (Pub/Sub, retries) — אותה הודעה מטופלת N פעמים
   כי dedup נמצא בסוף.
2. **partial failure** — קריאה חיצונית הצליחה, DB נפל → orphan state בצד 3.
3. **compliance trail mismatch** — log/audit נכתב לפני שהפעולה באמת הצליחה.

**Custom rule prompt:**
> *"בכל handler שעושה קריאה חיצונית בלתי-הפיכה (HTTP POST ל-API חיצוני,
> `client.create_*`, `client.send_*`, `provider.send_*`, שליחת מייל, חיוב,
> מחיקת resource חיצוני), חפש את הסדר הבא:
> (א) האם יש INSERT/UPDATE ב-DB **לפני** הקריאה החיצונית, עם UNIQUE constraint
> או lock that מבטיח dedup?
> (ב) האם יש try/except שמטפל בכשל הקריאה החיצונית עם compensating cleanup
> (delete של ה-resource היתום, או mark status='failed' עם CAS)?
> (ג) האם יש audit_log או metric שנכתב **לפני** הקריאה — אם כן, האם הוא
> מתעד 'intent' או 'completion'? התראת severity גבוהה אם 'completion'
> נכתב לפני שהקריאה חזרה בהצלחה.
>
> דגלים חמורים שמצריכים בדיקה ידנית:
> - `session.commit()` שמופיע *אחרי* `await client.X()` בלי INSERT מקדים.
> - `audit_log.append({action: 'sent'})` לפני `await client.send_*`.
> - lock מקומי (in-memory counter) שמועלה לפני verify של ה-work, בלי
>   release על failure path."*

**False positives (warning mode מומלץ, לא strict):**
- **Read-only external calls** (GET ל-Stripe לסטטוס, search Gmail API) — אין צורך ב-reserve.
- **Analytics/metrics best-effort** (Sentry, Datadog send) — fire-and-forget לגיטימי.
- **Background jobs שכבר picked-up מ-queue** — ה-queue הוא ה-reservation.
- **Tests עם mocks** — patterns רגילים נשברים שם.

---

## Pattern 2 — React State Stale on Prop Change / Hooks Ordering

**Priority:** P1 — **MEDIUM-HIGH** severity × **12** הופעות (frequency #1).

**תדירות:** 12 commits — הקטגוריה הכי תכופה.

**דוגמאות:**
- `e968135` — Rules of Hooks violated: `useState` אחרי early return →
  hooks count משתנה → React crash.
- `02f633a` — `key={conversationId}` מקסום: ReplyBox state carryover בין
  שיחות (state ישן הופיע בשיחה אחרת).
- `d84daca` + `3987818` — stale dropdown: status state synced רק על
  `leadId` change; אם list refetch ו-status התעדכן בDB → dropdown תקוע על
  ערך ישן → save משלח expected_status שגוי → revert של pipeline.
- `b14e3f3` — seenDraftKey collision: two messages באותה conversation
  שיתפו draft state.
- `ff398c1` — messageTag לא מתאפס במעבר שיחה.

**הסיבה השורשית:**
React component מקבל prop שמשתנה מ-source חיצוני (TanStack Query refetch,
parent re-render, URL change). State מקומי שתלוי בprop **לא** מסונכרן
אוטומטית — צריך לבחור: `key={id}` (force remount), useEffect on `[id]`,
או derived state. אם בוחרים derived state ושוכחים secondary trigger
(לדוגמה גם `id` וגם `data.status`) — bug שקט.

**Custom rule prompt:**
> *"בכל React component שמכיל `useState` או `useReducer`, חפש את התנאים:
> (א) האם ה-state initialized מ-prop (`useState(props.x)` או דרך useEffect)?
> (ב) אם כן, האם יש מנגנון לסנכרון כשה-prop משתנה — אחד מ:
>    - `key={propId}` בparent → force remount.
>    - useEffect שמאתחל מחדש את ה-state על שינוי הprop.
>    - derived state pattern (לקרוא ישר מ-props ב-render, לא לשמור).
> (ג) האם כל ה-`useState`/`useEffect`/`useCallback` קוראים **לפני** כל
>    `return null` / `return <X/>` / `if (!cond) return ...`?
>    (Rules of Hooks: hooks חייבים סדר יציב בכל render).
> (ד) האם dependency array של useEffect/useMemo כולל את כל ה-props/state
>    שמוזכרים בתוכו? במיוחד: TanStack Query mutation objects אסור (לא יציבים).
>
> דגלים חמורים:
> - `if (!data) return null;` אחריו `const [x, setX] = useState(...)`.
> - `const initial = data.status; const [s, setS] = useState(initial);`
>   בלי key/useEffect מסונכרן.
> - useEffect עם `mutation` ב-deps array (TanStack Query → unstable identity)."*

**False positives:**
- **Local-only state** (modal open/closed, theme toggle, tab selection) — לא תלוי בdata חיצוני.
- **Initial-value-only patterns** שמובחנים: e.g., uncontrolled inputs עם `defaultValue` — לא צריך sync.
- **Component שמקבל prop רק פעם אחת** (mount-only, e.g., user.id) — sync לא נדרש.
- ⚠️ ב-strict mode הrule הזה יזהה כל useState עם prop initialization → noise גבוה. **warning mode מומלץ**.

---

## Pattern 3 — External Input ללא isinstance Guards

**Priority:** P2 — **MEDIUM** severity × **6** הופעות (חוזר למרות כלל 9 ב-CLAUDE.md).

**תדירות:** 6 commits ישירים. חוזר *למרות* שכלל 9 ב-CLAUDE.md כבר מכסה אותו —
סימן שהrule הקיים לא ספציפי מספיק.

**דוגמאות:**
- `6b7dbeb` — `headers["list-unsubscribe"].strip()` קרס על non-str
  (Gmail mock רע / corrupt MIME).
- `46d05f7` — `parsed_json.get(...)` קרס על `parsed_json` שהיה list במקום dict.
- `55b4328` — `parse_webhook` קיבל payload עם `messages` שהוא None במקום list.
- `e432866` — setTimeout/Date עם NaN value → React crash או delay אינסופי.
- `018b166` — Gmail response עם attachment.size = "32KB" string במקום int.

**הסיבה השורשית:**
מתכנתים סומכים על type hints / schema של ספק חיצוני, אבל בפועל:
- Gmail/Meta/Anthropic מחזירים shapes שונים בtests/sandbox/prod.
- json.loads יכול להחזיר list/str/number/bool — לא רק dict.
- Network errors, MIME corruption, mock data → fields מוחזרים כלא-צפוי.

הכלל הקיים ב-CLAUDE.md מנוסח כללי ("isinstance guards לפני .get/.append") —
לא מספיק ספציפי לתפוס את כל ה-call sites.

**Custom rule prompt:**
> *"בכל קוד שעובד עם data ממקור אחד מהבאים:
> (א) `response.json()` / `await request.json()` / `payload = json.loads(...)`.
> (ב) Webhook body / HTTP response body של API חיצוני (Gmail, Meta, Anthropic,
>     Stripe, Twilio, וכו').
> (ג) ה-`parsed_json` field של response מ-AI (Claude/GPT).
> (ד) Headers dict שמגיע מ-MIME parser / HTTP framework.
>
> ודא לפני **כל** `.get()`, `.append()`, `.strip()`, `[key]`, או iteration:
> 1. `isinstance(obj, dict)` אם מצופה dict.
> 2. `isinstance(items, list)` אם מצופה list.
> 3. `isinstance(value, str)` לפני `.strip()`/`.lower()`/`.split()`.
> 4. עבור מספרים — `isinstance(n, (int, float))` + `math.isfinite(n)` עבור
>    NaN/Inf, + `n >= 0` עבור counts/sizes/timeouts.
>
> דגלים חמורים:
> - `response.json()['data']` או `payload.get('x').get('y')` (chained .get
>   על value שיכול להיות None / non-dict).
> - `setTimeout(fn, delay)` או `new Date(value)` ב-frontend בלי isFinite check.
> - parsing של MIME headers עם `.lower()` ישיר על values.
>
> דגל special — Gmail/Meta/Anthropic responses תמיד דורשים פסקת try/except
> סביב ה-parsing, עם logger.exception ולא silent swallow."*

**False positives:**
- **Internal data** שזה-עתה נוצר ע"י קוד שלנו (לא מ-external) — לא צריך.
- **Pydantic-validated input** ב-FastAPI endpoint — Pydantic כבר אוכף isinstance.
- **CLAUDE.md כלל 4 (NaN/Inf)** קיים — strict mode יחזור על אזהרה זהה.
- ⚠️ הrule הזה ירעיש על קוד שמערבב internal+external — להריץ בwarning mode במשך שבועיים, ואז להעלות לstrict.

---

## Pattern 4 — Side-Effect Lifecycle / SQLAlchemy Async Session

**Priority:** P2 — **HIGH** severity × **4** הופעות.

**תדירות:** 4 commits ישירים — אבל כל אחד מהם היה debugging מסיבי
(MissingGreenlet הוא bug שלוקח שעות לאתר).

**דוגמאות:**
- `0fdd247` — MissingGreenlet ב-`sync_recent`: ניגוש לattribute של ORM
  object אחרי rollback של ה-session.
- `018b166` — `asyncio.gather` עם session משותף בין tasks → race וcorruption.
- `0e6dc85` — embedding job ניגש לattributes שהפכו stale אחרי commit
  בתוך loop.
- `dfdf975` — Python `.strip()` על field שב-SQL היה צריך `TRIM()` →
  ה-Python expression לא הפעיל את הfilter.

**הסיבה השורשית:**
SQLAlchemy async עם `expire_on_commit=False` (default ב-EmailFlow) מאפשר
גישה ל-attributes אחרי commit — אבל **לא** אחרי rollback, ו**לא** מתוך
task אחר על אותו session. הgotchas:
- rollback (גם משתמע, מ-exception) מנתק את כל ה-ORM objects.
- `asyncio.gather` עם `AsyncSession` אחד = race (לא thread-safe).
- בלולאה: read → commit → read של אותו row → "stale" כי commit refresh-only-pkey.

**Custom rule prompt:**
> *"בכל קוד שמשתמש ב-`AsyncSession`/`async_sessionmaker`/`get_session`:
>
> 1. חפש שימוש ב-`asyncio.gather` או `asyncio.create_task` שמעבירים את
>    אותו session ל-tasks מקבילים. **חמור**: כל task צריך session משלו
>    דרך `async with sessionmaker() as session:`.
>
> 2. חפש גישה ל-attribute של ORM object **אחרי** אחד מהבאים:
>    - `await session.rollback()` במופע ספציפי או דרך exception path.
>    - `await session.close()` / סוף `async with` block.
>    - exception שמטופל ב-caller אבל ה-ORM object מועבר חזרה.
>
>    ⚠️ פתרון: לחלץ primitives (`.id`, `.email`, `.tenant_id`) לפני
>    rollback/close, או לעשות `session.expunge(obj)` במפורש.
>
> 3. חפש לולאה (`for`) שעושה `await session.commit()` בכל iteration וניגשת
>    אחר כך לattributes של row שכבר committed — בלי `await session.refresh(row)`.
>
> 4. חפש Python string ops (`.strip()`, `.lower()`) על Column expression
>    בquery — הם **לא** מופעלים ב-SQL. דרוש `func.trim()`, `func.lower()`.
>
> דגלים חמורים:
> - `await asyncio.gather(*[do_task(session, x) for x in items])` עם session אחד.
> - `try: ... except: await session.rollback(); return entity.name` — ה-name נגיש
>   אחרי rollback רק אם expunge קדם, אחרת MissingGreenlet."*

**False positives:**
- **Sync SQLAlchemy** (sessionmaker רגיל) — חוקים שונים, הrule לא רלוונטי.
- **Session ב-FastAPI dependency** עם scope per-request — בטוח כל עוד אין `gather`.
- **Tests שעוברים session ל-fixture** — pattern לגיטימי כי הtest דטרמיניסטי.

---

## Pattern 5 — PII / Internal Info מודלף ב-Logs או API Responses

**Priority:** P2 — **HIGH** severity (security/compliance) × **5-6** הופעות.

**תדירות:** 5 ישירים + 2 secondary. כלל 3 ב-CLAUDE.md מכסה את ה-API side אבל
לא את ה-logging side — שם רוב הbugים.

**דוגמאות:**
- `401f179` + `6b7dbeb` — `email_address` ב-logs (PII).
- `018b166` — search query עם user data ב-logger.info.
- `75c0a47` — `summary: "heuristic: esp:mailchimp.com"` ב-API response —
  exposed internal logic to client.
- `24e3666` — Meta OAuth HTTP status ב-error response (debug info leak).
- `704bb5b` — שגיאות באנגלית עם stack traces → תורגמו לעברית גנרית.

**הסיבה השורשית:**
מפתחים מוסיפים `logger.info("... email=%s", user.email)` ל-debugging במהלך
פיתוח ושוכחים להסיר. דומה ב-API responses: error message ספציפי לdebug
משאיר את ה-internal logic חשוף.

**Custom rule prompt:**
> *"בכל קריאה ל-`logger.*(...)` או ב-HTTPException's `detail`/`message`,
> חפש שדות שעלולים להכיל PII או internal info:
>
> 1. **PII fields** (אסור ב-log/response):
>    - `email`, `phone`, `from_email`, `to_email`, `address`.
>    - `body` של מייל/chat (יכול להכיל תוכן רגיש).
>    - `name`, `full_name`, `contact_name`, `external_contact_id`.
>    - Raw OAuth tokens, refresh_token, access_token, API keys.
>
> 2. **Internal logic exposure** (אסור ב-API response):
>    - Heuristic decision reasons (`'esp:mailchimp.com'`, `'spam_score=0.8'`).
>    - DB UUIDs פנימיים (`tenant_id`, `user_id` של אחרים).
>    - Stack traces, exception class names, framework messages.
>    - SQL fragments, query strings.
>
> 3. **Replacement patterns מותרים**:
>    - PII → `email_domain` בלבד, או `user_id` UUID (non-reversible), או hash.
>    - Internal logic → generic Hebrew message ("הבקשה נדחתה. נסה שוב מאוחר יותר").
>    - Internal IDs → רק ה-id של ה-resource שלנו, לא של אחרים.
>
> דגלים חמורים:
> - `logger.<level>("... %s ...", x)` כאשר `x` כולל מילים מ-1.
> - `HTTPException(detail=str(exc))` או `detail=f"... {internal_var} ..."`.
> - `raise ... from exc` בלי `detail` משלנו → FastAPI עלול לחשוף את ה-exc."*

**False positives:**
- **Debug log level** (`logger.debug`) — מותר ב-dev, מסונן בprod (אם logging מוגדר נכון).
- **Internal-only services** (admin tools, scripts) — ה-rule שמרני מדי.
- **error message ב-Hebrew גנרי** ("נסה שוב") — לא חושף כלום, false positive גם אם יש %s.
- ⚠️ **strict mode מצרף false positives על debug** — מומלץ warning mode + cleanup quarterly.

---

## Pattern 6 — Pagination & Ordering ללא Secondary Key

**Priority:** P3 — **LOW-MEDIUM** severity × **5** הופעות (זוחל אבל מציק).

**תדירות:** 5 commits. severity נמוך פר-באג אבל המצטבר מעצבן ל-UX.

**דוגמאות:**
- `d84daca` — `Lead.order_by(updated_at.desc())` בלבד → leads עם אותו
  timestamp (created in batch) מקבלים סדר אקראי → pagination cycles.
- `3987818` — `(timestamp, created_at)` tuple ordering ב-CAS — תיקון tie-break.
- `a0c4603` — drafter ranking ללא secondary key → ranking בלתי דטרמיניסטי.
- `e432866` — message order ב-feed לפי `last_message_at` בלבד.

**הסיבה השורשית:**
מפתחים כותבים `.order_by(X.timestamp.desc())` ושוכחים שב-Postgres, שורות
עם אותו ערך מקבלות סדר *unspecified* (לא יציב בין queries). LIMIT+OFFSET
אז גורם לחזרות/דילוגים בין דפים.

**Custom rule prompt:**
> *"בכל `query.order_by(...)` ב-SQLAlchemy או `ORDER BY` ב-SQL גולמי שמסוים
> ב-`limit()`/`offset()` (או cursor pagination), ודא:
>
> 1. ה-`order_by` כולל לפחות 2 expressions כדי להבטיח דטרמיניזם:
>    - ראשי: השדה הסמנטי (e.g., `created_at.desc()`, `score.desc()`).
>    - שניוני: ה-primary key כ-tie-breaker (`Model.id.desc()` או `.asc()`).
>
> 2. אם השדה הראשי הוא TIMESTAMP — היחס בין `timestamp` (event time) ל-
>    `created_at` (DB ingest time) חייב להיות עקבי בכל ה-call sites של
>    אותו entity. תיעדכן אם יש שני call sites עם order_by שונה.
>
> 3. CAS queries (`UPDATE ... WHERE ...`) שעובדות עם 'latest' תנאי —
>    ה-tie-break חייב להיות זהה בכל ה-flow (selector + verifier).
>
> דגלים חמורים:
> - `.order_by(X.created_at.desc()).limit(N).offset(M)` — עליה את ה-id.
> - `MAX(timestamp)` / `LATEST` semantic בלי tuple `(timestamp, id)`.
> - שני query על אותה table עם order_by שונה — אחד includes id, השני לא."*

**False positives:**
- **Queries בלי LIMIT** — סדר לא קריטי, פחות חמור.
- **Aggregations** (`GROUP BY` + `SUM`) — לא רלוונטי.
- **Single-row queries** עם `.first()` או `.scalar_one_or_none()` שמסתמכות על UNIQUE — בסדר.
- ⚠️ **strict mode** יוסיף id לכל query (גם איפה שזה לא חשוב) — מטרידן יותר מעוזר. warning mode מומלץ.

---

## Pattern 7 — Migration / Model Drift

**Priority:** P3 — **MEDIUM** severity × **6** הופעות.

**תדירות:** 6 commits — בעיקר ב-Sprint 5.5 (KB Refactor).

**דוגמאות:**
- `40f855d` — FTS index רק במ-migration, לא ב-model `__table_args__` →
  fresh DB build (test, dev) יוצא בלי הindex.
- `a3a3134` — Alembic revision id ארוך מ-VARCHAR(32) של `alembic_version` →
  migration נכשל ב-Render fresh deploy.
- `cea815d` — test_alembic_revisions עבר ל-AST parsing כי regex matching
  שבר על quotes/merge conflicts.
- `f143e1c` — migration עם DROP column בקוד שעדיין משתמש בעמודה.
- `3f43d91` — CHECK constraint sorted אחרת בין migration למודל.

**הסיבה השורשית:**
שינוי schema נכתב בשני מקומות (migration + model). מפתחים שוכחים לסנכרן —
fresh DB build (test, prod fresh) יוצא שונה מ-DB existing אחרי migration.

**Custom rule prompt:**
> *"בכל PR שמכיל קובץ ב-`backend/alembic/versions/*.py`, ודא:
>
> 1. **כל constraint/index** ב-migration מופיע גם ב-corresponding model
>    `__table_args__`:
>    - `Index(...)` ב-migration → `Index(...)` בtuple של `__table_args__`.
>    - `CheckConstraint(...)` ב-migration → `CheckConstraint(...)` בmodel.
>    - `UniqueConstraint(...)` ב-migration → דומה.
>    - הסדר/שמות חייבים זהים (CHECK constraint expressions מנורמלות בPostgres).
>
> 2. **Migration additive** (לא destructive) אם יש old code שעדיין משתמש
>    בעמודה: DROP COLUMN חייב להיות ב-migration נפרד שמופיע **אחרי** ה-PR
>    שמסיר את ה-callers.
>
> 3. **Alembic revision id** ≤ 32 characters (default `VARCHAR(32)` של
>    `alembic_version.version_num`).
>
> 4. אם ה-PR משנה schema אבל אין מ-migration חדש — דגל אזהרה.
>
> דגלים חמורים:
> - `op.create_index(...)` ב-migration אבל `Index(...)` חסר ב-`__table_args__`.
> - `op.drop_column(...)` באותו PR שמוסיף `Model.col` (לא נמחק עדיין מ-model).
> - revision string > 30 chars."*

**False positives:**
- **שינוי migration-only** (data migration, fixup) — אין שינוי schema, לא נדרש.
- **Index שנוצר ידנית ב-DB** (לא דרך Alembic) — pattern לגיטימי במצבים נדירים.
- **Test fixtures** עם table_args="extend_existing=True" — לא דורש sync.

---

## דפוסים שנשארו מחוץ ל-Top 7

| Pattern | Frequency | Severity | למה לא נכלל |
|---|---|---|---|
| HTML sanitization content vs tags | 2 | MED | מכוסה ע"י כלל 10 ב-CLAUDE.md |
| Hebrew docstring drift | ongoing | LOW | מנוהל דרך policy ב-CLAUDE.md (לא enforceable code-level) |
| Resource leak (sessions/connections) | 2 | MED | מכוסה תחת Pattern 4 |
| Auth / tenant isolation | 3 | HIGH | חשוב אבל נדיר; אכוף ב-`require_api_auth` decorator + tests |

---

## דירוג סופי וטענות פעולה

| Priority | Pattern | Mode מומלץ | Coverage in CLAUDE.md |
|---|---|---|---|
| **P1** | Reserve-then-fill | **strict** | חלקי (כלל 2) — להרחיב |
| **P1** | React state stale + Hooks order | **warning** | חלקי (כלל 7) — להוסיף stale-prop pattern |
| **P2** | External input isinstance | **warning** → strict | קיים (כלל 9) — תופס לא מספיק |
| **P2** | AsyncSession lifecycle | **strict** | קיים חלקי (כלל 5) — להרחיב לgather |
| **P2** | PII/Internal info leak | **warning** | קיים (כלל 3) — להוסיף logging side |
| **P3** | Pagination ordering | **warning** | חסר ב-CLAUDE.md |
| **P3** | Migration/model drift | **strict** (PR-level) | חסר ב-CLAUDE.md |

**המלצה לפריסה הדרגתית:**
1. **שבוע 1** — הפעל P1+P2 ב-warning mode. אסוף false-positive rate.
2. **שבוע 2** — אם FP < 20%, העלה ל-strict. אם > 30%, צמצם prompt.
3. **שבוע 4** — הוסף P3 בwarning mode בלבד (low-severity, אין דחיפות).

**הצעה להוספה ל-CLAUDE.md** אחרי שה-rules יעבדו טוב:
- כלל 12: Reserve-then-fill (Pattern 1).
- כלל 13: AsyncSession concurrency (Pattern 4, הרחבה של 5).
- כלל 14: Pagination secondary key (Pattern 6).
