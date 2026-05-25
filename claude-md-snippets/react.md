# React frontend patterns (paste into CLAUDE.md)

1. **`useState` from a changing prop must resync.** Pick one project-wide:
   - `<Child key={props.id} ...>` (force remount, simplest)
   - `useEffect(() => setX(props.x), [props.x])` (resync)
   - Derived state (read prop directly, no local copy)

   ❌ `const [s, setS] = useState(props.id);` alone — stale on prop change.

2. **All hooks before any conditional return.** No `if (!data) return null;` followed by `useState(...)`.

3. **`useCallback` / `useMemo` deps must include every prop/state used in the body.** Stale closures (e.g., `activeChildId` missing) make actions affect the previous selection. Keep ESLint `react-hooks/exhaustive-deps` on `error`.

4. **`setState` after `await` must check a cancellation flag** (`let cancelled = false; return () => { cancelled = true; }` in `useEffect`).

5. **Never include unstable identities in deps** (TanStack Query mutation objects, fresh `{}` literals).

6. **Cleanup `URL.createObjectURL` / event listeners** in `useEffect` return.

7. **Multi-field auth state is atomic.** Update access token + refresh token together (one JSON blob in `localStorage`, or both writes wrapped in a try block that rolls back on failure).

8. **`setTimeout(fn, delay)` / `new Date(value)` with externally-sourced input requires `isFinite()` guard.**

9. **Use `textContent`, not `innerHTML`, with user-supplied strings** (XSS — see CRITICAL K4).

See `BY-STACK/react-frontend.md` for code examples.
