# `agents.md` — How an AI coding partner must behave in this repository

This file governs any AI agent (Cursor, Claude Code, Copilot, an autonomous coding agent) working on the **Cashback Rewards Engine** described in [`specification.md`](./specification.md).

It is not style advice. This is a system that moves customer money inside a regulated institution. Most of the rules below exist because breaking them produces a **monetary or compliance defect** that looks, in a diff, exactly like ordinary working code.

---

## 1. The prime directive

**`specification.md` is the source of truth. You do not have authority to invent policy about money.**

When the spec is silent on a monetary, privacy, or audit question — how to round, whether to debit, what to do with an unmatched event, how long to retain something — **stop and ask**. Do not choose a reasonable-looking default. In this domain a plausible guess is worse than a blocked task, because a blocked task is visible and a wrong rate is not.

When the spec and an existing pattern in the codebase disagree, the spec wins and the pattern is a bug worth reporting.

---

## 2. Stack assumptions

- **TypeScript** (Node 20), `strict: true`, no `any` in the money path — ever.
- **PostgreSQL 15** is the system of record. The event bus is Kafka-shaped with **at-least-once** delivery.
- **Fastify** for internal HTTP surfaces (ops, support, finance). There is no public customer-facing API in this service.
- **Vitest** for unit/property tests, **Testcontainers** for integration tests against a real PostgreSQL — never against a mock, because half of the guarantees in this system (append-only triggers, unique constraints, exclusion constraints, atomic conditional updates) live *in the database* and a mock will happily let you violate them.

---

## 3. Banking domain rules (non-negotiable)

These restate §5.3, §5.4 and §6 of the spec. If you are about to write code that contradicts one of these, you have misunderstood the task.

1. **Money is `bigint` in minor units (kopiyky).** Never `number`, never a float, never a decimal string that gets parsed into a float somewhere downstream. This applies to intermediate values, JSON payloads, and test fixtures.
2. **Rates are integer basis points.** `accrual = round_half_up(eligible_minor × rate_bps, 10000)`, rounded **once per transaction**, never on an aggregate. The discarded remainder is persisted, not dropped.
3. **The ledger is append-only.** A correction is a new compensating entry. If you find yourself writing `UPDATE reward_ledger_entry`, stop — the database will reject it, and it should.
4. **Cap counters are updated with a single atomic conditional statement.** Never `SELECT` a counter and then `UPDATE` it. Two concurrent transactions will both read the old value and both pass the check, and the bug will be invisible until it is a headline.
5. **Reversals are scored at the original accrual's rate and rule version.** Never re-score against the currently active rules. A refund of a purchase made under a 5 % promo reverses 5 %, forever, no matter what today's rate is.
6. **Never debit the user's main account** to recover cashback. Over-payment is recovered via the negative carry balance (§5.4). If you write a call to `ledger-service`'s debit endpoint from this service, you have written a defect.
7. **Never assign a default rate.** If the rule service is unavailable, park the event and retry. A lagging accrual is an inconvenience; a guessed rate is a monetary error that will be found by reconciliation weeks later, after payout.
8. **Zero is a decision, not an absence.** Every evaluation that awards nothing emits a machine-readable reason code from the closed set in §6. A branch that returns `0` with no reason must fail the build.
9. **Period attribution follows the authorization timestamp in `Europe/Kyiv`**, not processing time and not UTC. The user's mental model is "the day I bought it".

---

## 4. Security and compliance constraints

**PAN, CVV and track data must never enter this system.** It handles `card_token` and `last4` only.

- If an inbound payload contains a PAN, that is a **producer defect**: drop the field, raise an alert, do not persist, do not log, do not include it in an error message, do not put it in a test fixture.
- There is no configuration flag, debug mode, or "temporary" branch that enables PAN logging. Do not add one. Do not add one "just for local development".
- Never log a full inbound card event payload. Log the `event_id`, `transaction_id`, and correlation ID — the identifiers, not the contents.
- Merchant name and MCC are personal data by association. They may not be shipped to analytics without aggregation.

