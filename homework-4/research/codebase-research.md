# Codebase Research — Expense Tracker (`src/`)

Investigation of the seeded defects in `context/bugs/001|002|003/bug-context.md`, plus a
follow-on defect (`context/bugs/004`) noted as discovered by the pipeline rather than
seeded. Each section below was located directly in source — line numbers are verified
against the current state of the files, not copied from the bug-context hints.

App shape for reference: `src/index.js` seeds three expenses and starts the server;
`src/app.js` wires `express.json()` and mounts `router` from `src/expenses.js` at `/`;
`src/store.js` is a tiny in-memory array-backed store; `src/validation.js` validates
`POST /expenses` payloads.

---

## Defect 1 — `GET /summary` ignores query filters (maps to `context/bugs/001`)

**Location:** `src/expenses.js:50-63` (the `router.get('/summary', ...)` handler); the
defect itself is on `src/expenses.js:56-57`.

**Evidence** (verbatim):

```js
router.get('/summary', (req, res) => {
  // The summary should describe the SAME filtered set a client sees from GET /expenses,
  // so passing ?category=food here should total only food expenses.
  //
  // SEEDED BUG (context/bugs/001): the query filter is ignored — totals are always
  // computed over every stored expense, so the summary disagrees with the filtered list.
  const rows = store.all();
  const total = rows.reduce((sum, e) => sum + e.amount, 0);
  const byCategory = {};
  for (const e of rows) {
    byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
  }
  return res.json({ count: rows.length, total, byCategory });
});
```

The handler even carries an inline comment (`SEEDED BUG (context/bugs/001)`) confirming
this is the intended defect, not incidental.

**Root cause:** `rows` is assigned from `store.all()` directly (`src/expenses.js:56`),
bypassing the `filterExpenses(list, query)` helper defined at `src/expenses.js:15-33` and
already used by the sibling `GET /expenses` handler (`src/expenses.js:45-48`,
specifically `filterExpenses(store.all(), req.query)` at line 46). Because `count`,
`total`, and `byCategory` are all derived from the unfiltered `rows`, any `?category=`,
`?from=`, or `?to=` query string passed to `/summary` is silently ignored — the response
always reflects the entire store, so it disagrees with what `GET /expenses` returns for
the same query string.

**Fix direction:** Replace `const rows = store.all();` with
`const rows = filterExpenses(store.all(), req.query);` so `/summary` aggregates over the
same filtered set that `/expenses` lists. `filterExpenses` is already exported from this
module (`module.exports = { router, filterExpenses };` at `src/expenses.js:85`), and is
in scope inside the same file, so no new import is needed. This is a one-line change,
matching the bug-context's own assessment.

---

## Defect 2 — date-range filter drops the upper-bound day (maps to `context/bugs/002`)

**Location:** `src/expenses.js:25-30`, inside `filterExpenses()` — the `query.to` branch.

**Evidence** (verbatim):

```js
  if (query.to) {
    const to = Date.parse(query.to);
    // SEEDED BUG (context/bugs/002): the upper bound is exclusive, so an expense dated
    // exactly `to` is dropped from the range. It should be inclusive (`<=`).
    result = result.filter((e) => Date.parse(e.date) < to);
  }
```

Again the offending line carries an inline `SEEDED BUG` comment pointing at itself.

**Root cause:** `Date.parse(query.to)` produces a timestamp for **midnight** of the `to`
date. Comparing with strict `<` means any expense whose own `Date.parse(e.date)` equals
that same midnight timestamp (i.e., dated exactly on `to`) fails the check and is
excluded. A date-range filter with `from`/`to` query parameters is expected to be
inclusive on both ends (the `from` branch at `src/expenses.js:21-24` is already
correctly inclusive, using `>=`), so the asymmetry is the tell: `>=` on the lower bound,
`<` on the upper bound.

Corroborating evidence from the seed data: `src/index.js:10` seeds expense `id: 3`
(`Coffee`, `2026-01-31`) with a comment explicitly noting "the coffee expense is dated
2026-01-31 on purpose — it sits exactly on the upper bound of the demo date-range query
and exposes the seeded boundary bug." A request like
`GET /expenses?from=2026-01-01&to=2026-01-31` returns only ids `[1, 2]`, omitting `3`.

