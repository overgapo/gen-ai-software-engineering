# Codebase Research — Expense Tracker Seeded Defects

Investigated `src/**` against the three seeded-defect descriptions in
`context/bugs/001|002|003/bug-context.md`. All line numbers below were verified against
the current contents of `src/expenses.js` (86 lines total) at research time; no other
`src/` file contains a seeded defect.

---

## Defect 1 — `GET /summary` ignores query filters

**Maps to:** `context/bugs/001/bug-context.md`

**Location:** `src/expenses.js:56` (handler body spans lines 50–63)

**Evidence** (verbatim, `src/expenses.js:50-63`):

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

The critical line is **`src/expenses.js:56`**: `const rows = store.all();` — it reads the
entire store instead of applying `req.query`.

**Root cause:** `GET /expenses` (line 46) builds its result via
`filterExpenses(store.all(), req.query)`, but the `/summary` handler was written to read
`store.all()` directly (line 56) instead of reusing that same helper. The helper
`filterExpenses` is already defined at the top of this file (lines 15–33) and exported
(line 85), so it is available to this handler — it's simply not called here. As a result
`count`, `total`, and `byCategory` are always computed over all stored expenses regardless
of `?category=`, `?from=`, `?to=` on the request.

**Fix direction:** Replace line 56 with
`const rows = filterExpenses(store.all(), req.query);` so the aggregation runs over the
same filtered subset that `GET /expenses` returns. No other lines in the handler need to
change — `total`, `byCategory`, and `count` all already derive from `rows`.

---

## Defect 2 — date-range filter drops the upper-bound day

**Maps to:** `context/bugs/002/bug-context.md`

**Location:** `src/expenses.js:29` (inside `filterExpenses`, lines 15–33)

**Evidence** (verbatim, `src/expenses.js:25-30`):

```js
  if (query.to) {
    const to = Date.parse(query.to);
    // SEEDED BUG (context/bugs/002): the upper bound is exclusive, so an expense dated
    // exactly `to` is dropped from the range. It should be inclusive (`<=`).
    result = result.filter((e) => Date.parse(e.date) < to);
  }
```

**Root cause:** The `query.to` branch filters with a strict `<` comparison
(`Date.parse(e.date) < to`, line 29). Because `Date.parse` on a bare `YYYY-MM-DD` string
resolves to midnight UTC of that day, an expense dated exactly on `to` has
`Date.parse(e.date) === to`, which fails `< to` and is excluded. The matching `query.from`
branch three lines above (line 23) correctly uses `>=`, confirming the intent was an
inclusive range on both ends and this is a one-sided off-by-one.

Confirmed against seed data in `src/index.js:10`: the coffee expense (`id: 3`,
`date: '2026-01-31'`) is the deliberate boundary case — a query of
`?from=2026-01-01&to=2026-01-31` currently returns only ids `[1, 2]`, dropping id 3.

**Fix direction:** Change line 29 from `Date.parse(e.date) < to` to
`Date.parse(e.date) <= to`, mirroring the `>=` used for `from` at line 23.

**Downstream note:** This helper (`filterExpenses`) is shared by `GET /expenses` (line 46)
and, once Defect 1 is fixed, by `GET /summary` too — fixing line 29 automatically corrects
the boundary behavior for both endpoints, so the Planner does not need a second edit site.

---

## Defect 3 (Security) — hardcoded API secret + insecure comparison

**Maps to:** `context/bugs/003/bug-context.md`

**Location:** `src/expenses.js:12` (secret) and `src/expenses.js:75` (comparison, inside
the `DELETE /expenses/:id` handler, lines 73–83)

**Evidence** (verbatim, `src/expenses.js:7-12`):

```js
// API key guarding destructive operations.
//
// SEEDED SECURITY ISSUE (context/bugs/003): the secret is hardcoded in source (so it
// leaks to anyone with repo access and cannot be rotated without a redeploy), and the
// check below compares it with loose `==`, which is neither type-safe nor constant-time.
const API_KEY = 'sk_live_9f8c2b1a7e4d';
```

**Evidence** (verbatim, `src/expenses.js:73-83`):

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

