# external-input-isinstance

Detect missing runtime type / shape guards on values that come from outside the process: API responses, webhook payloads, AI/LLM output, environment variables, CSV imports, parsed MIME headers.

## Flag when ANY apply

1. `.get(key)` / `.append(...)` / `[key]` / iteration on a value originating from `response.json()`, `await request.json()`, `json.loads(...)`, `headers[...]`, or webhook payload — without a preceding `isinstance(obj, dict)` (or `list`) check.

2. `.strip() / .lower() / .split()` / `+ str` on a value that may not be a string — without `isinstance(value, str)` guard.

3. Numeric comparison or arithmetic on an external number without `math.isfinite(n)` (or JS `Number.isFinite(n)`) — `NaN < anything` is `False`, so NaN passes all range checks.

4. Regex with `\b` / escape sequences in a non-raw string literal in Python (`"\b"` is `\x08` (backspace), not word boundary). Require `r"..."` for regex patterns.

5. JSON parsing on AI / LLM output using a greedy regex (`\{.*\}`) instead of `json.JSONDecoder().raw_decode(...)`.

6. `setTimeout(fn, delay)` / `new Date(value)` where `delay` or `value` is from external input, without `isFinite(...)` guard.

## False positives

- Pydantic-validated FastAPI input — Pydantic already enforces shape.
- Internal data structures freshly constructed in our own code.
- `logger.debug` paths that won't run in production.
- Test fixtures and mock data.

## Severity

MEDIUM — crashes a worker / request handler on real-world malformed payloads. HIGH if paired with SQL or eval.
