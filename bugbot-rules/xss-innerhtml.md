# xss-innerhtml

**CRITICAL — DOM XSS**

Detect DOM insertion of externally-sourced strings through unsafe sinks (`innerHTML`, `dangerouslySetInnerHTML`, `v-html`, `outerHTML`, `document.write`, jQuery `.html(...)`).

## Flag when ALL apply

1. Code assigns to one of these sinks:
   - `.innerHTML = ...`
   - `.outerHTML = ...`
   - JSX `dangerouslySetInnerHTML={{ __html: ... }}`
   - Vue `v-html="..."`
   - jQuery `.html(...)`, `.before/after(...)` with string args
   - `document.write(...)`
2. The right-hand side is composed (concatenation, template literal) with a value sourced from:
   - API response (`response.json()`, `useQuery` data)
   - DB row (server-rendered into template)
   - URL parameters / hash / search
   - `localStorage` / `sessionStorage` / cookies
   - Postmessage / WebSocket / SSE payloads
   - User input from any form / input
   - External provider names / display names (Facebook, Google, OAuth profile)
3. The value is NOT passed through `DOMPurify.sanitize(...)` (or `sanitize-html`, or framework-equivalent) immediately before assignment, in the same expression / line.

## Fix patterns

- Default to `textContent` / JSX text nodes.
- If HTML is genuinely required, sanitize inline:
  ```js
  element.innerHTML = DOMPurify.sanitize(externalValue, { ALLOWED_TAGS: ["b","i","em","strong"] });
  ```
- For React lists: render with text nodes, not `dangerouslySetInnerHTML`.

## Defense reminder

"Only admins see this panel" is **not** a defense — admins are exactly the targets attackers want.

## False positives

- Static / hardcoded HTML strings with no template-substituted variables.
- Markdown rendered by a vetted library (e.g., `marked` with `breaks: true, sanitize: true`) — verify the sanitizer is on.
- `innerText` / `textContent` writes (safe).

## Severity

CRITICAL — full DOM XSS in admin panels can chain into session theft, privilege use, and CSRF.
