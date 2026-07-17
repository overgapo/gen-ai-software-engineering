# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`homework-3` is one assignment in a university course ("GenAI and Agentic AI for Software Engineering"). The parent repo (`../`) is a homework template with one directory per assignment (`homework-1` … `homework-6`); each is self-contained.

**This assignment produces documents, not software.** There is no package manager, no build, no test suite, and no run command — nothing to install and nothing to execute. The two files currently present are inputs, not work product:

- `TASKS.md` — the assignment brief (the binding requirements; read it first)
- `specification-TEMPLATE-example.md` — a set of example spec skeletons (basic / banking / API / testing) plus prompt-engineering patterns

Sibling assignments (`../homework-1`, `../homework-2`) *are* implemented Node.js/Express projects with their own `CLAUDE.md`. Do not carry their commands or conventions into here.

## The one rule that is easy to violate

`TASKS.md` explicitly puts **code, APIs, and UI out of scope**. The graded artifact is the specification's *quality* — decomposition, traceability from goals down to tasks, and anticipation of failure modes. If a request here sounds like "build it," the right output is still a document. Scaffolding a project, writing source files, or adding a `package.json` would work against the grade, so confirm before creating anything executable.

## Deliverables to produce in `homework-3/`

1. **`specification.md`** — a layered spec for a self-chosen finance feature (the brief's running example is virtual-card lifecycle: create, freeze/unfreeze, set limits, view transactions). Layers, in order: high-level objective → mid-level objectives (observable/testable) → non-functional & policy → implementation notes → beginning/ending context → low-level tasks. Three cross-cutting concerns must be woven **into the spec itself**, not deferred to the README: an edge-case/failure-mode table with expected behavior, verification criteria per mid-level objective, and *measurable* performance targets (label hypothetical numbers as assumed targets and justify them). The template is a floor to exceed — the brief asks for many small low-level tasks with acceptance criteria, each tied back to the mid-level objective it serves, not three generic bullets.
2. **`agents.md`** — how an AI coding partner must behave in this domain: stack assumptions, banking domain rules, testing/verification expectations, security and compliance constraints, edge-case defaults (e.g. never log PAN, prefer idempotent writes).
3. **Editor/AI rules** — one of `.github/copilot-instructions.md`, a `.claude/` file, or `.cursor/rules/*.md`. None exist yet anywhere in the repo, so pick one form and create it.
4. **`README.md`** — must contain a student/task summary, the **rationale** (why the spec is shaped this way, how performance targets and verification depth were chosen), and **industry best practices** with file/section references pointing at where each practice actually appears in the spec.

The domain must read as regulated-environment-ready: auditability, security, clear boundaries around sensitive data. Stakeholders include at minimum end-users and an internal ops/compliance view.

## Record decisions here as they are made

The brief is deliberately open ("you choose scope and depth"), so the scoping choices are the author's to make — but once made they are binding, and a spec that quietly re-decides its own premises is exactly the failure this assignment grades against. Sibling assignments handle this with a numbered "resolved contract" section in their `CLAUDE.md`; do the same here.

### Resolved contract

1. **Feature: cashback / rewards on card spend.** Chosen over the brief's virtual-card example because accruals can be *reversed long after the fact* (refund or chargeback lands weeks after payout), which forces clawback, negative balances, and reconciliation into the spec — a richer failure-mode and verification surface than a state machine alone.
2. **Accrual timing: two-stage.** A `pending` accrual is shown on authorization; the accrual is only *confirmed* on clearing/settlement. Consequences that the spec must handle: cleared amount differing from the authorized amount, partial clearings, expired authorizations that never clear.
3. **Payout: automatic, monthly, to the account balance.** A background batch pays out confirmed cashback at period close, after a holding window that protects against clawback. No on-demand redemption in scope. This makes throughput (not p95 latency) the primary performance target for the payout path.
4. **Reward unit: real money** (minor units / kopiyky), credited to the account balance. No points, no exchange rate. Keeps monetary invariants (rounding, negative balance on clawback, accrued liability) literal.
5. **Stakeholders (six):** end-user, ops/compliance, finance/accounting (reconciliation + accrued liability), support (explain-a-decision + manual adjustment under maker-checker), fraud/risk (transaction cycling, buy-and-return abuse), marketing/program owner (rule authoring → rule versioning: which rule version scores a transaction that predates a rate change).

6. **Editor/AI rules form: `.cursor/rules/*.md`** — several topic-scoped files (money handling, ledger/audit, PII/PCI, testing) rather than one flat file, so the rules themselves demonstrate structure. This is the *one* form the brief asks for; do not also add a Copilot or `.claude/` rules file for the fictional project.
7. **No `HOWTORUN.md`.** Nothing in this assignment executes. The README carries a short "nothing to run — this is a documentation deliverable" note plus how to *read* the package, instead of a file that would have to invent a fake `npm start`.

Nothing in the resolved contract is open for quiet revision. If a later step wants to contradict one of these, say so out loud and get a decision.

## Repo-wide submission contract

From `../README.md` — these apply to every assignment and are grading gates:

- Work on a fork; one branch per assignment (`homework-3-submission`), PR targeting **your own fork's `main`**, never the upstream course repo. Reviewer: `Alexey-Popov`.
- The **PR body is the primary submission narrative** and must stand on its own: thorough summary, how AI was used, how to verify, plus 3–5 screenshots. Bare or one-line PRs are rejected outright, even when the branch content is complete.
- Screenshots (of AI interactions, since there's no running app here) belong in `docs/screenshots/`.
- `HOWTORUN.md` is listed as a repo-wide requirement, but nothing runs in this assignment — clarify with the user whether to ship one describing how to *read/use* the spec package, or to omit it.
