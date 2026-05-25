# Migration Notes — Meta-Analysis

Notes I wrote *after* cross-referencing the three source documents. Useful for calibrating future pattern-mining: what surprised me, what didn't translate the way I expected, and what to grab on day one of a new project.

---

## 1. Patterns I expected to be universal but weren't

### State-machine completeness
**Where it lives:** Heavy in Noa_Leads (P1 status transitions, P6 touchpoints, P9 activity log). Partial in EmailFlow (P1 reserve-then-fill has overlap). **Almost absent** in the 8-projects scan — most of those projects don't have explicit state machines, they have one-shot transactions or simpler CRUD shapes.

**Takeaway:** State-machine completeness is a Noa-specific intensity, but the *underlying principle* (atomically update all coupled fields) generalizes — that's why it's CORE U5 ("partial atomic updates / linked-field drift") rather than a Noa-only entry. The CRM context just makes the failure mode visible faster.

### Cron infinite loops
**Where it lives:** Central in Noa (P5 — repeatedly). Doesn't appear in EmailFlow (which uses Pub/Sub, not cron). The 8-projects scan has "loops" but they're routing/UI loops (C20 driver-secretary, C27 admin reset), not cron filters.

**Takeaway:** "Cron lacks terminal state" is unique to projects with scheduled retry loops over DB rows. I gave it its own `BY-STACK/cron-jobs.md` despite single-source frequency because the impact is severe and the pattern is sticky (every cron-using project will hit it).

### Pydantic schema defaults overriding caller intent
**Where it lives:** Only Noa (P4). Felt like a general "Python type-hints aren't actually type checks" pattern, but only Noa exercises Pydantic heavily on the API surface.

**Takeaway:** Stack-specific. Lives in `BY-STACK/external-sdk.md` and `state-machine.md` as a side note, not in CORE.

### React hooks ordering / Rules of Hooks violations
**Where it lives:** EmailFlow P2 explicitly. Noa mentions useEffect issues but doesn't formalize. 8-projects has stale closures (C22, C33) which are related but not exactly the same.

**Takeaway:** This made it into CORE U2 because the *family* of bugs (state sync, stale closure, hooks ordering) shows in all 3 sources even when the specific framing differs.

---

## 2. Surprising connections I didn't expect

### "Reserve-then-fill" ≡ "TOCTOU duplicate sends"
EmailFlow framed P1 around Pub/Sub at-least-once delivery and compensating transactions. Shipment-bot framed C5 around Celery beat scheduler + `.delay()` racing on `SELECT ... PENDING`. **Same root cause** — write to DB before the irreversible external action without a UNIQUE constraint or atomic CAS. The vocabularies diverged but the fix is identical:
```
INSERT INTO ... (with UNIQUE) BEFORE the external call
```
This is why CORE U1 is so broad: race conditions, missing await, reserve-then-fill, TOCTOU duplicate sends, and check-outside-lock are all manifestations of the same underlying error.

### "Activity log as source of truth" ≡ "Audit log lifecycle"
Noa P9 said: when `UPDATE` fails (rowcount=0 due to CAS rejection), still log the activity with `metadata.applied=false`, because cron and dashboards consume the log. EmailFlow P1 said: audit logs must record *intent*, not just *completion*, otherwise compliance shows a "send" that never happened. **Same principle** — log the intent before the side effect, log the result after, never lose the event signal in between.

### "VARCHAR(20) too small for enum" ≡ "Integer too small for Telegram ID"
Noa (`2c8263a`) added a new `StrEnum` value longer than `VARCHAR(20)`. Shipment-bot (`b16b99f`) discovered Telegram IDs exceed 2³¹. **Same root cause** — column type chosen too narrow for the actual value space, only caught when a real value hits prod. Both are subsumed under CORE U4 (Postgres/SQL edges) and U6 (migration drift).

### "Stale closure" ≡ "useEffect dep on object reference"
8-projects C22 (`activeChildId` missing from `useCallback` deps) and Noa P3's React fragment (`useEffect` deps on an object reference triggering re-renders that overwrite edits) are the same React-closure-staleness family. Different framings, one CORE entry (U2).

---

## 3. Top-3 patterns to catch from day 1 in a new project

Ordered by frequency-in-sources × severity:

### #1 — CORE U1: Async race conditions
**Why first:** 15+ instances across all 3 sources. By far the single largest bug class in my work.
**Day-1 action:** Before writing the first webhook handler, queue worker, or cron job:
1. Decide the idempotency strategy per endpoint (UNIQUE constraint? Idempotency key in header? Advisory lock?).
2. Wire `INSERT ... ON CONFLICT` or `SELECT FOR UPDATE` or CAS template into a project utility.
3. Add a "race-conditions checklist" item to PR templates: "what concurrent writes are protected by what mechanism?"

### #2 — CORE U2: React state sync from props
**Why second:** Affects every React project the moment it has a form or dropdown synced to backend data. Recovery from this bug is expensive (silent data corruption — wrong `expected_status` sent to backend).
**Day-1 action:** Decide a project-wide convention:
- Default: `<Child key={id} />` on every component that takes data from `useQuery`.
- Or: explicit `useEffect([id])` resync.
- Or: derived state (no local `useState` at all).
Pick one, write it into `CLAUDE.md`, and apply from the first form.

### #3 — CORE U3: External input validation
**Why third:** Crashes appear within weeks of real traffic. Test/sandbox/prod always diverge on shape (Gmail/Meta/Stripe), and the crash is at the worst time (a single user with a malformed payload takes down the worker).
**Day-1 action:** Before *any* `.get()`, `.append()`, `.strip()` on external data:
1. `isinstance` guard.
2. NaN/Inf check for numbers.
3. Raw string + word boundaries for regex on external text.
4. SDK base-class `except` ordered subclass-before-superclass.

Also: every startup-time SDK init (VAPID, OAuth, Stripe) wrapped in try/except — otherwise one bad env var crashes the boot.

---

## Process notes for next time

- **Source-doc structure matters.** EmailFlow's doc was the most useful — explicit P1..P7 list with code commits, false positives, and recommended mode. The 8-projects doc had richer breadth but flatter structure; harder to cross-reference. **Future docs: use EmailFlow's template.**
- **Severity vs frequency should be split from the start.** I initially conflated them in the plan, and the user (correctly) pushed back. Add a `severity` field to every documented pattern from day one so cross-referencing doesn't lose information.
- **One source ≠ unimportant.** The 8-projects security cluster (OAuth takeover, XSS, rate-limit spoofing, hash leak, panel exposure) all came from one source. Promoting them to CRITICAL anyway is correct — frequency is a noisy proxy for severity.
