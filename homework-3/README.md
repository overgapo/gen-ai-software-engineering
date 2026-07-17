# Homework 3 — Specification-Driven Design

> **Student Name**: Andrii Shukailo ([@overgapo](https://github.com/overgapo))

## Task summary

Homework 3 asks for a **specification package** for a finance-oriented application — no implementation. The graded artifact is the specification itself: how clearly the problem is decomposed, how traceable requirements are from goals down to tasks, and how well failure modes, verification and non-functional expectations are anticipated.

**Chosen feature: a cashback rewards engine.** It scores cleared card transactions against a versioned rule set, accrues rewards, reverses them when a purchase is refunded or charged back, and pays them out monthly — inside a regulated environment, with a full audit trail.

### Nothing to run

This assignment produces documents. There is no `HOWTORUN.md`, no build, and no test command, because there is nothing to install and nothing to execute — inventing an `npm start` for a system that does not exist would be a lie in a submission that is otherwise about precision. **Read the package in this order:**

| # | File | What it is |
|---|---|---|
| 1 | [`specification.md`](./specification.md) | The deliverable. Layered spec: objective → mid-level objectives → non-functional & policy → implementation notes → context → 28 low-level tasks → traceability matrix. |
| 2 | [`agents.md`](./agents.md) | How an AI coding partner must behave in this domain. |
| 3 | [`.cursor/rules/`](./.cursor/rules/) | Editor/AI rules: [project](./.cursor/rules/00-project.md), [money & ledger](./.cursor/rules/10-money-and-ledger.md), [sensitive data](./.cursor/rules/20-sensitive-data.md), [testing](./.cursor/rules/30-testing.md). |

To *use* the package as intended: feed `specification.md` and `agents.md` to a coding agent, ask it to implement a single low-level task (T9, the atomic cap enforcement, is the sharpest one), and check the result against that task's acceptance criteria. The spec is written to make that check mechanical rather than a matter of taste.

---

## Rationale

### Why cashback, and not the virtual card from the brief

The brief's running example is virtual-card lifecycle. I chose cashback deliberately, because it contains a failure mode the card example does not: **a reward can be invalidated long after it was granted.** A purchase refunded six weeks after the cashback was paid out leaves the user holding money they did not earn — and now the system must recover it without debiting a customer's account, without breaking the ledger, and without becoming a regulatory complaint.

That single fact forces almost everything interesting in the spec into existence: the two-stage accrual (§4 M2), the append-only ledger (§6), the negative carry balance (§5.4), the nightly reconciliation (§4 M9). A feature whose hardest edge case is "the user pressed freeze twice" cannot generate that much structure honestly.

### Why the spec is shaped this way

**Verification lives next to the objective, not in a chapter at the end.** Each of the nine mid-level objectives (§4) carries its own verification paragraph, and each of the 28 low-level tasks (§9) ends in acceptance criteria. This is a deliberate rejection of the common shape where a spec has a "Testing" section that nobody reads: if the way you would *know* an objective is met is written three pages away from the objective, it will drift away from it, and the drift is invisible.

**Traceability is enforced in both directions.** Every task names the objective it serves; §10 is the matrix. The rule I held myself to: *every objective is served by at least two tasks, and every task can name its objective.* A task that cannot is a task with no reason to exist, and it was cut.

**The edge-case table (§7) states two outcomes per row, not one:** what the user sees, and what it means for audit/compliance. A spec that only says "show an error" has answered the product question and left the regulated question open — and in a bank, the second one is the one that gets asked in the review.

**Some acceptance criteria assert the absence of code.** T15 fails if the clawback module so much as *imports* a debit client. A guarantee that depends on nobody ever calling a function is weak; a guarantee where the function is unreachable is strong. This idea is repeated in `agents.md` §5 and in the testing rules, because an AI agent's natural instinct is to relax a test like that.

### How the performance targets were chosen

Numbers without a stated basis cannot be renegotiated, so §3 fixes an explicit **assumed baseline** — 2 M active cards, 40 M cleared transactions/month, ×6 seasonal peak, UAH only — and §5.1 derives every target from it, with the reasoning in the table itself. They are labelled **assumed targets**, as the brief requires.

The load-bearing decision is that **different paths get different *kinds* of target**, because cashback is an asynchronous engine and the frequent mistake is to import authorization's latency budget into it:

- The **read path** gets a latency budget (p95 ≤ 200 ms) — it is an ordinary in-app screen, competing with the balance screen, and past ~200 ms scrolling stops feeling instant.
- The **pending path** gets a *deliberately relaxed* budget (p95 ≤ 5 s). The user is at the till, looking at their phone; five seconds is "while I put my card away". Chasing sub-second here buys nothing, because the amount is provisional anyway.
- The **confirmed path** is promised in **hours, not seconds** (≤ 24 h at p99), because network clearing itself arrives T+1…T+3. Promising the user seconds would be promising something we do not control — and an SLO you cannot keep is worse than an honest one you can.
- The **payout batch** gets a **deadline, not an availability SLO** (2 M accounts in ≤ 4 h, must complete by day 5). Availability is the wrong frame for a monthly job: nobody cares if it was up, they care if they were paid.
- **Reconciliation** is timed to finish before finance starts work (≤ 30 min), so a break is actionable the same morning rather than the next one.

The specific pagination, rate-limit and read-after-write rules in §5.1 exist because the brief names them explicitly as examples of measurable expectations — and because a cursor of `(occurred_at DESC, id DESC)` is the difference between a history page that is correct under concurrent inserts and one that silently skips a row.

### How verification depth was chosen

Depth was allocated **where the cost of being wrong is monetary or irreversible**, not evenly:

- **Property tests** where arithmetic happens (rounding, proportional reversal, cap truncation) — example-based tests confirm what you already believed.
- **Integration tests against a real PostgreSQL** where the guarantee lives in the database (append-only triggers, unique and exclusion constraints, the atomic conditional update). Mocking those tests the mock.
- **A concurrency test** for cap enforcement (100 simultaneous transactions against 1 ₴ of headroom, §4 M3) — the read-then-write bug is invisible in code review and expensive in production.
- **A crash-and-resume test** for the payout run — the only honest proof of "nobody paid twice, nobody skipped".
- **A false-positive fixture** for fraud (§8.3), because a suite where every abuse case is caught and no legitimate customer is checked will happily ship a rule that freezes half the user base.

By contrast, the explain-a-decision endpoint gets one load test and a shape assertion — it is read-only, and being slow there costs a support agent thirty seconds, not a customer their money.

---

## Industry best practices, and where they appear

| Practice | Where it appears | What it prevents |
|---|---|---|
| **Money as integer minor units; no floats anywhere** | `specification.md` §5.3, §6 rule 1; T1 acceptance criteria; [`10-money-and-ledger.md`](./.cursor/rules/10-money-and-ledger.md); `agents.md` §3.1 | Silent precision loss that reconciliation finds months later |
| **Append-only, double-entry ledger; corrections as compensating entries** | §6 (entry types), T2, E22; `agents.md` §3.3 | History that can be quietly rewritten — i.e. no audit trail at all |
| **Effectively-once processing via idempotency keys** | §5.2, §6 ("Idempotency"), T3, T17, E1, E12 | Double payouts under at-least-once delivery |
| **Atomic conditional updates instead of read-then-write** | §4 M3, T9 acceptance criteria, E5; [`10-money-and-ledger.md`](./.cursor/rules/10-money-and-ledger.md) | Concurrent transactions both passing the same cap check |
| **Temporal rule versioning; never re-score history** | §4 M6, T4, T5, E6, E7, E27 | A rate change silently rewriting last month's rewards |
| **Maker-checker / segregation of duties enforced in code** | §5.5, §4 M7, T5, T22, E19, E20; [`20-sensitive-data.md`](./.cursor/rules/20-sensitive-data.md) | One person moving customer money alone |
| **PCI scope containment: never log or store PAN/CVV** | §5.5, §6 rule 5, T23, E21; [`20-sensitive-data.md`](./.cursor/rules/20-sensitive-data.md); `agents.md` §4 | Dragging a rewards service into PCI DSS scope through a log line |
| **Audit written in the same transaction as the money movement** | §5.6, T23 acceptance criteria; `agents.md` §4 | Money that moved with no record of why |
| **Reconciliation as a first-class product feature, with named offending rows** | §4 M9, T25, T26, E24 | Finance unable to close the books on an unexplained delta |
| **Explicit retention-vs-erasure conflict, resolved and documented** | §5.6, T24, E23; [`20-sensitive-data.md`](./.cursor/rules/20-sensitive-data.md) | "Implementing GDPR" by deleting financial records |
| **Fail loudly rather than guess** (no default rate, dead-letter + alert, no FX guess) | §5.2, §5.7, §6 rule 7, E15, E25; `agents.md` §6 | A plausible default becoming a monetary error at scale |
| **Zero is a decision with a reason code** | §4 M1, §6 (closed reason-code set), T7, E26 | Support unable to answer "why did I get nothing?" |
| **SLOs tied to what the user actually experiences** (deadline for a batch, not uptime) | §5.1, §5.2, T27 | Green dashboards next to unpaid customers |
| **Fixtures as reviewable data, not code** | §8.3, T28; [`30-testing.md`](./.cursor/rules/30-testing.md) | Reward rules that only engineers can verify |

---

## How AI was used

The specification was developed conversationally with Claude (Claude Code, Opus 4.8): brainstorming candidate finance features against the grading criteria, pressure-testing the scope boundary, drafting each layer, and hardening the edge-case table. The binding scoping decisions — cashback over virtual cards, two-stage accrual, monthly auto-payout, real money over points, six stakeholders, Cursor rules over Copilot — were made by me and recorded as a numbered *resolved contract* in [`CLAUDE.md`](./CLAUDE.md) precisely so that later AI-assisted edits could not quietly re-decide the premises. That file is itself part of the method: it is what stops an agent from drifting.

Screenshots of the AI interactions are in [`docs/screenshots/`](./docs/screenshots/).
