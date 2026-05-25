# linked-field-atomicity

Detect partial atomic updates: code touches one of several coupled fields, forgetting the rest. The "missed" field is later read by another flow → silent inconsistency.

## Flag when ANY apply

1. **Status / lifecycle change** without the coupled timestamps and activity log entries in the same transaction. Examples:
   - `entity.status = "X"` without updating `entity.last_status_change_at` / `last_activity_type`.
   - Moving to `PROPOSAL_SENT` without writing `proposal_sent_at`.
   - Moving to a `BOOKED`-style state without creating / cancelling the related entity row.

2. **External irreversible action without compensating local state.** `await client.send(...)` or `payment.charge(...)` without a preceding INSERT to local DB (with `UNIQUE` constraint) marked "intent" — and follow-up update on success/failure.

3. **Multi-field auth state updated partially.** Updating `access_token` without `refresh_token`. Updating `localStorage["token"]` without `localStorage["refreshToken"]`. Use one JSON blob or always write both.

4. **Partial form-mutation request.** `PATCH /endpoint { hour: 8 }` without sending the `enabled` flag — concurrent requests overwrite each other.

5. **Audit log only on success path.** When the main `UPDATE` can fail (CAS rejection, race), failure branch must still call `log_activity(..., metadata={"applied": False})`. Otherwise downstream consumers (cron, dashboards) infer that the event never happened.

## False positives

- Migrations / backfill scripts (one-shot, not transactional touchpoints).
- Read-only paths.
- Single-field updates that are genuinely independent (e.g., `last_viewed_at` not tied to other fields).

## Severity

HIGH — silent data corruption; downstream flows operate on inconsistent state.
