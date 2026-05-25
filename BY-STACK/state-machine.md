# BY-STACK: State machines

## Relevance — copy this file if your project has...
- ✅ Status enums driving lifecycle (`Lead.status`, `Order.status`, `Booking.status`, `Conversation.state`)
- ✅ "Touchpoint" operations: a single action that must update multiple coupled fields atomically (status + last_outbound_at + last_activity_type + close-related-task + log-activity)
- ✅ Activity / audit logs that downstream cron / dashboards depend on
- ✅ State transitions with cascade requirements (status → side effects on related rows)
- ⏭ Skip if: pure CRUD without lifecycle semantics

---

## Pattern 1 — Status transition forgets coupled side-effects (CORE U5)

**Severity:** HIGH — silent data corruption; downstream cron / UI breaks

### What it looks like
```python
def apply_chip(lead, target_status):
  lead.status = target_status  # ❌ what else needs to update?
  await session.commit()
```

A status change in this codebase usually requires:
1. `lead.status` = new value
2. `lead.last_outbound_at` = UTC now (if it's an outbound touchpoint)
3. `lead.last_activity_type` = matching `ActivityType.<X>.value`
4. Close any open tasks in `AUTO_CLOSE_TASK_TYPES`
5. Create a new task with `assigned_to = lead.owner_id`, `due_at` in UTC, unique `origin_rule`
6. `log_activity(...)` row
7. `sync_lead_next_action_cache(...)` after flush

### Detection rule
Maintain a project-level **canonical sibling list** per status / per touchpoint type. For every function that updates a status / lifecycle column, verify the sibling list is also touched in the same transaction.

Pattern names to flag: `apply_chip`, `mark_*_sent`, `perform_action`, anything that creates `TEMPLATE_MARKED_SENT` / `PROPOSAL_SENT` / similar terminal activities.

### Real commits
- Noa `bd2b105` — chip set `PROPOSAL_SENT` bypassed `ProposalSentConfirmModal`.
- Noa `75b430a` — chip set `PROPOSAL_SENT` without `proposal_sent_at` → `check_stuck_proposals` broke.
- Noa `df530f3` — `apply_chip` forgot `last_outbound_at` + `last_activity_type`.
- Noa `4cc5a09` — `apply_chip` didn't close old tasks in `AUTO_CLOSE_TASK_TYPES`.
- Noa `3312957` — chip-created task missing `assigned_to` → not visible in owner-scoped views.
- Noa `c99a47a` — `LECTURE_INQUIRY` missing from canonical `AUTO_CLOSE` list.

### False positives
- Migrations / backfill scripts.
- Read-only views.
- Single-field updates genuinely independent (e.g., `last_viewed_at`).

### Recommended mode
**Strict** for known touchpoint functions; **warning** elsewhere.

---

## Pattern 2 — Transition that requires cascading row creation/deletion

`Lead.status = BOOKING_PENDING` or `BOOKED` is supposed to be tied 1:1 with a `Booking` row. Setting the status without creating/managing the booking row leaves the system in an impossible state.

### Detection rule
For every status target in `{BOOKING_PENDING, BOOKED}`: a `Booking` row must exist or `ValidationError` must be raised.

For `{WON, LOST, ARCHIVED}`: must go through `close_lead(...)`, not direct assignment.

For `{BOOKING_PENDING, BOOKED}` → other status: existing active `Booking` must be cascaded (`REJECT` / `CANCEL`) or user must be notified.

### Real commits
- Noa `3312957` — chip set `BOOKING_PENDING`/`BOOKED` without `Booking` row → stuck.
- Noa `75b384a` — `apply_chip` didn't block `BOOKED` + approved booking → orphan Calendar event.

---

## Pattern 3 — Activity log as source of truth (Noa P9)

**Source:** Noa-unique, but the principle generalizes (EmailFlow P1 audit-log-lifecycle is the same idea).

When an UPDATE can fail (CAS rejection, race, filter rejection), the activity log must still record the *intent* with `metadata.applied=false`. Otherwise downstream consumers (cron, dashboard, sorting) think the event never happened.

```python
result = await session.execute(update(Lead).where(...).values(...))
if result.rowcount == 0:
  await log_activity(type="rescheduled", metadata={"applied": False, "reason": "race"})
else:
  await log_activity(type="rescheduled", metadata={"applied": True})
```

Also: `last_activity_type` on the entity must match the `type` written into the activity log (string equality after `.value`). If activity log writes `MEETING_CANCELED` but the column reads `meeting_rejected`, downstream filters break.

### Real commits
- Noa `04cb101` — `_apply_reschedule` rowcount=0 → cron created task early.
- Noa `0aff4a1` — webhook empty changes, sync_token not persisted → infinite loop.
- Noa `0aff4a1` (variant) — `last_activity_type` mismatched activity log `type`.

---

## Pattern 4 — Pydantic schema default overriding caller intent (Noa P4)

**Source:** Noa-unique (Pydantic-heavy). 1-source signal — apply if your project uses Pydantic at API boundaries.

```python
class LeadCreate(BaseModel):
  preferred_contact: ContactChannel = ContactChannel.WHATSAPP  # default ❌
  ...

# Email intake flow:
lead = await create_lead(LeadCreate(full_name=..., phone=...))  # caller omits preferred_contact
# → lead gets WHATSAPP default, even though source was email
```

### Detection rule
For every Pydantic `BaseModel` with a default:
1. Find all callers creating instances **without** the field.
2. For each caller, verify the default matches the source intent (WhatsApp UI default ≠ email-intake default).
3. For enum fields nullable in DB but non-nullable in Pydantic: report schema mismatch.
4. For enum from external source (AI, webhook): consider whether rejecting unknown values = data loss. Sometimes `str | None` + idempotent validation in caller is better than a strict enum.
5. Walrus + truthy on env: use explicit `is not None` and `.strip()` to distinguish `""` from `None`.

### Real commits
- Noa `3203410` — `LeadCreate.preferred_contact` default WHATSAPP applied to email-sourced lead.
- Noa `7001892` — `LeadDraft.service_category` `StrEnum` rejected unknown → lost full_name + phone.
- Noa `f6293e3` — `LeadDraft.full_name` required; AI returned `null` → unnecessary manual review.
- Noa `dc24922` — `TodayActionItem.service_category` required but Lead nullable → validation fails in `/dashboard`.
- Noa `236b072` — walrus `if override := env.get(...)` treated `""` as falsy.

---

## Pattern 5 — State-machine routing loops

When users have multiple roles or when "back" navigation isn't tied to explicit state, infinite loops emerge.

### Real commits
- Shipment-bot `ea648a0` — driver-secretary "back to driver menu" detected secretary role → returned to secretary menu → infinite loop.
- Shipment-bot `9bd99c1` — stale state check filtered `user.role != SENDER` → admins with `SENDER.*` state hit reset loop.
- Shipment-bot `9bd99c1` (variant) — dict comprehension filtered `None` values (`if admin_ctx.get(k) is not None`) → legitimate `original_approval_status=None` was deleted, breaking backtrack.

### Detection rule
For every menu / state-transition handler that branches on user role:
1. Check the *target state*, not just the role (a user can be in `SENDER.SHIPPING_FORM` while also being an admin).
2. Distinguish "missing" from "None" — use explicit key presence (`k in d`), not `is not None`, when None is a valid value.

---

## Pattern 6 — Partial state update on multi-field entity

Touching one field of a logically atomic state object.

### Real commits
- Web `2e5c480` — only `token` updated in localStorage; `refreshToken` stayed stale.
- routine `01c61ac` — `handleMorningTimeChange` sent only `hour`, not `enabled` flag → concurrent requests overwrote each other.
- routine `259c2a3` (token balance) — global query instead of per-child query → all children shared one balance.

### Rule
Token pairs, role + permissions, status + last_*_at, etc., must be updated together. Use a single JSON blob in localStorage, a single API request body, or wrap multi-field updates in a transaction.

---

## Cross-references

- **CORE U5** — partial atomic updates (this file is the deep-dive)
- **CORE U1** — race conditions also affect state machines (CAS on status column)
- **BY-STACK/async-orm.md** — CAS template + audit-log-on-failure pattern
- **`bugbot-rules/linked-field-atomicity.md`**
