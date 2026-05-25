# window-open-protocol-handoff

Detect frontend code that misinterprets `window.open(url, ...)` returning `null` as a popup-blocker event, when in fact the URL uses a system protocol that the browser intentionally handed off to the OS (returning `null` is normal).

## Flag when ALL apply

1. Code calls `window.open(url, ...)` followed by a guard like `if (!win) { ... }` or `if (win === null) { ... }` that cancels the current operation, shows "popup blocked" error, or returns early.
2. The `url` argument can use a system protocol — i.e., starts with `mailto:`, `tel:`, `sms:`, `file:`, or is dynamically computed and can include those schemes.
3. The cancel branch produces a user-visible failure that abandons legitimate state (e.g., `markAsSent` not called, form not submitted).

## Fix

For system protocols, use an `<a>` element + `.click()`:
```js
const a = document.createElement("a");
a.href = `mailto:${address}`;
a.click();
markAsSent();
```

Or scheme-detect before applying the popup-blocker assumption:
```js
const isSystemProtocol = /^(mailto|tel|sms|file):/.test(url);
const win = window.open(url, "_blank");
if (!win && !isSystemProtocol) { showError("Popup blocked"); return; }
markAsSent();
```

## Related browser-quirk flags (suggest in same review pass)

- `navigator.clipboard.writeText(...)` without try/catch (fails on HTTP).
- `URL.createObjectURL(...)` without matching `URL.revokeObjectURL` in cleanup.
- `setTimeout(fn, delay)` where `delay` is externally sourced and not `isFinite`-guarded.

## False positives

- `window.open` strictly for `http(s):` URLs where popup-blocker check is correct.
- The cancel branch only logs and continues (best-effort, not state-cancelling).

## Severity

MEDIUM — UX-breaking, occasionally state-corrupting when the cancel branch reverts in-flight changes.
