# BY-STACK: React frontend

## Relevance — copy this file if your project has...
- ✅ React with `useState` / `useEffect` / `useCallback` / `useMemo`
- ✅ Data fetching via TanStack Query, SWR, or similar (frontend state synced from server)
- ✅ Forms, dropdowns, or any component that takes initial value from a prop that can change
- ✅ Browser-side `URL.createObjectURL`, `setTimeout`, or DOM manipulation
- ⏭ Skip if: server-rendered HTML only (no SPA), or React with purely local state

> Cross-link: **K4 (XSS via innerHTML)** in `CRITICAL-PATTERNS.md` is required reading for any React project rendering external strings.

---

## Pattern 1 — useState initialized from a prop that changes (CORE U2)

**Frequency:** Noa, EmailFlow, Web — 3+ instances
**Severity:** MEDIUM (silent corruption when the stale state is sent back to the backend)

### What it looks like
```jsx
function StatusDropdown({ leadId, currentStatus }) {
  const [status, setStatus] = useState(currentStatus);  // ❌
  // currentStatus changes when parent refetches, but status doesn't
  return <select value={status} onChange={...}>...</select>;
}
```
After a list refetch updates the lead's status, the dropdown still shows the old value. User clicks Save, dropdown sends the old `expected_status`, optimistic CAS check on the backend rejects, pipeline reverts.

### Three resync patterns (pick one project-wide)
1. **`key` prop on parent (simplest):**
   ```jsx
   <StatusDropdown key={lead.id} leadId={lead.id} currentStatus={lead.status} />
   ```
   Forces React to remount the component on `id` change, so local state is fresh.
2. **`useEffect` resync:**
   ```jsx
   const [status, setStatus] = useState(currentStatus);
   useEffect(() => { setStatus(currentStatus); }, [currentStatus]);
   ```
3. **Derived state (no local state):**
   ```jsx
   // Render directly from currentStatus, lift edits to parent
   return <select value={currentStatus} onChange={(e) => onChange(lead.id, e.target.value)}>...</select>;
   ```

### Detection rule
Flag `const [s, setS] = useState(props.X)` where `props.X` can change AND there's no `useEffect([props.X])` resync AND no `key={...}` on the component.

### False positives
- Mount-only props (`user.id` that never changes).
- Local-only state (modal open/closed).
- Uncontrolled inputs with `defaultValue`.

### Real commits
- EmailFlow `d84daca`, `3987818` — status dropdown stuck on old value.
- EmailFlow `02f633a` — missing `key={conversationId}` on ReplyBox → state carry-over.
- EmailFlow `b14e3f3` — `seenDraftKey` collision between two messages.
- Web `2e5c480` — only `token` updated, not `refreshToken`.

---

## Pattern 2 — Rules of Hooks violation

### What it looks like
```jsx
function Comp({ data }) {
  if (!data) return null;
  const [x, setX] = useState(data.x);  // ❌ hook after early return
  ...
}
```
Hook count varies across renders → React crashes ("Rendered fewer hooks than expected").

### Detection rule
All `useState` / `useEffect` / `useCallback` / `useMemo` MUST run before any `return null;` / conditional return.

### Real commits
- EmailFlow `e968135`.

---

## Pattern 3 — Stale closure in useCallback / useMemo

### What it looks like
```jsx
const toggleActivity = useCallback((id) => {
  api.toggle(activeChildId, id);  // ❌ activeChildId not in deps
}, []);
```
After switching child, the callback still uses the previous `activeChildId`.

### Detection rule
`useCallback` / `useMemo` body references must all appear in the dependency array. ESLint's `react-hooks/exhaustive-deps` catches most of these — keep it on `error`.

### Real commits
- routine `259c2a3` — `activeChildId` missing → toggle affected previous child.

---

## Pattern 4 — setState after `await` without cancellation flag

### What it looks like
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
Without the `cancelled` check, the second render's `await` finishes and overwrites the first's UI.

### Real commits
- Noa `b360c66` — async `renderTemplate` overwrote UI with stale preview.
- Noa `7444dd9` — `Promise.all` setLoading raced with render.

---

## Pattern 5 — Unstable dep references (TanStack Query mutation objects)

```jsx
const mutation = useMutation(...);
useEffect(() => { mutation.mutate(...); }, [mutation]);  // ❌ mutation identity unstable → infinite re-run
```
TanStack Query's mutation object is recreated each render. Use `mutation.mutate` (stable callback identity) in the dep array, or `useEffect(() => { ... }, [])` with `mutation.mutate` accessed inside (eslint suppression with comment).

---

## Pattern 6 — `URL.createObjectURL` leak

```jsx
const url = URL.createObjectURL(blob);  // ❌ never revoked
```

```jsx
useEffect(() => {
  const url = URL.createObjectURL(blob);
  setSrc(url);
  return () => URL.revokeObjectURL(url);
}, [blob]);
```

### Real commits
- Web `f5cbaf9` — profile picture blob URL leak.

---

## Pattern 7 — `setTimeout(fn, delay)` / `new Date(value)` with non-finite delay

```js
setTimeout(load, parsed);  // ❌ if parsed is NaN, React error
setTimeout(load, isFinite(parsed) && parsed > 0 ? parsed : 1000);  // ✅
```

### Real commits
- EmailFlow `e432866` — `setTimeout(fn, NaN)` crashed.

---

## Pattern 8 — Global CSS reset overriding utility classes

```css
* { margin: 0; padding: 0; }  /* ❌ overrides Tailwind space-y-*, p-*, m-* */
```

Use a scoped reset (e.g., `@tailwind base` only) or remove the `*` selector.

### Real commits
- Web `c586691`.

---

## Pattern 9 — Tooltip / dropdown closes on click due to event bubbling

```jsx
<div onClick={closeMenu}>
  <Tooltip>...</Tooltip>  {/* click inside tooltip bubbles up → closes */}
</div>
```

Stop propagation inside the inner element:
```jsx
<Tooltip onClick={(e) => e.stopPropagation()}>...</Tooltip>
```

### Real commits
- Markdown-Academy `315154e`.

---

## Cross-references

- **CORE U2** — React state sync (this file is the deep-dive)
- **CORE U1** — applies when React calls webhook-bound endpoints (idempotency keys in the request)
- **CRITICAL K4** — XSS via `innerHTML` / `dangerouslySetInnerHTML`
- **R3** — broader browser API quirks (clipboard, mailto:, blob URLs)
- **`bugbot-rules/react-stale-state-on-prop.md`** — standalone rule prompt
