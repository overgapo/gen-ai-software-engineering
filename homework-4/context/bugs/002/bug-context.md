# Bug 002 — date-range filter drops the upper-bound day

- **Type:** Logic / boundary defect
- **Severity:** Medium (off-by-one on an inclusive range; data quietly missing)
- **Location:** [`src/expenses.js`](../../../src/expenses.js) — `filterExpenses()`, the `query.to` branch

## Symptom

The `?to=` filter uses a strict less-than comparison:

```js
result = result.filter((e) => Date.parse(e.date) < to);
```

A date range is expected to be inclusive on both ends, so an expense dated exactly on
`to` is incorrectly excluded.

## Reproduction

Seed data includes a coffee expense (`id: 3`) dated `2026-01-31`.

```
GET /expenses?from=2026-01-01&to=2026-01-31   ->  returns ids [1, 2]   (id 3 missing)
```

## Expected behavior

Both bounds are inclusive. The upper-bound comparison must be `<=`:

```js
result = result.filter((e) => Date.parse(e.date) <= to);
```

so the query above returns ids `[1, 2, 3]`.

## Notes for the pipeline

Watch the boundary specifically — a test that only checks a mid-range date will pass even
with the bug present. The regression test must include a record dated exactly on `to`.
