# BY-STACK: Cron jobs / scheduled tasks ("I run on a timer")

## Relevance — copy this file if your project has...
- ✅ Scheduled jobs (Celery beat, APScheduler, cron, node-cron, Render cron, Heroku scheduler)
- ✅ Periodic queries that filter rows and process them in batch
- ✅ Background workers that retry failures with attempt counters
- ✅ Race possibilities between the scheduler and ad-hoc dispatchers (`.delay()`, manual triggers)
- ⏭ Skip if: no periodic / scheduled work

> Cross-link: **CORE U1** (race conditions) applies when a cron coexists with webhook / queue dispatchers on the same rows. **R5** (filter scope errors) lives partially here.

---

## Mental model

A cron job is a function that repeatedly asks "which rows still need work?" and acts on them. Two things must hold for it to converge:
1. **A row must leave the filter set after successful processing.** Otherwise it's reprocessed forever.
2. **The filter set must not catch rows that will never be processable.** Otherwise the cron loops trying to handle them.

Most cron bugs come from violating one of these.

---

## Pattern 1 — No terminal state → infinite loop (Noa P5)

**Severity:** HIGH — wasted compute, API quota burn, duplicate side effects

### Variants

**Variant A — filter on `IS NULL` catches terminal states:**
```python
# Cron: retry classifying leads where lead_id is null
q = select(Inbound).where(Inbound.lead_id.is_(None))
```
But the tagger marks some inbounds as `'spam'` or `'not_business'`, which legitimately have no `lead_id` and never will. They loop forever.

**Variant B — `count < MAX` doesn't catch exhaustion:**
```python
q = select(Job).where(Job.attempts < MAX_ATTEMPTS, Job.status == "pending")
```
A row stuck at `attempts == MAX_ATTEMPTS` exits the query → it stays `pending` forever, never moved to `failed`.

**Variant C — filter doesn't check post-action state:**
```python
# Cron: send warm followup
q = select(Lead).where(Lead.status == "warm", Lead.last_outbound_at < now() - 7d)
```
After the cron creates a follow-up task, `last_outbound_at` doesn't change (task isn't sent yet). Next hour, query catches the lead again, creates another task.

### Detection rule
For every job in `jobs/` / `tasks/` / `cron/`:
1. Identify the main query's `WHERE` clause.
2. Ask: "When the action succeeds, which `WHERE` condition becomes False?"
3. If the answer is heuristic (`lead_id IS NULL`, `count < MAX`, `status IN (...)`), verify the action writes a column that *guarantees* exit. If not, add a dedicated `processing_status` / `done_at` / `tag` column.
4. For retry loops with attempt counters: when `attempts == MAX`, transition the row to a terminal state (`status='failed'`), don't leave it `pending`.

### Real commits
- Noa `c608a85` — cron retry filter `lead_id IS NULL` caught spam/not_business → loop.
- Noa `2b978aa` — cron filter `count < MAX` left exhausted rows pending.
- Noa `1c4eb3a` — `check_warm_followups` didn't check "task created after last_outbound" → loop every hour.
- Noa `8bfa977` — `detect_dormant` didn't skip leads with `FIRST_RESPONSE/RETRY_CALL` open → duplicate reminders.

### Recommended mode
**Strict** — every cron query must filter on a column that the action explicitly writes.

### False positives
- Reporting cron (logs only, no DB writes) — loops are fine.
- One-shot job at startup (not periodic).

---

## Pattern 2 — Filter too narrow / wrong order (R5)

### Variants

**Too narrow — excludes legitimate cases:**
```python
q = select(Lead).where(Lead.channel == "whatsapp")  # ❌ misses email-pref leads
```

**Wrong order — security filter runs after override:**
```python
if message.contains(FORCE_SEND_KEYWORD):
  send(lead, message)
  return
if blocked_publishers.contains(lead.publisher_id):
  return  # ❌ never reaches this for force_send
```

### Detection rule
1. Check filter **completeness**: list all input variants the filter is supposed to cover (channels, statuses, source types). Walk through each.
2. Check filter **order**: deny / block / security filters come **first**, then business-logic filters, then "force include" overrides.

### Real commits
- Noa `f635304`, `d526948`, `95dcce6`, `ad34858`, `76b20b3` — various filter exclusion bugs.
- Facebook-Leads-New `24ad356` — blocked-publisher filter after `force_send`.

---

## Pattern 3 — Cron + beat-scheduler race (CORE U1 specialization)

A periodic dispatcher (beat) and an ad-hoc `.delay()` both try to claim the same row.

### Fix
Atomic CAS:
```sql
UPDATE messages SET status='processing'
  WHERE id=:id AND status='pending'
  RETURNING id;
```
Check rowcount in the worker; only proceed if you got the row.

### Real commits
- Shipment-bot `457eea1`.

---

## Pattern 4 — Singleton engine in Celery / async task runner

Module-level engine bound to import-time event loop fails when the next task gets a fresh loop.

### Fix
Lazy-create engine per task, or call `engine.dispose()` between tasks. See `BY-STACK/async-orm.md` Pattern 4.

### Real commits
- Shipment-bot `0f30963`.

---

## Pattern 5 — Blocking sync calls inside async event loop

```python
async def my_cron():
  result = send_lead(lead)  # ❌ sync call, blocks the loop for the duration
```

If the cron is running inside `asyncio` (FastAPI background, APScheduler async, Render async), sync calls block all other tasks.

### Fix
```python
result = await asyncio.to_thread(send_lead, lead)
# or: await loop.run_in_executor(None, send_lead, lead)
```

### Real commits
- Facebook-Leads-New `35ac718`.

---

## Pattern 6 — Distributed state seen as "still waiting" because cron module imports stale view

```python
# scanner.py
scan_progress = {"status": "scanning"}
def run_scan(): ...

# panel.py
from .scanner import scan_progress
return {"progress": scan_progress["status"]}  # ❌ panel sees the import-time snapshot
```

If `scanner.py` and `panel.py` run in different processes / imports, `scan_progress` diverges.

### Fix
Single source of truth (DB row) that all callers read at request time, not module-level globals.

### Real commits
- Facebook-Leads-New `454e530`, `4cb5c37`.

---

## Pattern 7 — Stale closure: `lastSentMap` grows without eviction

```js
const lastSentMap = new Map();  // process lifetime; never evicted
function push(userId) {
  if (Date.now() - lastSentMap.get(userId) < THROTTLE) return;
  send(userId);
  lastSentMap.set(userId, Date.now());
}
```

Memory leak — after days, the map has every user who ever interacted.

### Fix
Add TTL / LRU eviction, or move dedup to Redis with `EXPIRE`.

### Real commits
- routine `4d91c5c`.

---

## Pattern 8 — Time-edge bugs in periodic jobs

- `toLocaleTimeString({hour12: false})` can return `"24:00"` in some locales → 24-hour validation fails → midnight reminders never send (routine `4d91c5c`).
- Negative `timedelta` from clock skew → "-3 minutes ago" display (Facebook-Leads-New `9b15e0b`).
- Cron expression "every 5 minutes" + processing time of 6 minutes → overlapping runs.

### Fix
- Use `"00:00"` as canonical midnight; validate hours 0-23.
- `max(timedelta(0), now - last_seen)` for "time since" display.
- Acquire an advisory lock at the start of each cron run; skip if already held.

---

## Cross-references

- **CORE U1** — race conditions (general theory)
- **R5** — filter scope errors (this file is the deep-dive)
- **BY-STACK/async-orm.md** — Celery singleton engine, in-loop commits
- **`bugbot-rules/cron-terminal-state.md`**, **`filter-too-narrow.md`**
