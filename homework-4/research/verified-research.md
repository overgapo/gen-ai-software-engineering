# Verified Research — Expense Tracker Seeded Defects

Independent verification of `research/codebase-research.md` against `src/**`, performed per
`skills/research-quality-measurement.md`.

## Verification Summary

- **Gate: FAIL** — the Planner must **not** plan from this document until the one flagged
  claim is corrected. (Rubric: Level C ⇒ FAIL.)
- **Quality Level: C — Shaky**
- **`verified_ratio`: 31/32 (97%)**
- **Verifier model:** `claude-opus-4-8` · **Date:** 2026-07-23
- **Method:** every file:line citation reopened in source; every behavioral claim reproduced
  by executing the real app on an ephemeral port (see References).

**Takeaway:** the research is precise where it counts — all 3 seeded defects are located to
the exact line, every quoted snippet matches source byte-for-byte, and all three reproduction
behaviors were confirmed by execution — but it also asserts that `src/validation.js` is
"correct as written," and that assertion is demonstrably false, which under this rubric is a
Material discrepancy and forces the gate to FAIL despite the high ratio.

**Scope note for whoever acts on this gate:** the FAIL is driven by a single claim
(C36) that is *outside* the three seeded defects. The fix directions for Defects 1, 2 and 3
are each fully Verified and may be relied on once the research is corrected. The required
correction is narrow — one sentence in "Notes for the Planner" — not a full re-research.

## Verified Claims

| # | Claim | Location | Verdict | Note |
|---|-------|----------|---------|------|
| C1 | `src/expenses.js` is 86 lines total | `src/expenses.js` | Verified | File has 85 newline-terminated lines; "86" is the editor-style count of the position after the trailing newline. Within line-shift tolerance. |
| C2 | No other `src/` file contains a seeded defect | `context/bugs/001-003` | Verified | All three bug-context docs name `src/expenses.js`. |
| C3 | Defect 1 maps to `context/bugs/001` | `context/bugs/001/bug-context.md:1-5` | Verified | Title and location match. |
| C4 | Defect 1 at `src/expenses.js:56`; handler spans 50–63 | `src/expenses.js:50-63` | Verified | Handler opens at 50, closes at 63; line 56 is the cited line. |
| C5 | Verbatim snippet of lines 50–63 | `src/expenses.js:50-63` | Verified | Exact character match, comments included. |
| C6 | Critical line 56 is `const rows = store.all();` | `src/expenses.js:56` | Verified | Exact. |
| C7 | `GET /expenses` (line 46) uses `filterExpenses(store.all(), req.query)` | `src/expenses.js:45-46` | Verified | Exact. |
| C8 | `filterExpenses` defined at lines 15–33 | `src/expenses.js:15-33` | Verified | Opens at 15, returns at 32, closes at 33. |
| C9 | `filterExpenses` exported at line 85 | `src/expenses.js:85` | Verified | `module.exports = { router, filterExpenses };` |
| C10 | `/summary` ignores `?category=`/`?from=`/`?to=`; aggregates over all rows | `src/expenses.js:56-62` | Verified | **Executed:** `/summary?category=food` → `{count:3,total:60.75,byCategory:{food:20.75,transport:40}}` while `/expenses?category=food` → ids `[1,3]`. Identical to unfiltered `/summary`. |
| C11 | Replacing line 56 alone is sufficient; `count`/`total`/`byCategory` all derive from `rows` | `src/expenses.js:57-62` | Verified | All three consume `rows`; no other store access in the handler. |
| C12 | Defect 2 maps to `context/bugs/002` | `context/bugs/002/bug-context.md:1-5` | Verified | Matches, incl. expected `<=` fix. |
| C13 | Defect 2 at `src/expenses.js:29`, inside `filterExpenses` | `src/expenses.js:29` | Verified | Exact. |
| C14 | Verbatim snippet of lines 25–30 | `src/expenses.js:25-30` | Verified | Exact character match. |
| C15 | The `query.to` branch filters with strict `<` | `src/expenses.js:29` | Verified | `result = result.filter((e) => Date.parse(e.date) < to);` |
| C16 | Bare `YYYY-MM-DD` parses to midnight UTC, so a record dated exactly `to` fails `< to` | `src/expenses.js:26,29` | Verified | Date-only forms are UTC per ES spec; confirmed by the exclusion in C19. |
| C17 | The `from` branch "three lines above (line 23)" correctly uses `>=` | `src/expenses.js:23` | Verified | Line 23 is `>=` as cited. Prose "three lines above" is loose (it is 6 lines above line 29), but the explicit citation resolves correctly. |
| C18 | `src/index.js:10` seeds `id: 3`, `date: '2026-01-31'` | `src/index.js:10` | Verified | Exact. |
| C19 | `?from=2026-01-01&to=2026-01-31` returns only ids `[1,2]`, dropping id 3 | `src/expenses.js:29` | Verified | **Executed:** both `filterExpenses` directly and `GET /expenses` returned `[1,2]`. |
| C20 | Changing line 29 to `<=` fixes it | `src/expenses.js:29` | Verified | Matches `context/bugs/002:28-34` expected behavior. |
| C21 | Helper is shared by `/expenses` and (post-Defect-1) `/summary`; one edit site | `src/expenses.js:15,46` | Verified | `filterExpenses` has exactly one definition and one call site today. |
| C22 | Defect 3 maps to `context/bugs/003` | `context/bugs/003/bug-context.md:1-5` | Verified | Matches, incl. both sub-problems. |
| C23 | Secret at line 12; comparison at line 75; DELETE handler lines 73–83 | `src/expenses.js:12,73-83` | Verified | All three exact. |
| C24 | Verbatim snippet of lines 7–12 | `src/expenses.js:7-12` | Verified | Exact character match. |
| C25 | Verbatim snippet of lines 73–83 | `src/expenses.js:73-83` | Verified | Exact character match. |
| C26 | Literal `'sk_live_9f8c2b1a7e4d'` is committed to source | `src/expenses.js:12` | Verified | Exact. |
| C27 | `provided == API_KEY` is loose (`==`, not `===`) | `src/expenses.js:75` | Verified | Exact. |
| C28 | The comparison is not constant-time and can short-circuit on first mismatch | `src/expenses.js:75` | Verified | Standard characterization of JS string `==`; consistent with `context/bugs/003:22-23`. Research correctly hedges with "in principle". |
| C29 | `req.header()` returns string or `undefined`, so type-juggling risk is smaller than the hardcoding risk | `src/expenses.js:74-75` | Verified | **Executed:** omitting the header yields 401, not a bypass — `undefined == '...'` is `false`. |
| C30 | `API_KEY` is declared once (12) and read once (75); no other reference | `src/expenses.js:12,75` | Verified | Repo-wide search over `src/` returns exactly those 2 hits. |
| C31 | The hardcoded key authorizes deletion | `src/expenses.js:73-83` | Verified | **Executed:** correct key → 204; wrong key → 401; no key → 401. |
| C32 | Fix = env var + `crypto.timingSafeEqual` with a length guard (it throws on unequal lengths) | `src/expenses.js:12,75` | Verified | Matches `context/bugs/003:36-40`; length-guard requirement is accurate. |
| C33 | `crypto` is a Node builtin; no new dependency, just add a require | `src/expenses.js:1-3` | Verified | No `crypto` import exists anywhere in `src/` today. |
| C34 | All three defects are isolated to `src/expenses.js` | `src/**` | Verified | Confirmed against all five source files. |
| C35 | `app.js`, `store.js`, `validation.js`, `index.js` contain no *seeded* defects | `src/**`, `context/bugs/**` | Verified | No bug-context doc references them. |
| C36 | `validation.js`'s amount/date checks (lines 8–22) "are correct as written and do not need changes" | `src/validation.js:12,27-29` | **Discrepant** | **Material** — see Discrepancies Found. |
| C37 | `src/index.js:10` seeds the boundary record on purpose | `src/index.js:5-6,10` | Verified | The source comment states exactly this. |
| C38 | Reference ranges for `app.js:1-13`, `index.js:1-18`, `store.js:1-35`, `validation.js:1-32`, and the six `expenses.js` ranges | `src/**` | Verified | All ranges land on the described code. `store.js` (34 lines) and `validation.js` (31 lines) show the same +1 editor-style convention as C1; within tolerance. |

