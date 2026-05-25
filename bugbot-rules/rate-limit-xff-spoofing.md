# rate-limit-xff-spoofing

**CRITICAL — security control bypass**

Detect rate-limiter, abuse-detection, or any security decision that reads `X-Forwarded-For` (or `X-Real-IP`, `Forwarded`) directly without validating that the immediate peer is a trusted proxy.

## Flag when ALL apply

1. Code reads one of:
   - `request.headers["x-forwarded-for"]` / `req.headers["x-forwarded-for"]`
   - `request.headers["x-real-ip"]`
   - `request.headers["forwarded"]`
   - Manual parsing of `X-Forwarded-For` taking the leftmost / rightmost segment
2. The value is used for:
   - Rate-limit key
   - Abuse / block list lookup
   - Audit / fraud-detection logs
   - IP-based authentication / allowlisting
3. The framework / app has NOT been configured with an explicit trusted-proxy list:
   - FastAPI / Starlette: no `ProxyHeadersMiddleware(app, trusted_hosts="...")` configured with specific values.
   - Express: no `app.set('trust proxy', <specific value>)`.
   - Flask: no `ProxyFix(app, x_for=N)` with a specific hop count.

## Fix

Configure middleware first, then read `request.client.host` / `req.ip` (which the middleware has corrected to the real client IP).

If no proxy fronts the service, do NOT read the header at all — use `request.client.host` directly.

## False positives

- Internal-only routes behind authenticated VPN where IP doesn't gate anything.
- Diagnostic / logging-only use (still flag for review — these often slip into security decisions later).

## Severity

CRITICAL — bypasses the entire rate limiter; attacker spoofs the header per-request and faces no limit.
