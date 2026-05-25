# BY-STACK: Cron jobs / scheduled tasks ("אני רץ לפי טיימר")

## רלוונטיות — העתק את הקובץ הזה אם בפרויקט יש...
- ✅ jobs מתוזמנים (Celery beat, APScheduler, cron, node-cron, Render cron, Heroku scheduler)
- ✅ queries תקופתיים שמסננים שורות ומעבדים אותן ב-batch
- ✅ workers ברקע שעושים retry לכשלים עם מוני attempts
- ✅ אפשרויות race בין ה-scheduler ל-dispatchers ad-hoc (`.delay()`, triggers ידניים)
- ⏭ דלג אם: בלי עבודה תקופתית / מתוזמנת

> Cross-link: **CORE U1** (race conditions) חל כש-cron מתקיים יחד עם dispatchers של webhook / queue על אותן שורות. **R5** (filter scope errors) חי כאן חלקית.

---

## מודל מנטלי

cron job הוא פונקציה ששואלת שוב ושוב "אילו שורות עדיין צריכות עבודה?" ומפעילה עליהן פעולה. שני דברים חייבים להחזיק כדי שתתכנס:
1. **שורה חייבת לעזוב את ה-filter set אחרי עיבוד מוצלח.** אחרת היא מעובדת לנצח.
2. **ה-filter set לא חייב לתפוס שורות שלעולם לא יהיו ניתנות לעיבוד.** אחרת ה-cron נכנס ללולאה בניסיון לטפל בהן.

רוב באגי ה-cron מגיעים מהפרה של אחד מהשניים.

---

## דפוס 1 — בלי terminal state → לולאה אינסופית (Noa P5)

**חומרה:** HIGH — בזבוז compute, שריפת מכסת API, side effects כפולים

### וריאציות

**וריאציה A — filter על `IS NULL` תופס terminal states:**
```python
# Cron: retry classify של leads שבהם lead_id הוא null
q = select(Inbound).where(Inbound.lead_id.is_(None))
```
אבל ה-tagger מסמן חלק מה-inbounds כ-`'spam'` או `'not_business'`, ולגיטימית אין להם `lead_id` ולעולם לא יהיה. הם בלולאה לנצח.

**וריאציה B — `count < MAX` לא תופס מיצוי:**
```python
q = select(Job).where(Job.attempts < MAX_ATTEMPTS, Job.status == "pending")
```
שורה תקועה ב-`attempts == MAX_ATTEMPTS` יוצאת מה-query → היא נשארת `pending` לנצח, לעולם לא עוברת ל-`failed`.

**וריאציה C — filter לא בודק state אחרי הפעולה:**
```python
# Cron: שלח warm followup
q = select(Lead).where(Lead.status == "warm", Lead.last_outbound_at < now() - 7d)
```
אחרי שה-cron יוצר task של follow-up, `last_outbound_at` לא משתנה (ה-task עוד לא נשלח). השעה הבאה, ה-query תופס את ה-lead שוב, יוצר task נוסף.

### כלל לזיהוי
לכל job ב-`jobs/` / `tasks/` / `cron/`:
1. זהה את ה-`WHERE` הראשי של ה-query.
2. שאל: "כשהפעולה מצליחה, איזה תנאי `WHERE` הופך False?"
3. אם התשובה היא heuristic (`lead_id IS NULL`, `count < MAX`, `status IN (...)`), ודא שהפעולה כותבת עמודה ש*מבטיחה* יציאה. אם לא, הוסף עמודת `processing_status` / `done_at` / tag ייעודית.
4. ללולאות retry עם מוני attempts: כש-`attempts == MAX`, עבור עם השורה ל-state סופי (`status='failed'`), אל תשאיר אותה `pending`.

### Commits אמיתיים
- Noa `c608a85` — filter retry של cron `lead_id IS NULL` תפס spam/not_business → לולאה.
- Noa `2b978aa` — filter cron `count < MAX` השאיר שורות שמוצו pending.
- Noa `1c4eb3a` — `check_warm_followups` לא בדק "task נוצר אחרי last_outbound" → לולאה כל שעה.
- Noa `8bfa977` — `detect_dormant` לא דילג על leads עם `FIRST_RESPONSE/RETRY_CALL` פתוחים → תזכורות כפולות.

### מצב מומלץ
**strict** — כל cron query חייב לסנן על עמודה שהפעולה כותבת במפורש.

### False positives
- cron של reporting (logs בלבד, בלי כתיבות DB) — לולאות בסדר.
- job one-shot ב-startup (לא תקופתי).

---

## דפוס 2 — filter צר מדי / סדר שגוי (R5)

### וריאציות

**צר מדי — מוציא מקרים לגיטימיים:**
```python
q = select(Lead).where(Lead.channel == "whatsapp")  # ❌ מפספס leads שמעדיפים email
```

**סדר שגוי — security filter רץ אחרי override:**
```python
if message.contains(FORCE_SEND_KEYWORD):
  send(lead, message)
  return
if blocked_publishers.contains(lead.publisher_id):
  return  # ❌ לעולם לא מגיע לכאן ל-force_send
```

