# privilege-escalation-unverified

**CRITICAL — privilege escalation via unverified attributes**

Detect role / permission grants that depend on a user-supplied attribute (email, claim) without verifying that the user actually owns the attribute.

## Flag when ALL apply

1. Code grants an elevated role / permission (`admin`, `staff`, `owner`, `super_user`, custom high-privilege role).
2. The grant decision is based on a user-supplied value at registration / login / link time:
   - `request.body.email == OWNER_EMAIL` (or any allowlist comparison).
   - A claim from an unverified JWT.
   - A header value (`X-User-Role`).
   - A value from a self-asserted profile field.
3. The grant happens BEFORE one of:
   - Email verification (token mailed, `email_verified_at` set).
   - Out-of-band action by an existing admin (invite token).
   - Possession proof of an OAuth identity (token from IdP).

## Required pattern

Elevated role grants must be gated by an explicit verification:

```python
if user.email_verified_at is None:
  raise NotVerified()
if request.body.email == settings.OWNER_EMAIL:
  user.role = "owner"
```

Or via invite tokens issued by existing admins:

```python
invite = await get_invite_by_token(request.body.token)
if invite and invite.role == "admin" and invite.email == request.body.email:
  user.role = "admin"
  await invite.consume()
```

## False positives

- Read-only role display (showing "you are admin" UI when the role is already trusted).
- Test fixtures / seed data.

## Severity

CRITICAL — attacker who knows an admin's email creates an account, never verifies, gains admin role.