**Audit before money.** Every money movement writes an audit record — actor, action, reason, correlation ID — **in the same database transaction**. If the audit write fails, the money movement rolls back. Never the other way round.

**Segregation of duties is code, not procedure.** Manual adjustments and rule activations require two distinct principals. Do not add an "admin override" that bypasses maker-checker, however convenient it would be for testing — write a test fixture with two principals instead.

**Erasure does not delete financial records.** A GDPR erasure request pseudonymizes identity and retains ledger rows for 7 years under a legal-obligation basis (§5.6). If asked to "implement account deletion", implement pseudonymization and say why.

---

## 5. Testing and verification expectations

A task is not done when the code compiles. It is done when its **acceptance criteria in §9 of the spec** are demonstrably met.

**Every money-path change requires:**

- **A property test** where arithmetic is involved (rounding, proportional reversal, cap truncation). Example-based tests confirm what you already believed; property tests find the case you did not consider.
- **An integration test against a real PostgreSQL** where a database constraint is part of the guarantee (append-only, uniqueness, exclusion, atomic conditional update). Mocking these away tests your mock.
- **A concurrency test** where shared state is involved. Cap counters and payout idempotency are not correct until proven correct under parallel load. "It works when I click it twice" is not a concurrency test.
- **A crash test** where a multi-step process moves money. Kill the payout batch mid-run and assert nobody was paid twice and nobody was skipped.

**Some tests assert the absence of code.** T15's acceptance criterion fails if the clawback module so much as *imports* a debit client. This is deliberate: a guarantee that depends on nobody ever calling a function is stronger when the function is not reachable. Do not "fix" such a test by relaxing it.

**The false positive is the failure that matters** in fraud detection. A test suite where every abuse fixture is held and no legitimate user is checked is a suite that will happily ship a rule that freezes half the customer base.

**Never weaken a test to make it pass.** If a test fails, either the code is wrong or the spec is wrong. Both are worth saying out loud. Neither is fixed by loosening an assertion.

---

## 6. How to treat edge cases

The spec's §7 table is a **contract**, not a list of nice-to-haves. When you implement a task, check the table for rows anchored to its objective and make sure your code answers them.

Default postures when you hit something the table does not cover:

| Situation | Default posture |
|---|---|
| Ambiguous monetary behavior | **Stop and ask.** Do not pick a default. |
| A write that could be retried | **Make it idempotent**, keyed on a stable identifier. Assume every event will arrive twice, because it will. |
| An unknown or malformed inbound event | **Dead-letter and alert.** Never silently drop — a stuck event is unpaid money, which is a compliance concern, not just an ops one. |
| A dependency is unavailable | **Park and retry.** Never substitute a default value for a fact you do not have. |
| A calculation produces zero | **Emit it with a reason.** Zero is explainable; silence is not. |
| Data the user could dispute | **Persist the trace** (rule version, rate, caps, remainder) so support can reconstruct the arithmetic by hand. |

---

## 7. Code conventions

- Domain logic is **pure**: `score()` takes a transaction, a rule version and cap state, and returns an amount and a reason. No I/O, no clock, no randomness. This is what makes it replayable and what lets a fixture file be reviewed by someone who does not read TypeScript.
- **Reason codes are a closed set.** Adding one is a change to the spec, not a change to an enum. Say so in the PR.
- Names use domain language, not implementation language: `negativeCarryMinor`, not `debt`; `confirmedMinor`, not `available`. Support and compliance read these names in the explain-a-decision output.
- Thresholds that will be tuned (fraud sensitivity, payout minimum) are **configuration**. Thresholds that are policy (rate ceiling, retention period) are **code with a test**.
- Comments explain *why a rule exists*, not what the line does. `// authorization time, not processing time — the user's mental model is the purchase date` earns its place. `// add amounts` does not.

---

## 8. When you are asked to do something this file forbids

Say so, name the rule, and propose the compliant alternative. "The spec forbids debiting the main account (§5.4); the equivalent outcome is a negative carry balance, which I can implement instead" is the expected response.

Do not comply quietly. Do not comply with a `// TODO: revisit before production` comment. In this domain, that comment is how the defect ships.
