# Verified Research — Expense Tracker (`src/`)

Independent verification of `research/codebase-research.md`, performed under
`skills/research-quality-measurement.md`.

## Verification Summary

- **Gate: PASS** — the Planner may proceed.
- **Quality Level: A — Verified**
- **`verified_ratio`: 36/36 (100%)** — 36 Verified, 0 Discrepant, 0 Unresolvable.
- **Takeaway:** every file:line citation resolves to the code the research says it does,
  every quoted snippet is byte-for-byte accurate, and all four root causes were confirmed
  by executing the code rather than by reading it alone — the plan can be written directly
  from this research without re-checking it.

Verifier model: `claude-opus-4-8`. Date: 2026-07-24.

Verification method: each cited file was re-opened and read in full (not sampled), and
every behavioral assertion was reproduced by running Node against the actual modules —
the floating-point examples, the boundary-filter result, and `crypto.timingSafeEqual`'s
mismatched-length behavior were all executed, not assumed.

## Verified Claims

| # | Claim | Location | Verdict | Note |
|---|-------|----------|---------|------|
| 1 | `index.js` seeds three expenses and starts the server | `src/index.js:7-11`, `:16-18` | Verified | Three records; `app.listen(PORT)` present |
| 2 | `app.js` wires `express.json()` and mounts `router` at `/` | `src/app.js:8-9` | Verified | Exact |
| 3 | `store.js` is a tiny in-memory array-backed store | `src/store.js:4`, `:13-15` | Verified | `let expenses = []`; `all()` returns it |
| 4 | `validation.js` validates `POST /expenses` payloads | `src/validation.js:4-25`; `src/expenses.js:36` | Verified | `validateExpense(req.body)` is the sole call site |
| 5 | Defect 1 lives in the `GET /summary` handler at `50-63` | `src/expenses.js:50-63` | Verified | Handler spans exactly 50–63 |
| 6 | The defect itself is at `56-57` | `src/expenses.js:56-57` | Verified | The causal line is `56`; `57` is the derived `reduce` |
| 7 | Quoted `/summary` handler snippet is verbatim | `src/expenses.js:50-63` | Verified | Byte-for-byte, including comments |
| 8 | Handler carries an inline `SEEDED BUG (context/bugs/001)` comment | `src/expenses.js:54-55` | Verified | Confirms intent, not incidental |
| 9 | `rows` is assigned from `store.all()` directly | `src/expenses.js:56` | Verified | Exact |
| 10 | `filterExpenses(list, query)` is defined at `15-33` | `src/expenses.js:15-33` | Verified | Exact |
| 11 | `GET /expenses` correctly calls `filterExpenses(store.all(), req.query)` | `src/expenses.js:45-48`, call at `:46` | Verified | Exact |
| 12 | `module.exports = { router, filterExpenses }` | `src/expenses.js:85` | Verified | Last line of file |
| 13 | Root cause: `/summary` ignores `req.query`, so it disagrees with `GET /expenses` | `src/expenses.js:46` vs `:56` | Verified | `count`/`total`/`byCategory` all derive from unfiltered `rows` |
| 14 | Fix is a one-line change routing `/summary` through `filterExpenses` | `src/expenses.js:56`, `:85` | Verified | Same-file scope; no new import needed |
| 15 | Defect 2 is the `query.to` branch at `25-30` | `src/expenses.js:25-30` | Verified | Exact |
| 16 | Quoted `to`-branch snippet is verbatim | `src/expenses.js:25-30` | Verified | Byte-for-byte |
| 17 | The offending comparison at `:29` uses strict `<` | `src/expenses.js:29` | Verified | `Date.parse(e.date) < to` |
| 18 | The `from` branch at `21-24` is already inclusive (`>=`) | `src/expenses.js:21-24` | Verified | The `>=`/`<` asymmetry is real |
| 19 | Root cause: `Date.parse(to)` is midnight, so a record dated exactly `to` fails `<` | `src/expenses.js:26`, `:29` | Verified | Reproduced by execution |
| 20 | Seed id 3 (`Coffee`, `2026-01-31`) sits on the boundary, with a comment saying so | `src/index.js:10`; comment at `:5-6` | Verified | Citation `:10` is exact for the record; the quoted comment text is verbatim from `:5-6` of the same block |
| 21 | `?from=2026-01-01&to=2026-01-31` returns only ids `[1, 2]` | `src/expenses.js:15-33` | Verified | **Executed** against `filterExpenses` — returned `[1, 2]`, id 3 dropped |
| 22 | Hardcoded `API_KEY = 'sk_live_9f8c2b1a7e4d'` | `src/expenses.js:12` | Verified | Literal committed to source |
| 23 | `DELETE /expenses/:id` at `73-83`; comparison at `:75` | `src/expenses.js:73-83`, `:75` | Verified | Exact |
| 24 | Both quoted security snippets are verbatim | `src/expenses.js:7-12`, `:73-83` | Verified | Byte-for-byte |
| 25 | The check uses loose `==` and has no length guard | `src/expenses.js:75` | Verified | `provided == API_KEY`, non-constant-time |
| 26 | `crypto` is not currently imported in `expenses.js` | `src/expenses.js:1-3` | Verified | Zero occurrences of `crypto` in the file |
| 27 | `crypto.timingSafeEqual` throws on mismatched lengths (so a length guard is needed) | Node built-in | Verified | **Executed**: throws `Input buffers must have the same byte length` |
| 28 | Defect 4 is `hasAtMostTwoDecimals()` at `27-29`, quoted verbatim | `src/validation.js:27-29` | Verified | Byte-for-byte |
| 29 | Called from `validateExpense()` at `:12`, snippet verbatim | `src/validation.js:12-14` | Verified | Exact |
| 30 | `19.99*100 = 1998.9999999999998`, `0.07*100 = 7.000000000000001`, `8.29*100 = 828.9999999999999`, `4.35*100 = 434.99999999999994` | `src/validation.js:28` | Verified | **Executed** — all four values reproduce exactly as written; each returns `false` |
| 31 | Seed amounts `12.5`, `40.0`, `8.25` are exactly representable, masking the bug | `src/index.js:8-10` | Verified | **Executed**: `12.5`, `8.25` return `true` — demo data cannot surface the defect |
| 32 | Bug 004 was found by the pipeline (verifier rejected a false "validation is correct" claim), not seeded | `context/bugs/004/bug-context.md:1-8` | Verified | "Discovered by: the pipeline itself, not seeded by the author" |
| 33 | Both proposed fixes accept `8.29/19.99/0.07/4.35/1.10/12.5/8.25` and reject `1.005/0.001` | `src/validation.js:27-29` | Verified | **Executed** both the epsilon and decimal-string variants — correct on all nine values |
| 34 | Defect 3's fix touches only `src/expenses.js` | `src/expenses.js:12`, `:73-83` | Verified | `API_KEY` has no other reference in the repo source |
| 35 | Defect 4's fix is isolated; `hasAtMostTwoDecimals` has one call site, no signature change | `src/validation.js:12`, `:27` | Verified | Sole call site confirmed by repo-wide search |
| 36 | No existing test files under `tests/`/`test/` | `tests/` | Verified | The `tests/` directory exists but is empty — the Test Generator starts from scratch |

