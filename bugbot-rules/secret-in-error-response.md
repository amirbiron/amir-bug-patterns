# secret-in-error-response

**CRITICAL — secret material / internal-ID exposure**

Detect API responses or exception bodies that leak credentials, password hashes, internal UUIDs of other actors, or framework / debug messages.

## Flag when ANY apply

1. User-like or actor-like ORM object returned to a client *without* passing through an explicit DTO / Pydantic response model that lists allowed fields. ORM-row-to-JSON is forbidden at API surfaces.

2. Forbidden field names anywhere in an HTTP response body:
   - `password`, `passwordHash`, `password_hash`, `salt`
   - `refresh_token`, `access_token`, `api_key`, `secret`, `private_key`
   - JWT bearer tokens in non-cookie response fields
   - Internal-only operational fields (`internal_status`, `decision_factors`, `model_version`)

3. Custom exception class includes internal identifiers in its `message` / `to_dict()` / serialization, then is raised at an API surface. Example:
   ```python
   class InsufficientCreditError(AppException):
     def __init__(self, courier_id):
       super().__init__(f"Insufficient credit for courier {courier_id}")  # ❌ leaks courier_id to client
   ```
   Fix: separate `public_message` (safe) from `detail` (server-only).

4. `raise X` re-raised without conversion to a safe error response; FastAPI / Express default handler emits `{"detail": "<exception repr>"}`.

## False positives

- Tokens in `Set-Cookie` headers (designed for secret transit, not in body).
- Internal-only service endpoints behind authn for staff only — still risky if compromised, but lower severity.
- Tests / mocks.

## Severity

CRITICAL — direct secret-material exposure or assists attacker reconnaissance.
