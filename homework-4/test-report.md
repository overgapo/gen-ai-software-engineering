# Test Report — Expense Tracker API

**Agent:** Unit Test Generator (required agent, Task 4) · **Model:** `claude-sonnet-5` ·
**Date:** 2026-07-23 · **Scope:** `fix-summary.md` + `src/**` · **Write scope:** `tests/**`
(new test file only — `src/**` was not modified).

## Summary

`fix-summary.md` reports **Status: BLOCKED** with **"Changes Made: None"** — the upstream
research quality gate failed (Level C), so the Bug Fixer applied no edits and `src/**` is
unmodified in this run. There is therefore no *applied* fix to write regression tests
against.

Rather than return an empty artifact, this run wrote the acceptance tests that the three
seeded defects (`context/bugs/001|002|003`) require — the tests that must fail on the
current, unfixed code and pass once the Bug Fixer actually applies the plan. They were then
run against the **current baseline** of `src/**`, which is exactly the state the next Fixer
run will start from. This mirrors how the Security Verifier handled the same blocked
upstream state for `security-report.md`.

**`npm test` result: 1 suite, 7 tests — 4 passed, 3 failed.** The 3 failures are *expected*
and *diagnostic*: each one is the test for a seeded defect that is still present, confirming
the bug is real and unfixed. They are not test bugs — they will flip to green the moment the
corresponding `src/expenses.js` change from `implementation-plan.md` is applied, with no
change to the test file itself.

| Metric | Count |
|---|---|
| Test suites | 1 (`tests/expenses.test.js`) |
| Tests total | 7 |
| Passed | 4 |
| Failed | 3 (all expected — defect still open) |

## Test → defect mapping

| Test | Defect | Result now | Expected after fix |
|---|---|---|---|
| `filtered summary equals the aggregate of the matching filtered list, and differs from the unfiltered total` | **001** — `/summary` ignores filters (`src/expenses.js:56`) | ❌ FAIL (`count` 3 not 2, `total` 60.75 not 20.75) | ✅ PASS once `/summary` aggregates over `filterExpenses(store.all(), req.query)` |
| `unfiltered summary aggregates every record` | 001 (control case) | ✅ PASS | ✅ PASS (unaffected by the fix) |
| `a record dated exactly on the \`to\` bound is included in the range` | **002** — exclusive upper bound (`src/expenses.js:29`) | ❌ FAIL (id `3` dropped) | ✅ PASS once the comparison is `<=` |
| `a record one day after the \`to\` bound is still excluded` | 002 (control case — proves the fix doesn't over-include) | ✅ PASS | ✅ PASS (unaffected by the fix) |
| `the key configured via process.env.API_KEY authorizes deletion` | **003** — hardcoded secret, not read from env (`src/expenses.js:12`) | ❌ FAIL (401 instead of 204 — code still compares against the hardcoded literal, not `process.env.API_KEY`) | ✅ PASS once the key is read from `process.env.API_KEY` and compared with `crypto.timingSafeEqual` |
| `a wrong key is rejected with 401 and the record is not removed` | 003 (control case) | ✅ PASS | ✅ PASS (unaffected by the fix) |
| `a missing key header is rejected with 401` | 003 (control case) | ✅ PASS | ✅ PASS (unaffected by the fix) |

## FIRST compliance

- **Fast** — every test drives `supertest(createApp())` in-process; `app.listen()` is never
  called and no real port is bound. Full suite runs in ~0.35s.
- **Independent** — `beforeEach` calls `store.reset(FIXTURE)` with the same fixed 3-record
  fixture for every test, so a prior test's `DELETE` (which mutates the in-memory store)
  never leaks into the next. No module-level mutable state is shared across tests; the
  security `describe` block also snapshots and restores `process.env.API_KEY` in
  `beforeEach`/`afterEach` so it never leaks into other suites.
- **Repeatable** — no wall-clock, timezone, locale, or randomness dependence. All dates and
  amounts are fixed literals in `FIXTURE`; the API key used is a fixed test string set
  explicitly via `process.env.API_KEY`, never the environment's ambient value.
- **Self-validating** — every test asserts concrete values (`toBe(204)`, `toBe(20.75)`,
  `toEqual([1, 2, 3])`, etc.). No test relies on a human reading console output.
- **Timely** — each test targets exactly the line(s) `implementation-plan.md` and
  `research/verified-research.md` identify as the fix site for defects 001/002/003, and is
  written to fail now / pass after, per the skill's core rule. No unrelated code (e.g. the
  `validation.js` `hasAtMostTwoDecimals` discrepancy that blocked the research gate) is
  covered — that issue is outside `fix-summary.md`'s three seeded defects and outside this
  agent's scope.

## Boundary discipline

- **Defect 002** is covered by *two* dates, not one: the exact `to` boundary (`2026-01-31`,
  must be included) and one day before it (`2026-01-30`, must still be excluded) — so the fix
  can't be satisfied by simply widening the range indiscriminately.
- **Defect 001** asserts equality with the filtered aggregate *and* inequality with the
  unfiltered total in the same test, so a fix that filters `count`/`byCategory` but leaves
  `total` unfiltered (or vice versa) would still be caught.
- **Defect 003** asserts all three authorization outcomes (correct key from env → 204, wrong
  key → 401, missing key → 401) and never places a valid secret in the test file — the
  positive case reads the key back from `process.env.API_KEY`, matching the skill's
  requirement that "no valid key value is hardcoded in the test."

## Constraints observed

- **`src/**` was not modified.** `git status --short src/` is empty for this run.
- Only one new file was added: `tests/expenses.test.js`.
- Tests cover only the three defects named in `fix-summary.md` / `implementation-plan.md`;
  no unrelated behavior (e.g. validation edge cases, 404 handling beyond what's needed for a
  control case) was tested.

## Finding for the next pipeline run

Because the Bug Fixer made no changes, this suite is currently **red on 3/7 tests by
design**. That is the correct baseline signal, not a defect in the tests: once
`research/codebase-research.md`'s claim C36 is corrected, `research/verified-research.md` is
re-run to **Gate: PASS**, and the Bug Planner/Bug Fixer produce and apply the real
before/after change for defects 001–003, re-running `npm test` with **no edits to
`tests/expenses.test.js`** should turn all 7 tests green. If any of the three still fail
after the fix lands, that is a signal the applied change didn't match
`research/verified-research.md`'s fix direction and should be investigated before merging.

## References

- `fix-summary.md:1-69` — confirms zero code changes this run (BLOCKED status)
- `research/verified-research.md` — independently verified fix directions for defects
  001/002/003, cited by line in `fix-summary.md`
- `context/bugs/001/bug-context.md`, `context/bugs/002/bug-context.md`,
  `context/bugs/003/bug-context.md` — seeded defect contracts the tests encode
- `src/expenses.js:12,29,56,73-83` — unfixed lines each test targets
- `src/app.js`, `src/store.js` — `createApp()` / `store.reset()` test seams used throughout
- `skills/unit-tests-FIRST.md` — FIRST definition and boundary-discipline checklist applied
  above
- `tests/expenses.test.js:1-107` — the test file this report describes
- Command run: `npx jest --colors=false` — full output captured; 4 passed / 3 failed as
  tabulated above
