# Implementation Plan — Expense Tracker (`src/`)

Derived from `research/verified-research.md`.

## Gate check

- **Verification Summary gate: PASS** (Quality Level A — Verified, `verified_ratio` 36/36,
  zero Discrepancies).
- Proceeding to plan all four verified defects directly from
  `research/codebase-research.md` / `research/verified-research.md`. No claim requires
  re-research.

---

## Change 1 — `GET /summary` ignores query filters

- **Target:** `src/expenses.js`, `router.get('/summary', ...)` handler (lines 50-63).
- **Which defect:** `context/bugs/001` (logic defect).

**Before:**

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

**After:**

```js
router.get('/summary', (req, res) => {
  // Reuse the shared filter so the summary always describes the same set GET /expenses
  // returns for the same query.
  const rows = filterExpenses(store.all(), req.query);
  const total = rows.reduce((sum, e) => sum + e.amount, 0);
  const byCategory = {};
  for (const e of rows) {
    byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
  }
  return res.json({ count: rows.length, total, byCategory });
});
```

- **Why:** Routing through the existing `filterExpenses(list, query)` helper (already used
  correctly by `GET /expenses` at line 46) makes `/summary` agree with `/expenses` for the
  same query, per the expected behavior in `context/bugs/001/bug-context.md`.

---

## Change 2 — date-range filter drops the upper-bound day

- **Target:** `src/expenses.js`, `filterExpenses()`, the `query.to` branch (lines 25-30).
- **Which defect:** `context/bugs/002` (logic / boundary defect).

**Before:**

```js
  if (query.to) {
    const to = Date.parse(query.to);
    // SEEDED BUG (context/bugs/002): the upper bound is exclusive, so an expense dated
    // exactly `to` is dropped from the range. It should be inclusive (`<=`).
    result = result.filter((e) => Date.parse(e.date) < to);
  }
```

**After:**

```js
  if (query.to) {
    const to = Date.parse(query.to);
    result = result.filter((e) => Date.parse(e.date) <= to);
  }
```

- **Why:** The date range must be inclusive on both ends (the `from` branch already uses
  `>=`); switching `<` to `<=` makes `?from=2026-01-01&to=2026-01-31` return `[1, 2, 3]`
  instead of dropping boundary id 3, per `context/bugs/002/bug-context.md`.

---

## Change 3 — hardcoded API secret + insecure comparison

- **Target:** `src/expenses.js`, the `API_KEY` constant (lines 7-12) and the
  `DELETE /expenses/:id` handler (lines 73-83).
- **Which defect:** `context/bugs/003` (security vulnerability — both halves required).

### 3a. Imports

**Before:**

```js
const express = require('express');
const store = require('./store');
const { validateExpense } = require('./validation');
```

**After:**

```js
const crypto = require('crypto');
const express = require('express');
const store = require('./store');
const { validateExpense } = require('./validation');
```

### 3b. Secret source

**Before:**

```js
// API key guarding destructive operations.
//
// SEEDED SECURITY ISSUE (context/bugs/003): the secret is hardcoded in source (so it
// leaks to anyone with repo access and cannot be rotated without a redeploy), and the
// check below compares it with loose `==`, which is neither type-safe nor constant-time.
const API_KEY = 'sk_live_9f8c2b1a7e4d';
```

**After:**

```js
// API key guarding destructive operations. Read from the environment — never hardcode a
// secret in source. If unset, the DELETE route fails closed (see the handler below).
const API_KEY = process.env.API_KEY;
```

### 3c. Comparison

**Before:**

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

**After:**

```js
router.delete('/expenses/:id', (req, res) => {
  const provided = req.header('x-api-key');

  if (!API_KEY || typeof provided !== 'string') {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const providedBuf = Buffer.from(provided);
  const expectedBuf = Buffer.from(API_KEY);
  const authorized =
    providedBuf.length === expectedBuf.length &&
    crypto.timingSafeEqual(providedBuf, expectedBuf);

  if (!authorized) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const removed = store.remove(Number(req.params.id));
  if (!removed) {
    return res.status(404).json({ error: 'Expense not found' });
  }
  return res.status(204).send();
});
```

- **Why:** Moves the secret out of source into `process.env.API_KEY` (fail closed when
  unset) and replaces the loose, non-constant-time `==` with a length check followed by
  `crypto.timingSafeEqual`, so a mismatched length never reaches `timingSafeEqual` (which
  throws on unequal-length buffers per the verified research, claim 27). Both halves of
  the remediation are required — a half-fix leaves the finding open per
  `context/bugs/003/bug-context.md`.

---

## Change 4 — floating-point amount validation rejects valid two-decimal amounts

- **Target:** `src/validation.js`, `hasAtMostTwoDecimals()` (lines 27-29).
- **Which defect:** `context/bugs/004` (logic defect, floating point — found by the
  pipeline, not seeded).

**Before:**

```js
function hasAtMostTwoDecimals(n) {
  return Math.round(n * 100) === n * 100;
}
```

**After:**

```js
function hasAtMostTwoDecimals(n) {
  return Math.abs(Math.round(n * 100) - n * 100) < 1e-9;
}
```

- **Why:** Comparing the rounded and raw values with a tolerance instead of strict
  equality tolerates IEEE-754 rounding error (`19.99 * 100 === 1998.9999999999998`) while
  still rejecting genuinely over-precise amounts like `1.005`, per the expected behavior in
  `context/bugs/004/bug-context.md`.

---

## Test command

```
npm test
```

This is how the Bug Fixer verifies all four changes (existing tests plus any new
regression tests, including the Unit Test Generator's later additions).

## Manual verification

Assumes the server is running (`PORT` defaults to `3000`) and seed data from
`src/index.js` is loaded (ids 1-3: `food 12.50` on `2026-01-05`, `transport 40.00` on
`2026-01-10`, `food 8.25` on `2026-01-31`).

**Change 1 — `/summary` respects filters:**

```
curl -s 'http://localhost:3000/expenses?category=food'
curl -s 'http://localhost:3000/summary?category=food'
# expect summary: {"count":2,"total":20.75,"byCategory":{"food":20.75}}
```

**Change 2 — inclusive upper date bound:**

```
curl -s 'http://localhost:3000/expenses?from=2026-01-01&to=2026-01-31'
# expect ids [1, 2, 3] (id 3, dated exactly 2026-01-31, now included)
```

**Change 3 — secret from env + constant-time compare:**

```
API_KEY=sk_live_9f8c2b1a7e4d node src/index.js &

curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://localhost:3000/expenses/2 \
  -H 'x-api-key: sk_live_9f8c2b1a7e4d'
# expect 204

curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://localhost:3000/expenses/1 \
  -H 'x-api-key: nope'
# expect 401

curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://localhost:3000/expenses/1
# no header at all (API_KEY unset case): expect 401, and confirm the literal
# 'sk_live_9f8c2b1a7e4d' no longer appears anywhere in src/expenses.js
```

**Change 4 — two-decimal amounts accepted:**

```
curl -s -X POST http://localhost:3000/expenses \
  -H 'Content-Type: application/json' \
  -d '{"amount":8.29,"category":"food","date":"2026-02-01"}'
# expect 201, not 400

curl -s -X POST http://localhost:3000/expenses \
  -H 'Content-Type: application/json' \
  -d '{"amount":1.005,"category":"food","date":"2026-02-01"}'
# expect 400 (still rejected: over-precise)
```
