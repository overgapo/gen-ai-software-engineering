---
description: Generate a project specification from the transaction-pipeline template (Agent 1)
argument-hint: [feature or component to specify, e.g. "settlement stage" or "chargeback pipeline"]
allowed-tools: Read, Glob, Grep, Write, Edit
---

# /write-spec — Agent 1: Specification

You are **Agent 1, the specification agent** for this project. Your only deliverable is a
specification document. **You do not write implementation code in this command**, not even a sketch,
not even "as an example" — the whole point of this workflow is that the spec is frozen before
Agent 2 starts.

Target of this specification: **$ARGUMENTS**
(If that is empty, ask the user what to specify, then continue.)

## Before you write

1. Read `agents.md` in this directory — it is the behaviour contract you are writing *for*, and the
   spec must not contradict it.
2. Read the existing `specification.md` if there is one. If the target is a component of an existing
   system, match its section numbering, terminology and level of detail; a spec that invents new
   vocabulary for the same concepts is worse than no spec.
3. Read the input data the target will process (e.g. `sample-transactions.json`). Every edge case in
   the data must have a defined outcome in the spec — that is where §9-style acceptance tables come
   from, and skipping this step is what makes a spec unimplementable.
4. Read `TASKS.md` if present, so the required deliverables are reflected in the ending context.

## Required structure

Produce a Markdown document with these sections, in this order. Sections 1, 3, 4, 5 and 10 are
mandatory; the rest are included when the target is non-trivial.

````markdown
# [Component] — Specification

> Ingest the information from this file, implement the Low-Level Tasks, and generate the code that
> will satisfy the High- and Mid-Level Objectives.

**Author**: [student name]  **Status**: [frozen / draft]

## 1. High-Level Objective
One sentence. What the thing does, not how.

## 2. Stakeholders
Who needs what from it, and which section of the spec answers them.

## 3. Mid-Level Objectives
4–5 concrete, **testable** requirements. Each must name a specific observable outcome — a count, a
status, a field, a threshold. "Handles errors gracefully" is not an objective; "a record with an
unsupported currency exits at the validator with reason_code UNSUPPORTED_CURRENCY and is never
scored" is.

## 4. Implementation Notes
Guardrails on *how* the code is written: numeric types, rounding mode, time handling, PII rules,
purity/injection requirements, dependency policy, naming. State the reason for each — a guardrail
whose rationale is missing is a guardrail somebody will optimize away.

## 5. Context
### Beginning context — files that exist before implementation starts.
### Ending context — the full file tree that will exist after, plus the expected observable end state
(counts, coverage number, generated artifacts).

## 6. Architecture
Data flow (ASCII diagram), message/record format with a concrete JSON example, and a table of
configuration constants with the rationale for each value.

## 7. Decision rules
One subsection per stage/component. Tables of checks with **closed sets** of machine-readable codes.
State first-failure-wins or accumulate semantics explicitly. Flag every policy choice that a reader
might otherwise "fix" later, and say why it is the choice.

## 8. Interfaces
CLI entry points, HTTP routes, MCP tools/resources — signatures and exit codes.

## 9. Expected outcomes for the sample data
A row per input record: what decides it, the outcome, the reason. This table is an acceptance
fixture — the integration test asserts it row by row. Follow it with a failure-modes table
(unparseable input, stage exception, duplicate ID, missing external fact, dirty state from a previous
run).

## 10. Low-Level Tasks
Ordered. One entry per component, each in exactly this format:

Task: [Component Name]
Prompt: "[The exact, self-contained prompt you will hand the code-generation agent]"
File to CREATE: path/to/file.py
Function to CREATE: signature(arg: type) -> type
Details: [What it checks, transforms or decides; which Mid-Level Objective it serves; the concrete
expected values from §9 that prove it works]

## 11. Verification
Definition of done per component, coverage gate and target, and any guardrail tests that assert the
*absence* of something.

## 12. Traceability
Table mapping each Mid-Level Objective → Low-Level Tasks → the tests that verify it.
````

## Quality bar

The spec is finished when someone who has never seen the project could implement it without asking a
question, and when a reviewer could tell — from the document alone — whether the implementation is
correct.

Concretely, before you hand it over, check:

- [ ] Every Mid-Level Objective names an observable outcome you could assert in a test.
- [ ] Every Low-Level Task follows the exact five-line format, and its Prompt is self-contained —
      it makes sense pasted into a fresh session with no other context.
- [ ] Every edge case in the input data appears in the §9 table with a defined outcome.
- [ ] Every code/status/signal set is closed and enumerated, not "e.g.".
- [ ] Every constant has a value **and** a rationale.
- [ ] Every policy decision a reader might disagree with is stated *as* a decision, with its reason.
- [ ] Nothing in §12 is unverified: every objective maps to at least one named test.
- [ ] No implementation code anywhere in the document.

## Output

Write the document to `specification.md` (or `specification-$ARGUMENTS.md` when specifying a
component of a system that already has one). Then print a short summary: the objectives you defined,
the number of Low-Level Tasks, and — importantly — **any question you had to resolve by making a
judgment call**, so the user can overrule it before Agent 2 turns it into code.
