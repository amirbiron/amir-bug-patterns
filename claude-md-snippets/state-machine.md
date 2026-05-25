# State-machine patterns (paste into CLAUDE.md)

1. **Touchpoint completeness.** Any function that updates an entity's status / lifecycle column (`apply_chip`, `mark_*_sent`, `perform_action`) must atomically update the **canonical sibling list** in one transaction:
   - status field
   - `last_outbound_at` (UTC)
   - `last_activity_type` (matching `ActivityType.<X>.value`)
   - Close open tasks in `AUTO_CLOSE_TASK_TYPES`
   - Create new task with `assigned_to`, `due_at`, unique `origin_rule`
   - `log_activity(...)`
   - `sync_lead_next_action_cache(...)` after flush

2. **Status with cascade requirements.** Transitioning to `BOOKING_PENDING` / `BOOKED` requires a `Booking` row or `ValidationError`. Transitions to `WON` / `LOST` / `ARCHIVED` go through `close_lead(...)`, not direct assignment.

3. **Activity log records intent, not just outcome.** When CAS / `UPDATE` returns `rowcount=0`, still log activity with `metadata.applied=false`. Otherwise downstream consumers (cron, dashboard) think the event never happened.

4. **`last_activity_type` column value MUST equal the `type` written to activity log.** Mismatches (e.g., `meeting_rejected` vs `MEETING_CANCELED`) break downstream filters.

5. **Pydantic schema defaults are strict contracts.** When a caller omits a field with a default, the default applies silently. Verify the default matches the source intent (don't default `preferred_contact=WHATSAPP` for an email-intake flow).

6. **Distinguish "missing" from "None" in dict filtering.** Use `if k in d:` not `if d.get(k) is not None:` when `None` is a legal value.

7. **Multi-role users:** state transitions check the *target state*, not just the role. A user can be both driver and secretary; menu routing must select target by explicit state, not role.

See `BY-STACK/state-machine.md` for code examples.
