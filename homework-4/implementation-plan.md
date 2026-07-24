# Implementation Plan — Expense Tracker Seeded Defects

## Gate check (per `research/verified-research.md`)

**Result: FAIL — Quality Level C (Shaky).** `verified_ratio` = 31/32 (97%), with **1 Material
discrepancy** (C36) and 0 Critical discrepancies.

Per the Bug Planner's process, a FAIL gate at Level C or D means: **do not plan fixes from
this document.** This plan therefore contains a single step — correct the research — and
stops there. No before/after code changes are authorized in this run.

## Failing claim

- **C36** — `research/codebase-research.md`, "Notes for the Planner" (first bullet), and its
  restatement in the References section, asserts:

  > `validation.js`'s amount/date checks (lines 8–22) are correct as written and do not need
  > changes.

  This is **false**. `src/validation.js:27-29` (`hasAtMostTwoDecimals`) rejects valid
  two-decimal amounts (e.g. `8.29`, `0.07`) due to a floating-point round-trip error
  (`Math.round(n * 100) === n * 100` fails for these inputs). `verified-research.md` confirmed
  this by execution and classified it as a Material discrepancy — false where it counts,
  because it scopes downstream work (a Unit Test Generator relying on this claim could write a
  FIRST test asserting `amount: 8.29` → 201, which fails against unmodified code).

## Required correction before re-planning

`research/codebase-research.md` must replace the "correct as written" bullet (and its
References-section restatement) with:

> `validation.js` contains no **seeded** defect (no `context/bugs/` entry references it), but
> its two-decimal check (`hasAtMostTwoDecimals`, lines 27–29) has a pre-existing,
> **unseeded** floating-point flaw that rejects valid amounts such as `8.29` and `0.07`. This
> is out of scope for the three seeded defects in `context/bugs/001-003` and is not fixed in
> this run.

No other part of the research needs to change — `verified-research.md` confirms the three
seeded-defect fix directions (Defect 1 at `src/expenses.js:56`, Defect 2 at
`src/expenses.js:29`, Defect 3 at `src/expenses.js:12,75`) are each independently Verified and
will remain valid once this single sentence is corrected.

## Next step

Re-run the Bug Researcher (or hand-correct the one sentence above) to produce a corrected
`codebase-research.md`, then re-run the Research Verifier. Once `verified-research.md` reports
**Gate: PASS** (Level A or B), re-run the Bug Planner to produce the full before/after change
plan for Defects 1–3 and the security fix.

## Test command

Not applicable this run — no code changes are planned. Once the gate passes and a full plan is
produced, the Fixer will still run `npm test` to verify.

## Manual verification

Not applicable this run — no fixes are planned pending the research correction above.
