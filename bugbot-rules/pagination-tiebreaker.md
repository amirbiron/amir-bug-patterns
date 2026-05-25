# pagination-tiebreaker

Detect `ORDER BY` clauses that lack a secondary tiebreaker, leading to non-deterministic row order on ties. In paginated queries (LIMIT/OFFSET or cursor), this causes rows to be duplicated or skipped between pages.

## Flag when ALL apply

1. A SQL or ORM query uses `ORDER BY` (or `.order_by()`) with **only one** expression (usually a timestamp like `created_at`, `updated_at`, or a score / rank field).
2. The query is followed by `LIMIT` / `OFFSET`, or used in cursor-based pagination, or used in a CAS query with "latest" semantics.
3. The ordering column is NOT a `UNIQUE` constraint (timestamps can tie, scores can tie).

## Fix

Add the primary key as a secondary expression:
```python
.order_by(Model.created_at.desc(), Model.id.desc())
```

For CAS queries with "latest" semantics, the selector and the verifier MUST use the same multi-expression tuple.

## False positives

- Queries without `LIMIT` / `OFFSET` (full result set, order on ties less critical).
- Aggregations (`GROUP BY` + `SUM`) — `ORDER BY` over an aggregate doesn't need PK tiebreaker.
- Single-row queries (`.first()`, `.scalar_one_or_none()`) where the ordering column is `UNIQUE`.

## Severity

MEDIUM — pagination shows duplicate rows on one page and missing on the next; users see "moving" lists.
