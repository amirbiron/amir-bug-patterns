# pii-in-logs

**CRITICAL — privacy / GDPR / compliance**

Detect personally-identifiable information (PII), secrets, or internal-logic disclosures in `logger.*` calls, exception detail returned to clients, and API response bodies.

## Flag when ANY apply

### Forbidden in `logger.*` calls (any level) AND in any API response

- Field names: `email`, `phone`, `mobile`, `from_email`, `to_email`, `address`, `street`, `city`, `zip`, `postal_code`.
- Personal name fields: `name`, `full_name`, `first_name`, `last_name`, `contact_name`, `display_name`, `external_contact_id`.
- Message / chat / email body content (may contain anything).
- Secrets: `password`, `passwordHash`, `password_hash`, `salt`, `refresh_token`, `access_token`, `api_key`, `secret`, `private_key`, JWT bearer tokens.

### Forbidden in API response (logs OK only if log access is controlled)

- Heuristic decision reasons (`"esp:mailchimp.com"`, `"spam_score=0.8"`, internal rule names).
- Internal DB UUIDs / IDs of *other* tenants or users (`courier_id`, `worker_id` not owned by the requester).
- Stack traces, exception class names, framework messages (`Exception: <details>`).
- SQL fragments, query strings, internal route paths.

### Allowed replacements

- PII → email *domain* only (`example.com`), or own-user_id (a value the requester already has), or a non-reversible hash.
- Internal logic → generic localized error message ("Service unavailable, please try again").
- Internal IDs → only IDs of resources the requester owns.

## Pattern matches

- `logger.<level>("... %s ...", x)` where `x` is a variable named like the forbidden list.
- `HTTPException(detail=str(exc))` or `detail=f"... {internal_var} ..."`.
- `raise X from exc` at API surfaces without an explicit safe `detail`.
- Returning ORM rows directly to clients (instead of through a DTO / response model).

## False positives

- `logger.debug` paths verified to be excluded from production log aggregation.
- Internal-only services (admin tools / scripts) — rule overly conservative but worth a quarterly cleanup.
- Generic non-PII identifiers (own user_id, request_id, trace_id).

## Severity

CRITICAL — privacy breach, possible GDPR / regulatory exposure.
