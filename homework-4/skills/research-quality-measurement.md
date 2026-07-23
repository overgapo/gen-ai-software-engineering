# Skill: Research Quality Measurement

**Purpose.** Give the Bug Research Verifier a single, repeatable rubric for judging how
trustworthy a `codebase-research.md` document is, and a fixed shape for the
`verified-research.md` it writes. "Quality" here means *verifiability* — does every claim
survive an independent check against the actual source — not how well-written the prose is.

Use this skill whenever you verify research. Do not invent your own scale.

---

## 1. What counts as a claim

A **claim** is any statement in the research that can be checked against the repository:

- a file:line reference (e.g. "`src/expenses.js:34`")
- a quoted code snippet attributed to a location
- an assertion about behavior ("the `to` filter uses `<`")
- an assertion about a root cause ("the summary ignores `req.query`")

Every claim is checked **independently** — open the cited file at the cited location and
confirm it says what the research says. Do not take the researcher's word for anything, and
do not rely on your own memory of the code; re-read the source each time.

## 2. How to verify one claim

For each claim assign exactly one verdict:

| Verdict | Meaning |
|---------|---------|
| **Verified** | The reference resolves and the source matches the claim exactly (allowing only whitespace/line-shift noise, see below). |
| **Discrepant** | The reference resolves but the source disagrees in a way that matters (wrong operator, wrong symbol, snippet not present, wrong root cause). |
| **Unresolvable** | The file or line does not exist, or the citation is too vague to check. |

**Line-shift tolerance:** a citation off by ≤2 lines that still points at the right code is
**Verified** (note the drift in the claim). A citation that lands on unrelated code is
**Discrepant**, however small the numeric gap.

## 3. Discrepancy classes

Classify every non-Verified claim so severity is comparable across runs:

- **Cosmetic** — line number drift >2 but correct code nearby; a paraphrased-but-accurate
  snippet. Does not change what a planner would do.
- **Material** — wrong file, wrong symbol, snippet that isn't in the source, or a stated
  root cause that is incorrect. A planner acting on it would make a wrong edit.
- **Critical** — a Material discrepancy on a claim the fix depends on (the actual buggy
  line, the security-sensitive comparison). Planning on it produces a broken or unsafe fix.

## 4. Quality levels (the scale)

Pick the **single** level that matches; when a run straddles two levels, choose the lower.
`verified_ratio` = Verified claims ÷ total claims.

| Level | Label | Criteria |
|-------|-------|----------|
| **A** | **Verified** | `verified_ratio` = 1.00 and zero discrepancies. Plan directly from it. |
| **B** | **Sound** | `verified_ratio` ≥ 0.90, only Cosmetic discrepancies, no Material/Critical. Plan with the noted cautions. |
| **C** | **Shaky** | `verified_ratio` ≥ 0.70, or ≥1 Material discrepancy but no Critical. Re-research the flagged claims before planning. |
| **D** | **Unreliable** | `verified_ratio` < 0.70, or ≥1 Critical discrepancy. Do not plan from this — return it to the Bug Researcher. |

The level drives a **pass/fail gate**: **A or B = PASS** (the Planner may proceed);
**C or D = FAIL** (research must be corrected first). State the gate explicitly.

## 5. Required output shape for `verified-research.md`

Write these five sections, in this order, with these exact headings:

1. **## Verification Summary** — PASS/FAIL gate, the Quality Level + Label, `verified_ratio`
   as `X/Y (NN%)`, and a one-line takeaway. State the model and date.
2. **## Verified Claims** — a table: Claim | Location | Verdict | Note. One row per claim.
3. **## Discrepancies Found** — every Discrepant/Unresolvable claim with its class
   (Cosmetic/Material/Critical), what the research said, what the source actually says, and
   the corrected reference. If none: write "None." explicitly — do not omit the section.
4. **## Research Quality Assessment** — the chosen Level + Label and the *reasoning* that
   ties the counts and discrepancy classes to the rubric above. Name what would raise it.
5. **## References** — every file:line you personally opened to verify, so the check is
   reproducible.

## 6. Rules of engagement

- **You verify, you do not fix.** Do not edit source and do not rewrite the research; report
  what you found. Correcting the research is the Researcher's job on a re-run.
- **An empty "Discrepancies Found" must be earned**, not assumed — it means you checked every
  claim and each passed, and that is itself a signal of quality worth stating.
- **Independence is the whole point.** If you find yourself agreeing with the research
  because it sounds right, you have not verified it. Open the file.
