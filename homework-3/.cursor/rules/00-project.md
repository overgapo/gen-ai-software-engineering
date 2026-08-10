---
description: Project context and the rules that override every other instinct. Always apply.
alwaysApply: true
---

# Cashback Rewards Engine — project rules

You are working on a **cashback rewards engine** for a regulated financial institution. It scores card transactions, accrues rewards, reverses them when purchases are refunded or charged back, and pays them out monthly.

The authoritative documents, in precedence order:

1. [`specification.md`](../../specification.md) — objectives, policies, edge cases, tasks. **Source of truth.**
2. [`agents.md`](../../agents.md) — how an AI partner must behave here.
3. These rules — the short form, for when you are mid-edit and not re-reading the spec.

## The four rules that override everything

1. **Never invent policy about money.** If the spec does not say how to round, whether to debit, what rate to apply, or how long to keep something — **stop and ask**. A blocked task is visible. A wrong rate is not.
2. **Money is `bigint` in minor units.** No floats. Not in calculations, not in JSON, not in fixtures.
3. **The ledger is append-only.** Corrections are new compensating entries, never edits.
4. **Zero is a decision with a reason code.** Never award nothing silently.

## What this service does not do

It does not issue cards, authorize or clear transactions, handle points/miles, do FX, or produce tax reporting. It also never debits the user's main account — over-payment is recovered via the negative carry balance.

If a request implies one of these, you have been asked to work outside the scope boundary in §1 of the spec. Say so.

## Traceability

Every change traces to a task in §9 of the spec, and every task names the mid-level objective it serves. A PR that cannot name its objective is a PR without a reason to exist — put the task ID (`T13`) and the objective (`M4`) in the description.
