# react-stale-state-on-prop

Detect React components where local `useState` is initialized from a prop that can change, without a resync mechanism. Symptom: UI shows the old value after the parent refetches; user actions are taken against stale data.

## Flag when ALL apply

1. `useState` is initialized with a value derived from `props.X` or destructured prop.
2. `props.X` is plausibly mutable (comes from a parent's query result, route param, or external state — not a one-time mount value).
3. Neither of these is present:
   - A `key={X}` on the component in its parent (forces remount on change).
   - A `useEffect([X], () => setState(X))` that resyncs.
4. The component sends the local state back to a server (form submit, mutation), where staleness causes corruption.

## Also flag

- Any `useState` / `useEffect` / `useCallback` / `useMemo` called AFTER an early `return null;` / conditional return (Rules of Hooks violation).
- `useCallback` / `useMemo` whose body references a prop/state variable not in its dependency array.

## False positives

- Local-only state (modal open/closed, theme toggle, tab selection).
- Uncontrolled inputs with `defaultValue`.
- Mount-only props (e.g., `user.id` that never changes during the component's lifetime).
- Dep intentionally excludes an unstable reference (TanStack mutation object); a comment should explain why.

## Severity

MEDIUM — silent data corruption when stale state is sent back to the server.
