# BY-STACK: Browser-side handoff (mailto:, tel:, clipboard, DOM quirks)

## Relevance — copy this file if your project has...
- ✅ Browser code that opens `mailto:`, `tel:`, `sms:`, or `file:` links
- ✅ Browser code that uses `navigator.clipboard.*`
- ✅ React components with tooltips, dropdowns, or modals that close on outside click
- ✅ CSS resets in a project that uses Tailwind / utility-CSS frameworks
- ✅ Code that creates blob URLs (`URL.createObjectURL`) for previews
- ⏭ Skip if: server-rendered, no browser-side JS, or pure React without browser-API integration

> Cross-link: **R3** (browser API quirks) is the parent pattern. **K4** (XSS) is a separate concern — see `react-frontend.md`.

---

## Pattern 1 — `window.open(mailto:)` returns null (Noa P10)

**Severity:** MEDIUM — legitimate operation cancelled by mistake

### What it looks like
```jsx
const win = window.open(`mailto:${address}`, "_blank");
if (!win) {
  showError("Popup blocked");
  return;  // ❌ cancels mark_sent flow
}
markAsSent();
```

In Chrome, `window.open(url, ...)` returns `null` when `url` uses a system protocol (`mailto:`, `tel:`, `sms:`, `file:`). This is **intentional handoff to the OS**, not a popup-blocker action. The check above misinterprets handoff as block.

### Fix
For system protocols, use an `<a>` element + `.click()`:
```jsx
const a = document.createElement("a");
a.href = `mailto:${address}`;
a.click();
markAsSent();
```

Or detect by URL scheme before deciding the popup-blocker fallback applies:
```jsx
const isSystemProtocol = /^(mailto|tel|sms|file):/.test(url);
const win = window.open(url, "_blank");
if (!win && !isSystemProtocol) {
  showError("Popup blocked");
  return;
}
markAsSent();
```

### Real commits
- Noa `f635304`.

---

## Pattern 2 — `navigator.clipboard.writeText` on HTTP

```js
function copy(text) {
  navigator.clipboard.writeText(text);  // ❌ throws on HTTP; promise rejection unhandled
}
```

The Clipboard API requires a secure context (HTTPS, localhost). On HTTP, `navigator.clipboard` may be `undefined`, or `writeText` may reject.

### Fix
```js
async function copy(text) {
  try {
    if (!navigator.clipboard) throw new Error("Clipboard API unavailable");
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch (err) {
    // Fallback: legacy document.execCommand or show error
    return { ok: false, err };
  }
}
```

### Real commits
- Markdown-Academy `b97d3f5`.

---

## Pattern 3 — Tooltip / dropdown closes on click due to event bubbling

```jsx
<div onClick={closeMenu}>
  <Tooltip>...</Tooltip>  {/* clicks inside bubble up → menu closes */}
</div>
```

### Fix
```jsx
<Tooltip onClick={(e) => e.stopPropagation()}>...</Tooltip>
```

Or use a "click outside" hook that ignores clicks within the inner element's tree (compare `event.target` against the inner ref via `.contains()`).

### Real commits
- Markdown-Academy `315154e`.

---

## Pattern 4 — Global CSS reset overrides utility classes

```css
/* somewhere in legacy CSS */
* { margin: 0; padding: 0; }
```

In a Tailwind project, `space-y-6` translates to margins on children. The global reset has higher specificity (universal selector + direct declaration) and wins.

### Fix
- Use Tailwind's own `@tailwind base` for the reset (Preflight).
- Or scope the reset: `body > * { margin: 0; padding: 0 }` — but this still breaks utilities.
- Best: remove the manual reset and rely on Tailwind / utility-CSS framework's built-in reset.

### Real commits
- Web `c586691`.

---

## Pattern 5 — `URL.createObjectURL` not revoked

```jsx
const url = URL.createObjectURL(blob);  // ❌ never revoked, leaks on every render
return <img src={url} />;
```

### Fix
```jsx
useEffect(() => {
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  setSrc(url);
  return () => URL.revokeObjectURL(url);  // cleanup on unmount or blob change
}, [blob]);
```

### Real commits
- Web `f5cbaf9`.

---

## Pattern 6 — `setTimeout(fn, delay)` / `new Date(value)` with NaN

```js
const delay = parseInt(input);  // user-provided
setTimeout(load, delay);  // ❌ if NaN → React error / immediate or never
```

### Fix
```js
const parsed = parseInt(input, 10);
const delay = Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_DELAY;
setTimeout(load, delay);
```

Same for `new Date(value).getTime()` — guard with `isFinite`.

### Real commits
- EmailFlow `e432866`.

---

## Pattern 7 — `localStorage` partial update of multi-field auth state

```js
localStorage.setItem("token", newToken);  // ❌ refreshToken stays from signup
```

`localStorage` operates per-key; updating just `token` leaves `refreshToken` stale.

### Fix
- Store as one JSON object: `localStorage.setItem("auth", JSON.stringify({token, refreshToken, expires}))`.
- Or always update both atomically: `localStorage.setItem("token", t); localStorage.setItem("refreshToken", r);` and never write one without the other.

### Real commits
- Web `2e5c480`.

---

## Pattern 8 — UI button shown at wrong time relative to slot

```jsx
const showBooked = nowMs > slot_start + 30 * 60 * 1000;  // ❌ short meetings broken
```

If the action is "after the meeting ends", calculate from `slot_end`, not `slot_start + estimate`.

### Fix
```jsx
const showBooked = nowMs > slot_end;
```

### Real commits
- Noa `f4769bf`.

---

## Pattern 9 — Component unmounts before async operation finishes

If the user navigates away while a `useEffect` is mid-await, the subsequent `setState` runs on an unmounted component → warning in dev, memory retention in prod.

### Fix
Cancellation flag:
```jsx
useEffect(() => {
  let cancelled = false;
  async function load() {
    const data = await fetchData();
    if (cancelled) return;
    setData(data);
  }
  load();
  return () => { cancelled = true; };
}, [...]);
```

### Real commits
- Noa `b360c66`, `7444dd9`.

---

## Cross-references

- **R3** — Browser API quirks (this file is the deep-dive)
- **CORE U2** — React state sync (Pattern 9 here is the cancellation-flag variant)
- **CRITICAL K4** — XSS via innerHTML
- **`bugbot-rules/window-open-protocol-handoff.md`**