### כלל לזיהוי
1. בדוק **שלמות** של filter: רשום את כל ה-variants של input שה-filter אמור לכסות (channels, statuses, source types). עבור על כל אחד.
2. בדוק **סדר** של filter: filters של deny / block / security באים **קודם**, אחר כך filters של business-logic, ואז overrides של "force include".

### Commits אמיתיים
- Noa `f635304`, `d526948`, `95dcce6`, `ad34858`, `76b20b3` — באגי filter exclusion שונים.
- Facebook-Leads-New `24ad356` — filter blocked-publisher אחרי `force_send`.

---

## דפוס 3 — race של cron + beat-scheduler (CORE U1 specialization)

dispatcher תקופתי (beat) ו-`.delay()` ad-hoc שניהם מנסים לתבוע את אותה שורה.

### תיקון
CAS atomic:
```sql
UPDATE messages SET status='processing'
  WHERE id=:id AND status='pending'
  RETURNING id;
```
בדוק rowcount ב-worker; המשך רק אם קיבלת את השורה.

### Commits אמיתיים
- Shipment-bot `457eea1`.

---

## דפוס 4 — singleton engine ב-Celery / async task runner

engine ברמת module שמקושר ל-event loop של זמן ה-import נכשל כשה-task הבא מקבל loop טרי.

### תיקון
יצירת engine lazy לכל task, או `engine.dispose()` בין tasks. ראה `BY-STACK/async-orm.md` דפוס 4.

### Commits אמיתיים
- Shipment-bot `0f30963`.

---

## דפוס 5 — קריאות sync חוסמות בתוך event loop async

```python
async def my_cron():
  result = send_lead(lead)  # ❌ קריאה sync, חוסמת את ה-loop למשך הזמן
```

אם ה-cron רץ בתוך `asyncio` (FastAPI background, APScheduler async, Render async), קריאות sync חוסמות את כל ה-tasks האחרים.

### תיקון
```python
result = await asyncio.to_thread(send_lead, lead)
# או: await loop.run_in_executor(None, send_lead, lead)
```

### Commits אמיתיים
- Facebook-Leads-New `35ac718`.

---

## דפוס 6 — state מבוזר נראה "עדיין מחכה" כי module של cron מייבא view ישן

```python
# scanner.py
scan_progress = {"status": "scanning"}
def run_scan(): ...

# panel.py
from .scanner import scan_progress
return {"progress": scan_progress["status"]}  # ❌ ה-panel רואה snapshot מזמן ה-import
```

אם `scanner.py` ו-`panel.py` רצים בתהליכים / imports שונים, `scan_progress` מתפצל.

### תיקון
מקור אמת יחיד (שורת DB) שכל ה-callers קוראים בזמן הבקשה, לא globals ברמת module.

### Commits אמיתיים
- Facebook-Leads-New `454e530`, `4cb5c37`.

---

## דפוס 7 — Stale closure: `lastSentMap` גדל בלי eviction

```js
const lastSentMap = new Map();  // אורך חיי תהליך; לעולם לא מתפנה
function push(userId) {
  if (Date.now() - lastSentMap.get(userId) < THROTTLE) return;
  send(userId);
  lastSentMap.set(userId, Date.now());
}
```

דליפת זיכרון — אחרי ימים, ה-map מכיל כל משתמש שאי פעם תיקשר.

### תיקון
הוסף TTL / LRU eviction, או הזז dedup ל-Redis עם `EXPIRE`.

### Commits אמיתיים
- routine `4d91c5c`.

---

## דפוס 8 — באגי קצוות זמן ב-jobs תקופתיים

- `toLocaleTimeString({hour12: false})` יכול להחזיר `"24:00"` בלוקאלים מסוימים → ולידציית 24-hour נכשלת → תזכורות חצות לעולם לא נשלחות (routine `4d91c5c`).
- `timedelta` שלילי מ-clock skew → תצוגת "-3 minutes ago" (Facebook-Leads-New `9b15e0b`).
- ביטוי cron "כל 5 דקות" + זמן עיבוד של 6 דקות → ריצות חופפות.

### תיקון
- השתמש ב-`"00:00"` כחצות קנוני; ולידציה לשעות 0-23.
- `max(timedelta(0), now - last_seen)` לתצוגת "זמן מאז".
- רכישת advisory lock בתחילת כל ריצת cron; דלג אם כבר מוחזק.

---

## דפוס 9 — state במקום-יחיד-כמקור-אמת חי ב-DB, לא ב-globals ברמת module

cross-process imports מתפצלים.

---

## הפניות צולבות

- **CORE U1** — race conditions (תיאוריה כללית)
- **R5** — filter scope errors (הקובץ הזה הוא ה-deep-dive)
- **BY-STACK/async-orm.md** — Celery singleton engine, commits בתוך לולאה
- **`bugbot-rules/cron-terminal-state.md`**, **`filter-too-narrow.md`**
