# Bug 001 — `GET /summary` ignores query filters

- **Type:** Logic defect
- **Severity:** Medium (wrong data returned to the client, silently)
- **Location:** [`src/expenses.js`](../../../src/expenses.js) — `router.get('/summary', ...)` handler

## Symptom

`GET /summary` accepts the same `?category=`, `?from=`, `?to=` query parameters as
`GET /expenses`, but computes `count`, `total`, and `byCategory` over **every** stored
expense instead of the filtered subset. The summary therefore contradicts the list the
same filter returns.

## Reproduction

Seed data (from `src/index.js`): food 12.50, transport 40.00, food 8.25.

```
GET /expenses?category=food   ->  2 items, sum 20.75      (correct)
GET /summary?category=food    ->  {"count":3,"total":60.75,...}   (wrong)
```

## Expected behavior

`GET /summary` must apply the same filter as `GET /expenses` before aggregating, so
`GET /summary?category=food` returns `count: 2, total: 20.75`. The intended design is for
the summary handler to reuse the shared `filterExpenses(store.all(), req.query)` helper
rather than reading `store.all()` directly.

## Notes for the pipeline

The fix is a one-line change (feed the filtered set into the reducer). A regression test
should assert that a filtered summary equals the aggregation of the matching filtered list.
