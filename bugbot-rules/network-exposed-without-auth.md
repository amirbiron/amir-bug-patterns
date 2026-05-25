# network-exposed-without-auth

**CRITICAL — RCE / admin takeover**

Detect HTTP servers bound to all-interfaces (`0.0.0.0`, `::`) without an authentication middleware that rejects unauthenticated requests before any route runs.

## Flag when ALL apply

1. Server startup binds to one of:
   - `0.0.0.0`
   - `::` / `[::]`
   - The string literal `"all"` / framework-equivalent
   - Empty/unset bind address that defaults to all interfaces (some frameworks)
2. No authentication middleware is registered to run unconditionally before route dispatch:
   - FastAPI / Starlette: no global `app.add_middleware(AuthMiddleware)` checking every request.
   - Express: no app-level `app.use(authMiddleware)`.
   - Flask: no `@app.before_request` doing auth, or no `Flask-Login` / `flask-httpauth` covering all routes.
3. The application exposes admin / control / write endpoints (panel, settings, debug, admin API).

## Allowed configurations

- Bind to `127.0.0.1` / `localhost` for dev / single-machine deploys (preferred default).
- Authentication middleware AT THE FRAMEWORK LEVEL, rejecting requests lacking valid token / session before any route runs (not just `@require_auth` decorators that can be forgotten on new routes).
- Network-level access controls (firewall, ingress allowlist) documented in the deployment config.

## False positives

- HTTPS termination proxy that enforces mTLS / client certs in front of an otherwise-open server (verify the proxy is actually in front and required).
- Health-check-only endpoint at `:/healthz` is acceptable on `0.0.0.0` if it returns no sensitive data.

## Severity

CRITICAL — anyone with network access to the port has admin / write access; common in dev environments accidentally promoted to prod or exposed via misconfigured cloud security groups.