**Fix direction:** Change the comparison at `src/expenses.js:29` from
`Date.parse(e.date) < to` to `Date.parse(e.date) <= to`, matching the `>=` used for
`from`. Any regression test must use a record dated exactly on the `to` boundary (as the
seed data already does) — a mid-range-only test would pass whether or not the bug is
present.

---

## Defect 3 (security) — hardcoded API key + insecure comparison (maps to `context/bugs/003`)

**Location:** `src/expenses.js:12` (the constant) and `src/expenses.js:73-83` (the
`router.delete('/expenses/:id', ...)` handler, specifically line 75).

**Evidence** (verbatim):

```js
// API key guarding destructive operations.
//
// SEEDED SECURITY ISSUE (context/bugs/003): the secret is hardcoded in source (so it
// leaks to anyone with repo access and cannot be rotated without a redeploy), and the
// check below compares it with loose `==`, which is neither type-safe nor constant-time.
const API_KEY = 'sk_live_9f8c2b1a7e4d';
```

```js
router.delete('/expenses/:id', (req, res) => {
  const provided = req.header('x-api-key');
  if (provided == API_KEY) {
    const removed = store.remove(Number(req.params.id));
    if (!removed) {
      return res.status(404).json({ error: 'Expense not found' });
    }
    return res.status(204).send();
  }
  return res.status(401).json({ error: 'Unauthorized' });
});
```

**Root cause:** Two independent problems, both present:

1. **Hardcoded secret.** `API_KEY` is a literal string committed to source
   (`src/expenses.js:12`), so anyone with repository read access has the credential, and
   rotating it requires a code change plus redeploy rather than an environment/config
   change.
2. **Insecure comparison.** `provided == API_KEY` (`src/expenses.js:75`) uses loose `==`
   (JavaScript type coercion) and is not constant-time — comparison short-circuits on the
   first mismatched character/byte, which is a textbook timing side-channel that can help
   an attacker recover the key incrementally. There is also no length check before
   comparison.

**Fix direction:** Read the key from `process.env.API_KEY` instead of a literal (fail
closed — i.e., refuse all deletions — if the env var is unset, rather than falling back
to a default). Replace the `==` check with a constant-time comparison via
`crypto.timingSafeEqual`, guarding first for equal buffer length (since
`timingSafeEqual` throws on mismatched lengths rather than returning `false`). Both
parts of the remediation (env-based secret **and** constant-time comparison) are
required — fixing only one leaves the other finding open, per the bug-context notes.
No valid credential value should remain anywhere in committed code or tests after the
fix.

---

## Defect 4 — `hasAtMostTwoDecimals()` rejects valid two-decimal amounts (maps to `context/bugs/004`)

**Location:** `src/validation.js:27-29`.

**Evidence** (verbatim):

```js
function hasAtMostTwoDecimals(n) {
  return Math.round(n * 100) === n * 100;
}
```

Called from `validateExpense()` at `src/validation.js:12`:

```js
  } else if (!hasAtMostTwoDecimals(amount)) {
    errors.push({ field: 'amount', message: 'amount must have at most 2 decimal places' });
  }
```

**Root cause:** This is a floating-point comparison bug, not a validation-logic bug —
the intent (reject amounts with more than 2 decimal places) is correct, but the
implementation compares a float to its own rounding, and `n * 100` is frequently not
exactly representable in IEEE-754 double precision. For example:

```
19.99 * 100  === 1998.9999999999998   (Math.round → 1999, but n*100 !== 1999)
0.07  * 100  === 7.000000000000001
8.29  * 100  === 828.9999999999999
4.35  * 100  === 434.99999999999994
```

In each case `Math.round(n * 100)` and `n * 100` are not strictly equal, so
`hasAtMostTwoDecimals` returns `false` and the amount is rejected with
`400 Validation failed`, even though the value is a perfectly valid two-decimal amount.
The bug is masked by the seed data in `src/index.js` (`12.5`, `40.0`, `8.25`), all of
which happen to be exactly representable in binary floating point, which is why manual
smoke-testing with the seeded demo data would not surface it.

