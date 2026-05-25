# auth-before-irreversible-action

**CRITICAL — auth bypass / OAuth takeover / OTP misuse**

Detect authentication / authorization flows that dispatch an irreversible action (send OTP, link an account, set a password) before persisting the verification state, or that present a fallback path on storage failure.

## Flag when ANY apply

1. **Credential dispatch before storage.** Order of operations:
   ```
   send_otp(user, code)  ❌
   redis.set(f"otp:{user}", code, ex=TTL)
   ```
   If Redis fails after send, user has a code in hand but no verifier matches. Worse, if there's a "skip OTP on Redis miss" fallback path, attacker gains a bypass.

   Correct order:
   ```
   redis.set(f"otp:{user}", code, ex=TTL)
   send_otp(user, code)
   ```

2. **No-OTP fallback on storage failure.** Any code path that proceeds with authentication when verification storage is unreachable. Fail closed.

3. **"Set password" / "register" / "link account" endpoint accepting an email** without verifying the requester actually owns that email or OAuth identity. If an account already exists via OAuth (or any IdP), reject password-setting unless authenticated as that user, OR proven via a verified one-time link mailed to the OAuth-bound email.

4. **Login error handling collapses 5xx → "invalid credentials".** Branch:
   - `401 / 403` → "Invalid credentials" (generic; doesn't leak whether email exists).
   - `5xx` → "Service temporarily unavailable" + alert monitoring.
   - `429` → "Too many attempts."
   Never display "invalid credentials" for DB errors.

## False positives

- Synchronous storage where the dispatch and the persist are in one transaction (atomic).
- Tests with mocked verification storage.

## Severity

CRITICAL — auth bypass, credential takeover, or denial-of-auth-availability masked as user error.
