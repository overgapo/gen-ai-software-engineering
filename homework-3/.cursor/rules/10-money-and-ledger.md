---
description: Monetary arithmetic, the ledger, idempotency, caps, and clawback. Apply when touching any money path.
globs:
  - "src/domain/**"
  - "src/ingest/**"
  - "src/payout/**"
  - "src/finance/**"
  - "migrations/**"
---

# Money and ledger rules

## Arithmetic

- **`bigint`, minor units (kopiyky), always.** A `number` in the money path is a defect, including in intermediate values and test fixtures.
- **Rates are integer basis points.** `round_half_up(eligible_minor × rate_bps, 10000)`.
- **Round once, per transaction.** Never round an aggregate. Persist the discarded remainder — reconciliation must be able to explain every kopiyka, and a rounding residue that was never recorded becomes an unexplainable delta three months later.
- Reject rates outside `0..500` bps at authoring time, not at scoring time.

## The ledger

Four entry types, and no others: `ACCRUAL` (+), `REVERSAL` (−), `PAYOUT` (−), `ADJUSTMENT` (±).

- **`INSERT` only.** No `UPDATE`, no `DELETE`. The database enforces this with a trigger and with revoked privileges; do not try to work around either.
- A mistake is corrected by **writing a compensating entry**, not by fixing the old one. The wrong number stays in the record forever, next to the correction. That is the point of an audit trail.
- Every entry carries a correlation ID and is written **in the same transaction as its audit record**. If the audit write fails, the money movement rolls back.

## Idempotency

Assume **every event arrives at least twice**, because the bus guarantees exactly that.

- Consumers dedupe on `event_id`; payouts on `(run_id, user_id)`; adjustments on a client key.
- The dedupe record and the effect are written in **one transaction**. Not two. A crash between them either double-pays or loses money, and you do not get to choose which.

## Caps

- Enforced with **one atomic conditional statement**:
  ```sql
  UPDATE cap_counter
     SET consumed_minor = consumed_minor + LEAST(:amt, cap_minor - consumed_minor)
   WHERE user_id = :u AND period = :p AND category = :c
  RETURNING consumed_minor, cap_minor;
  ```
- **Never `SELECT` then `UPDATE`.** Two concurrent transactions both read the old value, both pass the check, and both accrue. The bug is invisible in review and expensive in production.
- A cap may **truncate** an accrual rather than block it. Report the granted amount *and* the remaining headroom, so the user can be told which cap they hit and how much is left.

## Clawback

- A refund reverses **proportionally, at the original accrual's rate and rule version**. Never re-score against today's rules.
- A chargeback reverses **in full** and raises a fraud signal.
- If the cashback was already paid out, the shortfall becomes a **negative carry balance**, recovered from future accruals at 100 %.
- **Never debit the user's main account.** There is no code path from this service to `ledger-service`'s debit endpoint, and there must not be one. A test asserts the module does not even import it.

## Rule versions

- Immutable once active. A rate change creates a **new version**; it does not edit the old one and does not re-score history.
- A transaction is scored against the version active at its **`authorized_at`**, not at processing time. A purchase made on 28 February under the old rate keeps the old rate even if it clears in March.