**Note on how this defect surfaced:** `context/bugs/004/bug-context.md` records that this
defect was **not** one of the three originally seeded bugs — it was found because a
prior research pass incorrectly asserted `src/validation.js` was "correct as written,"
which the Research Verifier rejected, failing the research-quality gate. Reading the
current source directly (rather than trusting that prior claim) confirms the bug is real
and still present in `src/validation.js:27-29` as of this investigation.

**Fix direction:** Do not compare floats for equality. Either use a small epsilon
tolerance (`Math.abs(n * 100 - Math.round(n * 100)) < 1e-9`) or inspect the decimal
string directly (`(n.toString().split('.')[1] || '').length <= 2`). Values like `8.29`,
`19.99`, `0.07`, `4.35`, `1.10`, `12.5`, `8.25` must be accepted; only genuinely
over-precise amounts (`1.005`, `0.001`) should be rejected. Any regression test must use
a non-exactly-representable value (e.g. `19.99` or `8.29`) — a test using `8.25` or
`12.5` would pass even with the bug present, which is exactly how this defect survived
initial seeding.

---

## Notes for the Planner

- `filterExpenses` (Defect 1's fix target) is defined once (`src/expenses.js:15-33`) and
  already shared correctly by `GET /expenses`; the fix for Defect 1 is to route
  `/summary` through the same function rather than duplicating filter logic.
- Defects 1 and 2 are both inside/adjacent to `filterExpenses`/`/summary` in the same
  file (`src/expenses.js`) — fixing Defect 2 (the `<=` change) affects both `GET
  /expenses` and, once Defect 1 is fixed, `GET /summary` as well, since both routes will
  then call the same helper. A single regression test asserting
  `summary(filter) == aggregate(list(filter))` for a boundary-inclusive range exercises
  both fixes together.
- Defect 3's fix touches only `src/expenses.js` (the `API_KEY` constant and the `DELETE`
  handler) and will need Node's built-in `crypto` module, not currently imported in that
  file.
- Defect 4's fix is isolated to `src/validation.js` and has no call-site impact beyond
  `validateExpense()` already calling `hasAtMostTwoDecimals()` — no signature changes
  needed.
- No existing test files were found under a `tests/` or `test/` directory at the time of
  this research; the Unit Test Generator will likely be creating test coverage from
  scratch for all four defects.

---

## References

- `src/expenses.js:12` — `const API_KEY = 'sk_live_9f8c2b1a7e4d';`
- `src/expenses.js:15-33` — `filterExpenses(list, query)` helper (category/from/to filter logic)
- `src/expenses.js:21-24` — `from` branch (correct, inclusive `>=`)
- `src/expenses.js:25-30` — `to` branch (Defect 2: exclusive `<`)
- `src/expenses.js:35-43` — `POST /expenses` handler (validation call site)
- `src/expenses.js:45-48` — `GET /expenses` handler (correct use of `filterExpenses`)
- `src/expenses.js:50-63` — `GET /summary` handler (Defect 1: unfiltered aggregation)
- `src/expenses.js:65-71` — `GET /expenses/:id` handler
- `src/expenses.js:73-83` — `DELETE /expenses/:id` handler (Defect 3: `==` comparison)
- `src/expenses.js:85` — module exports (`router`, `filterExpenses`)
- `src/validation.js:4-25` — `validateExpense(body)`
- `src/validation.js:12-14` — call site of `hasAtMostTwoDecimals`
- `src/validation.js:27-29` — `hasAtMostTwoDecimals(n)` (Defect 4)
- `src/store.js:1-35` — in-memory store (`reset`, `all`, `getById`, `add`, `remove`)
- `src/index.js:7-11` — seed data (three expenses; id 3 dated on the Defect 2 boundary)
- `src/app.js:1-13` — `createApp()` wiring (`express.json()`, router mount)
- `context/bugs/001/bug-context.md` — Defect 1 source description
- `context/bugs/002/bug-context.md` — Defect 2 source description
- `context/bugs/003/bug-context.md` — Defect 3 source description
- `context/bugs/004/bug-context.md` — Defect 4 source description
