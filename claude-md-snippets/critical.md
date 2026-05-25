# Critical patterns (paste into CLAUDE.md — security/privacy/data-loss, always apply)

1. **OAuth password takeover.** "Set password" / "register" / "link account" endpoints accepting an email MUST reject the request if an account already exists via OAuth, unless authenticated as that user or proven via verified one-time link.

2. **Rate limiter XFF spoofing.** Never read `X-Forwarded-For` directly for security decisions. Configure trusted-proxy middleware (`ProxyHeadersMiddleware`, `app.set('trust proxy', N)`) — then read `request.client.host`.

3. **Auto-admin by unverified email.** Admin / staff / owner role grants happen only after email verification, or via an invite-link + token from an existing admin. Never trust `request.body.email == OWNER_EMAIL`.

4. **XSS via innerHTML.** Default to `textContent` / JSX text. `innerHTML` / `dangerouslySetInnerHTML` / `v-html` with externally-sourced values requires `DOMPurify` (or equivalent) immediately before assignment. "Admin only" is not a defense.

5. **Network-exposed admin panel.** Server bound to `0.0.0.0` requires authentication middleware *before* any route runs, or a firewall. Otherwise bind `127.0.0.1`.

6. **Secret in response.** User serialization goes through an explicit DTO/response model. Forbidden field names anywhere in API response: `password`, `passwordHash`, `salt`, `refresh_token`, `access_token`, `api_key`, `secret`. Exception messages at API surfaces must not include internal IDs / heuristic reasons.

7. **PII in logs.** Forbidden in `logger.*` and `HTTPException.detail`: `email`, `phone`, `from_email`, `to_email`, names, message bodies, tokens, API keys. Replace with email-domain only, hash, or own user_id. Generic localized error message for user-facing details.

8. **LIKE wildcard injection.** User-supplied prefix in `LIKE` must escape `_` and `%`, or use `.startswith(value, autoescape=True)`, or exact `=`.

9. **Credential dispatch before storage.** Persist OTP / token / link (Redis SET / DB INSERT) BEFORE sending. If persist fails, do not send. No fallback "skip verification" path on storage failure — fail closed.

10. **500 ≠ "invalid credentials".** Login error handling branches: 401/403 → "Invalid credentials"; 5xx → "Service unavailable, try again"; 429 → "Too many attempts". Never collapse 5xx to auth error.

See `CRITICAL-PATTERNS.md` for full rationale and detection rules.
