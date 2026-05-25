# External SDK patterns (paste into CLAUDE.md)

1. **Catch the SDK's base class, refine inside.** `except anthropic.APIError` (not just `RateLimitError`); subclass `except` blocks ordered subclass-before-superclass.

2. **`asyncio.gather(return_exceptions=True)` result checks use `isinstance(r, BaseException)`**, not `Exception` (CancelledError is BaseException, not Exception since Python 3.8).

3. **Startup-time SDK init wrapped in try/except + format validation.** Bad VAPID keys / missing `mailto:` prefix / malformed OAuth secret must degrade the feature, not crash the boot.

4. **isinstance guards on every external response.** Before `.get()`, `.append()`, `.strip()`, iteration on data from `response.json()` / webhook body / AI output: `isinstance(obj, dict/list/str)`. Numbers: `isfinite()` + range.

5. **Regex on AI/SDK JSON output:** raw strings (`r"..."`), word boundaries (`\b`). Prefer `json.JSONDecoder().raw_decode(s[s.find("{"):])` over greedy `\{.*\}` (breaks on prose).

6. **Pydantic enums from external sources:** use `str | None` with idempotent validation, NOT a strict `StrEnum` — strict rejection drops the entire payload (including valid sibling fields).

7. **SDK env flags:** document and respect (e.g., `OAUTHLIB_RELAX_TOKEN_SCOPE=1` for Google scope drift, `STRIPE_API_VERSION` to pin).

8. **Walrus + truthy on env vars:** `if override := os.environ.get("X"):` treats `""` as falsy. Use `if override is not None:` and `.strip()`.

9. **Implement `__bool__` on result objects** (or check `isinstance(r, SendResult) and r.ok` — never `r is True`).

See `BY-STACK/external-sdk.md`.