**Root cause:** Two independent, compounding problems:

1. **Hardcoded credential (`src/expenses.js:12`).** The literal secret string
   `'sk_live_9f8c2b1a7e4d'` is committed to source control. Anyone with read access to the
   repository (or its git history, even after a later "fix") has the live key; rotating it
   requires a code change and redeploy rather than a config change.
2. **Insecure comparison (`src/expenses.js:75`).** `provided == API_KEY` is a loose
   (`==`, not `===`) string comparison evaluated character-by-character by the JS engine in
   a way that is not constant-time — comparison can short-circuit on the first mismatched
   byte, which in principle leaks timing information an attacker could use to recover the
   key incrementally. It's also loose-typed (though `req.header()` always returns a string
   or `undefined`, so the type-juggling risk here is smaller than the hardcoding risk).

There is no other reference to `API_KEY` in the file — it's declared once (line 12) and
read once (line 75).

**Fix direction:**
- Replace line 12 with a read from `process.env.API_KEY` (no literal default value), and
  fail closed (reject all deletions, e.g. respond 401/500) if the env var is unset at
  startup or request time.
- Replace line 75's `==` comparison with a length check followed by
  `crypto.timingSafeEqual` on two equal-length buffers (`Buffer.from(provided)` vs.
  `Buffer.from(API_KEY)`), guarding first against length mismatch since
  `timingSafeEqual` throws on unequal-length buffers.
- `crypto` is a Node.js builtin — no new dependency needed, just `require('crypto')` at
  the top of `src/expenses.js`.
- No valid key value should remain in source or tests after the fix (per bug-context notes).

---

## Notes for the Planner

- All three defects are isolated to a single file, `src/expenses.js`. `src/app.js`,
  `src/store.js`, `src/validation.js`, and `src/index.js` were inspected and contain no
  seeded defects — `validation.js`'s amount/date checks (lines 8–22) are correct as written
  and do not need changes.
- Fixing Defect 2 (line 29) benefits both `GET /expenses` and `GET /summary` once Defect 1
  is also fixed to call `filterExpenses`, since both routes converge on the same helper.
- Defect 1's fix depends only on `filterExpenses` already being defined and exported in the
  same file (lines 15–33, exported at line 85) — no new imports required.
- Defect 3's fix requires adding `const crypto = require('crypto');` (or
  `require('node:crypto')`) near the top of `src/expenses.js`, alongside removing the
  hardcoded literal on line 12.
- `src/index.js:10` seeds the `id: 3` / `2026-01-31` record specifically to exercise the
  Defect 2 boundary in demos/tests — the Unit Test Generator should reuse or mirror this
  boundary case rather than only testing a mid-range date.

## References

- `src/app.js:1-13` — Express app factory; no defects.
- `src/index.js:1-18` — demo seed data and server bootstrap; confirms Defect 2 boundary
  fixture (`id: 3`, `date: '2026-01-31'`, line 10).
- `src/store.js:1-35` — in-memory store; no defects.
- `src/validation.js:1-32` — expense payload validation; no defects.
- `src/expenses.js:1-13` — imports, router setup, `API_KEY` constant (Defect 3, line 12).
- `src/expenses.js:15-33` — `filterExpenses()`; Defect 2 at line 29; correct `from` handling
  at line 23 used as the reference pattern for the fix.
- `src/expenses.js:35-48` — `POST /expenses` and `GET /expenses`; no defects; line 46 shows
  the correct `filterExpenses(store.all(), req.query)` usage that `/summary` should mirror.
- `src/expenses.js:50-63` — `GET /summary`; Defect 1 at line 56.
- `src/expenses.js:65-71` — `GET /expenses/:id`; no defects.
- `src/expenses.js:73-83` — `DELETE /expenses/:id`; Defect 3 comparison at line 75.
- `src/expenses.js:85` — module exports (`router`, `filterExpenses`).
- `context/bugs/001/bug-context.md`, `context/bugs/002/bug-context.md`,
  `context/bugs/003/bug-context.md` — seeded defect descriptions consulted for this report.
