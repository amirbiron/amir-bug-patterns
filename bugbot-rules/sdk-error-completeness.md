# sdk-error-completeness

Detect external-SDK calls where the exception handler is too narrow, mis-orders subclass-vs-superclass, or fails to catch async-task cancellation properly.

## Flag when ANY apply

1. **Narrow base in `except`.** SDK call wrapped in `try/except SpecificError` where `SpecificError` is a subclass of the SDK's documented base class (`anthropic.APIError`, `googleapiclient.errors.HttpError`, `stripe.error.StripeError`, `requests.HTTPError`). Untied SDK exception types propagate uncaught.

2. **Wrong subclass order.** `except APIError` placed BEFORE `except RateLimitError` (where `RateLimitError` is a subclass) — the subclass branch never runs.

3. **`asyncio.gather(return_exceptions=True)` result check uses `isinstance(r, Exception)`.** Since Python 3.8, `asyncio.CancelledError` inherits from `BaseException`, not `Exception` → cancelled tasks miscounted as success. Use `isinstance(r, BaseException)`.

4. **Startup-time SDK init at module / import scope without try/except.** `webpush.set_vapid_details(...)`, `stripe.api_key = ...`, OAuth client init. Malformed keys → uncaught exception → server crashes on boot. Wrap, validate, degrade the feature.

5. **`isinstance(r, Exception)` vs `r is True`** on SDK result objects. SDK return values may be objects with `__bool__` not defined; identity comparison with `True` never matches.

## False positives

- Narrow `except` for intentional propagation (e.g., re-raising an `AppException` that FastAPI handles globally).
- Catching `Exception` in CLI scripts where any failure should print + exit.
- Tests with mocks that always succeed.

## Severity

MEDIUM — production crashes on init, silent miscount on async batch results, retry storms when expected error types aren't recognized.
