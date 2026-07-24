# Bug 004 — amount validation rejects valid two-decimal amounts (floating point)

- **Type:** Logic defect (floating-point comparison)
- **Severity:** High (the API refuses legitimate input — most real prices are unusable)
- **Location:** [`src/validation.js`](../../../src/validation.js) — `hasAtMostTwoDecimals()`
- **Discovered by:** the pipeline itself, not seeded by the author. The Research Verifier
  rejected the Bug Researcher's claim that `src/validation.js` was "correct as written",
  which failed the quality gate on the first run.

## Symptom

The two-decimal check compares a float against its own rounding:

```js
function hasAtMostTwoDecimals(n) {
  return Math.round(n * 100) === n * 100;
}
```

`n * 100` is not exact in IEEE-754, so the equality fails for most two-decimal values and a
valid amount is rejected with `400 Validation failed`.

## Reproduction

```
node -e "console.log(19.99 * 100)"   // 1998.9999999999998  -> rejected
node -e "console.log(0.07  * 100)"   // 7.000000000000001   -> rejected
node -e "console.log(8.29  * 100)"   // 828.9999999999999   -> rejected
node -e "console.log(4.35  * 100)"   // 434.99999999999994  -> rejected
```

Against the running API:

```
POST /expenses {"amount":8.29,"category":"food","date":"2026-02-01"}
  -> 400 {"error":"Validation failed",
          "details":[{"field":"amount","message":"amount must have at most 2 decimal places"}]}
```

It passes only for values that happen to be exactly representable (`8.25`, `12.5`, `35.35`),
which is why the seeded demo data hid the defect.

## Expected behavior

Any amount with at most two decimal places is accepted; only genuinely over-precise amounts
(e.g. `1.005`) are rejected.

```
8.29, 19.99, 0.07, 4.35, 1.10, 12.5, 8.25  -> accepted
1.005, 0.001                                -> rejected
```

Fix direction: don't compare floats for equality. Either compare against a tolerance
(`Math.abs(n * 100 - Math.round(n * 100)) < 1e-9`) or inspect the decimal string
(`(n.toString().split('.')[1] || '').length <= 2`).

## Notes for the pipeline

The regression test must use a value that is **not** exactly representable — `19.99` or
`8.29`. A test written with `8.25` or `12.5` passes even with the bug present, which is
exactly how it survived the initial seeding.