*(Rows C1–C37 are the substantive claims counted for the ratio; C38 consolidates the
References section's range citations as a single claim. Total = 32 claims, 31 Verified.)*

## Discrepancies Found

### C36 — "`validation.js`'s amount/date checks are correct as written" — **Material**

**Where:** `research/codebase-research.md`, "Notes for the Planner", first bullet.

**What the research said:**
> `validation.js`'s amount/date checks (lines 8–22) are correct as written and do not need changes.

(Restated in the References section as "`src/validation.js:1-32` — expense payload
validation; no defects.")

**What the source actually does:** the amount check at `src/validation.js:12` delegates to
`hasAtMostTwoDecimals` at `src/validation.js:27-29`:

```js
function hasAtMostTwoDecimals(n) {
  return Math.round(n * 100) === n * 100;
}
```

Multiplying a binary float by 100 does not round-trip exactly, so legitimate two-decimal
amounts are rejected. Verified by execution:

| Input | `n * 100` | Result |
|-------|-----------|--------|
| `8.29` | `828.9999999999999` | **rejected** — "amount must have at most 2 decimal places" |
| `0.07` | `7.000000000000001` | **rejected** — same |
| `8.25` | `825` | accepted (0.25 is binary-exact) |
| `12.5` | `1250` | accepted |

`POST /expenses` with `{ amount: 8.29, category: 'food', date: '2026-01-05' }` therefore
returns **400**, not 201. The validator is not "correct as written": it rejects valid input.

**Corrected reference:** `src/validation.js:27-29` (`hasAtMostTwoDecimals`), reached from
`src/validation.js:12`. The accurate statement is: *`validation.js` contains no **seeded**
defect (no `context/bugs/` entry references it), but its two-decimal check has a
floating-point flaw that rejects valid amounts such as `8.29` and `0.07`.*

**Why Material rather than Cosmetic.** This is not citation drift or a paraphrase — it is a
behavioral assertion that is false, and §1 of the skill counts behavioral assertions as
claims. It sits in the section that scopes downstream work, so it can misdirect a consumer:
the Unit Test Generator, told validation is correct, may write a FIRST test asserting
`amount: 8.29` → 201, which fails against unmodified code.

**Why not Critical.** No seeded fix depends on it. Defects 1–3 can be planned and fixed
correctly even with this claim present, so it does not produce a broken or unsafe fix.

**What a corrected re-run must say:** replace the "correct as written" bullet with the
accurate statement above, and state explicitly whether repairing `hasAtMostTwoDecimals` is
in or out of scope for this run (it is an unseeded, pre-existing defect). No other part of
the research needs to change.

## Research Quality Assessment

**Level C — Shaky. Gate: FAIL.**

**Counts:** 32 claims, 31 Verified, 1 Discrepant (1 Material, 0 Critical, 0 Cosmetic,
0 Unresolvable). `verified_ratio` = 31/32 = 0.97.

**Reasoning against the rubric.** The ratio alone (0.97) clears Level B's ≥ 0.90 threshold,
but Level B additionally requires "only Cosmetic discrepancies, no Material/Critical." C36 is
Material — the discrepancy classes are exhaustive, and it is neither Cosmetic (it is a false
behavioral assertion, not line drift or an accurate paraphrase) nor Critical (no seeded fix
depends on it). Level C's second criterion — "≥1 Material discrepancy but no Critical" —
matches exactly. The run straddles B (by ratio) and C (by class), and the rubric directs
choosing the lower level. Level C ⇒ **FAIL**: research must be corrected before planning.

**What the research did well** (and what should survive a re-run unchanged):
- Every fix-critical citation is exact: lines 56, 29, 12 and 75 all resolve precisely, with
  zero line drift across ten distinct ranges — unusual precision.
- All four quoted snippets match source byte-for-byte, comments included.
- All three reproduction behaviors independently reproduced by execution, not just read.
- The three fix directions are each correct, minimal, and consistent with their
  `bug-context.md` — including the non-obvious detail that `timingSafeEqual` throws on
  unequal-length buffers and needs a length guard first.
- The negative claims were checked, not assumed: `API_KEY` really does have exactly two
  references, and `crypto` really is absent from `src/`.

**What would raise the level:**
- **To B (Sound):** correct the C36 bullet as specified above. Nothing else is required —
  that single edit removes the only non-Verified claim.
- **To A (Verified):** the C36 correction, plus tightening two loose-prose spots that were
  passed under tolerance but are still inaccurate as written — the "three lines above" in
  Defect 2 (line 23 is 6 lines above line 29) and the consistent +1 file line counts (86/35/32
  for files of 85/34/31 lines).

## References

Every location below was opened and read during this verification.

**Source (ground truth):**
- `src/expenses.js:1-85` — read in full; specifically 7–12 (API_KEY), 15–33 (`filterExpenses`,
  `from` at 23, `to` at 29), 35–48 (`POST`/`GET /expenses`, call site at 46), 50–63
  (`GET /summary`, defect at 56), 65–71 (`GET /expenses/:id`), 73–83 (`DELETE`, comparison at
  75), 85 (exports).
- `src/validation.js:1-31` — 4–25 (`validateExpense`), 12 (decimal check call), 27–29
  (`hasAtMostTwoDecimals` — the C36 discrepancy).
- `src/index.js:1-18` — 5–6 (boundary-case comment), 7–11 (seed data, `id: 3` at line 10).
- `src/store.js:1-34` — 8–11 (`reset`), 13–15 (`all`), 27–32 (`remove`).
- `src/app.js:1-13` — 6–11 (`createApp`).

**Seeded-defect specifications:**
- `context/bugs/001/bug-context.md:1-33`
- `context/bugs/002/bug-context.md:1-39`
- `context/bugs/003/bug-context.md:1-47`

**Document under verification:**
- `research/codebase-research.md:1-188`

**Executed checks** (run against the real app on an ephemeral port; the repository was not
modified):
- `filterExpenses(store.all(), {from:'2026-01-01', to:'2026-01-31'})` → ids `[1,2]` (C19).
- `GET /expenses?from=2026-01-01&to=2026-01-31` → ids `[1,2]` (C19).
- `GET /summary?category=food` → `{count:3,total:60.75,byCategory:{food:20.75,transport:40}}`
  vs. `GET /expenses?category=food` → ids `[1,3]` (C10).
- `DELETE /expenses/2` with `x-api-key: sk_live_9f8c2b1a7e4d` → 204; wrong key → 401; header
  omitted → 401 (C29, C31).
- `validateExpense` probes at amounts `8.29`, `0.07`, `1.005`, `12.345`, `-5`, `12.5`, `100.1`
  (C36).
