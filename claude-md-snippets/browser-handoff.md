# Browser-handoff patterns (paste into CLAUDE.md)

1. **`window.open(mailto:|tel:|sms:|file:)` returns `null` in Chrome** — that's OS handoff, NOT popup-blocker. Don't gate `markAsSent()` on `if (!win)`. Use `<a>` + `.click()` for system protocols, reserve popup-blocker check for `http(s):` URLs.

2. **`navigator.clipboard.writeText` requires HTTPS / localhost.** Wrap in try/catch; on failure, fall back to legacy `document.execCommand` or show a user-actionable error.

3. **Tooltip / dropdown closes on click → check event propagation.** Either `e.stopPropagation()` inside the inner element, or "click outside" hook that compares `event.target` with the inner ref via `.contains()`.

4. **`* { margin: 0; padding: 0 }` overrides Tailwind utility classes.** Use `@tailwind base` (Preflight) only; remove manual `*` resets.

5. **`URL.createObjectURL(blob)` must have a matching `URL.revokeObjectURL` in `useEffect` cleanup** — otherwise blob URL leaks accumulate.

6. **`setTimeout(fn, delay)` / `new Date(value)` with externally-sourced number requires `isFinite(value) && value > 0` guard.**

7. **`localStorage` is per-key; multi-field auth state must be atomic** — store as one JSON blob or always write both keys together.

8. **Time-anchored UI ("show after meeting ends") uses `slot_end`, not `slot_start + estimate`.** Short meetings break the latter.

9. **`useEffect` mid-await + unmount: use a cancellation flag** so subsequent `setState` is a no-op.

See `BY-STACK/browser-handoff.md`.
