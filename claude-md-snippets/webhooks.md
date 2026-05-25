# Webhook patterns (paste into CLAUDE.md)

1. **Reserve before fill.** INSERT to local DB with `UNIQUE` constraint or idempotency key BEFORE any irreversible external call (Gmail draft, SMS, payment). On `IntegrityError`, return 200 (duplicate, ignore). Never `commit()` after `await client.X()`.

2. **CAS on shared cursors.** When two webhooks can read the same `sync_token` / `history_id` / cursor, advance it via `UPDATE ... WHERE id=:id AND token=:expected RETURNING ...`. Branch `IS NULL` for nullable values.

3. **Persist cursor on every call, even empty.** If the provider returns `changes=[]` with `next_sync_token`, write the token. Otherwise infinite loop.

4. **Signature verification before any processing.** Use the provider's verifier (`stripe.Webhook.construct_event`, Meta HMAC-SHA256, GitHub `X-Hub-Signature-256`). Compare with `hmac.compare_digest`, never `==`. Read raw bytes, not re-encoded text.

5. **Trusted proxy for IP-based decisions.** Configure `ProxyHeadersMiddleware` / `app.set('trust proxy', N)` with explicit hop count. Then read `request.client.host`. Never read `X-Forwarded-For` directly.

6. **Acquire rate-limit slot AFTER work-validity check.** Spam / not-business should not consume slots reserved for real work.

7. **No fallback "skip verification" on storage failure.** If Redis SET / DB INSERT of OTP fails, do not send the SMS. Fail closed.

8. **Beat scheduler + `.delay()` race:** atomic `UPDATE ... WHERE status='pending' RETURNING id`, check rowcount before sending.

See `BY-STACK/webhooks.md` and `CRITICAL-PATTERNS.md` K2 / K9.