## Discrepancies Found

**None.**

All 36 claims were checked individually against the current source and each one passed.
This is an earned empty section, not an assumed one: every citation was resolved by
re-opening the file, every quoted snippet was compared character-by-character, and the
four behavioral claims that could not be settled by reading alone (claims 21, 27, 30, 33)
were settled by executing the code.

Two citations carry harmless drift, both inside the skill's ≤2-line tolerance or
otherwise landing on the correct code, and neither changes what a Planner would do:

- **Claim 20** — the research cites `src/index.js:10` for the boundary-dated seed record.
  That line is exactly right; the comment it quotes actually lives at `src/index.js:5-6`,
  four lines above, and the research gave no separate line citation for it. The quoted
  comment text is verbatim.
- **Reference list** — `src/store.js:1-35` is cited for a file that ends at line 34
  (1-line overshoot). The described contents (`reset`, `all`, `getById`, `add`, `remove`)
  are accurate.

Neither rises to Cosmetic-discrepancy status under §3, since both citations resolve to
the right code; they are recorded here for completeness.

## Research Quality Assessment

**Level A — Verified.** `verified_ratio` = 36/36 (1.00) with zero Cosmetic, zero Material,
and zero Critical discrepancies, which is the exact criterion for A in §4 of the skill.
No straddle rule applies — the run does not touch the B threshold, since B requires at
least one Cosmetic discrepancy to be the limiting factor and there are none.

What earns the A specifically:

- **The claims that matter most are the ones best evidenced.** Under §3, a Material error
  on the actual buggy line or the security-sensitive comparison would be Critical and
  force a D. Those four lines — `expenses.js:56`, `expenses.js:29`, `expenses.js:75`, and
  `validation.js:28` — are each cited to the exact line and quoted verbatim. There is no
  ambiguity for the Planner to resolve.
