# like-wildcard-injection

**CRITICAL — SQL query manipulation / data exposure**

Detect `LIKE` clauses constructed from user-supplied input without escaping the `_` and `%` wildcard characters. User-supplied input can match more rows than intended (data leak) or all rows (`%`).

## Flag when ALL apply

1. A SQL `LIKE` clause (or `ILIKE`, `NOT LIKE`) where the pattern is built from a user-supplied value.
2. The user value is concatenated / interpolated directly:
   - `f"{user_prefix}%"` / `f"%{user_input}%"`
   - `:param || '%'` / `'%' || :param || '%'`
   - `.like(`f"...{value}..."`)` in SQLAlchemy
3. The input is not escaped (`_` → `\_`, `%` → `\%`, backslash → `\\`) and the query doesn't include `ESCAPE '\\'`.

## Fix patterns

- **SQLAlchemy:** use `column.startswith(value, autoescape=True)` / `.endswith(...)` / `.contains(...)` — these escape automatically.
- **Raw SQL:** escape and declare:
  ```python
  esc = value.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
  q = "SELECT ... WHERE col LIKE :p ESCAPE '\\\\'"
  conn.execute(q, {"p": f"{esc}%"})
  ```
- **Or use `=`** if a prefix search isn't actually required (often the answer).

## False positives

- Hardcoded patterns (no user input).
- Internal admin tools where only trusted operators provide input — still risky.

## Severity

CRITICAL — `prefix="%"` selects all rows; `prefix="user_id_"` matches `user_idXfoo` etc. — leaks data the user shouldn't see.