- **Root causes are correct, not just locations.** A citation can resolve while the stated
  cause is wrong (a Material discrepancy). Here each cause survives an independent check:
  the `/summary` bypass of `filterExpenses`, the midnight-timestamp equality that `<`
  excludes, the dual hardcoded-secret/non-constant-time finding, and the IEEE-754
  round-trip failure are all accurate characterizations, not plausible-sounding guesses.
- **The falsifiable numeric claims hold exactly.** The research printed four specific
  float products; all four reproduce digit-for-digit. This is where a fabricated research
  document usually breaks, and it did not.
- **The research is honest about its own limits.** It flags that `8.25`/`12.5` would let a
  regression test pass with the bug still present, and that a mid-range-only test would not
  catch Defect 2. Both are true and I confirmed the first by execution. Research that names
  the tests that would falsely reassure is materially more useful than research that
  merely locates the bug.
- **The Defect 4 provenance claim checks out.** `context/bugs/004/bug-context.md` records
  it as pipeline-discovered rather than seeded, matching the research's account.

Nothing would raise this level — A is the ceiling. To *hold* it on a re-run, the research
must keep quoting exact float products rather than rounding them, keep citing the buggy
line itself rather than the enclosing handler, and continue re-reading `src/` instead of
carrying forward prior conclusions (the failure mode that produced Defect 4 in the first
place). Two small precision improvements, neither gate-affecting: cite the boundary
comment at `index.js:5-6` alongside the seed record at `:10`, and correct the
`store.js:1-35` range to `1-34`.

**Gate for the Planner: PASS.** Plan directly from `research/codebase-research.md`; no
claim requires re-research.

## References

Files opened and read in full during verification:

- `src/expenses.js:1-85` — all four route handlers, `filterExpenses`, `API_KEY`, exports
  - `:7-12` — hardcoded `API_KEY` and its `SEEDED SECURITY ISSUE` comment (claims 22, 24)
  - `:15-33` — `filterExpenses` (claims 10, 15–19)
  - `:21-24` — inclusive `from` branch, `>=` (claim 18)
  - `:25-30` — exclusive `to` branch, `<` (claims 15–17)
  - `:35-43` — `POST /expenses`, the `validateExpense` call site (claim 4)
  - `:45-48` — `GET /expenses`, correct `filterExpenses` use (claim 11)
  - `:50-63` — `GET /summary`, unfiltered aggregation (claims 5–9, 13)
  - `:65-71` — `GET /expenses/:id`
  - `:73-83` — `DELETE /expenses/:id`, loose `==` at `:75` (claims 23–25)
  - `:85` — module exports (claim 12)
- `src/validation.js:1-31` — `validateExpense` and `hasAtMostTwoDecimals`
  - `:12-14` — call site of `hasAtMostTwoDecimals` (claims 29, 35)
  - `:27-29` — the float-equality comparison (claims 28, 30, 33)
- `src/index.js:1-18` — seed data and listener
  - `:5-6` — boundary-intent comment (claim 20)
  - `:8-10` — the three seeded amounts and the boundary-dated record (claims 20, 31)
- `src/store.js:1-34` — in-memory store; `reset`, `all`, `getById`, `add`, `remove` (claim 3)
- `src/app.js:1-13` — `createApp()` wiring (claim 2)
- `context/bugs/004/bug-context.md:1-40` — Defect 4 provenance (claim 32)
- `research/codebase-research.md:1-255` — the document under verification
- `tests/` — confirmed present but empty (claim 36)

Commands executed to verify behavioral claims (reproducible):

- `node -e "…"` over `[19.99, 0.07, 8.29, 4.35, 1.10, 12.5, 8.25, 1.005, 0.001]` printing
  `n*100`, `Math.round(n*100)`, and the predicate result — claims 30, 31, 33.
- `node -e "…"` calling `filterExpenses(seed, {from:'2026-01-01', to:'2026-01-31'})` on the
  `index.js` seed data — returned `[1, 2]`, claim 21.
- `node -e "crypto.timingSafeEqual(Buffer.from('abc'), Buffer.from('abcd'))"` — throws
  `Input buffers must have the same byte length`, claim 27.
- Repo-wide search for `hasAtMostTwoDecimals`, `filterExpenses`, and `crypto` in `src/` —
  claims 26, 34, 35.
