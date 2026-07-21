# Cashback Rewards Engine — Specification

> Ingest the information in this file, implement the Low-Level Tasks, and produce a system that satisfies the High- and Mid-Level Objectives without violating any rule in **Implementation Notes** or **Non-Functional & Policy**.
>
> This document is the single source of truth. Where this document and a habit disagree, this document wins. Where this document is silent, stop and ask — do not invent policy about money.

---

## 1. High-Level Objective

**Build a cashback rewards engine that pays users a share of their card spend such that every kopiyka is traceable from the transaction that earned it to the payout that delivered it, every decision (earned / not earned / how much) is explainable to the user and to support, and any late reversal — a refund, a chargeback, or a mis-priced rule — can be corrected without breaking balance integrity or the audit trail.**

**Scope boundary (one sentence):** the engine consumes card authorization, clearing, refund and chargeback events and produces reward accruals, reversals and monthly payouts — it does not issue cards, does not authorize or clear transactions, does not implement merchant-funded offers, does not convert rewards into points/miles, and does not produce end-user tax reporting.

### 1.1 Why this shape

Cashback is deceptively simple to state and hard to make correct, because **a reward can be invalidated long after it was granted**. A purchase refunded six weeks after the cashback was paid out leaves the user holding money they did not earn. Every structural decision below — the two-stage accrual, the append-only ledger, the negative carry balance, the nightly reconciliation — exists to make that class of event survivable and auditable rather than surprising.

---

## 2. Stakeholders

| Stakeholder | What they need from this system | Where it lands in the spec |
|---|---|---|
| **End-user** | Predictable, visible, explainable rewards; no silent zeros | M1, M2, M3, T21 |
| **Ops / compliance** | Immutable audit trail; no unilateral money movement; defensible retention | M7, §5.5, §5.6, T22–T24 |
| **Finance / accounting** | Accrued liability they can close the books on; reconciliation that ties out | M9, T25, T26 |
| **Support** | Answer "why did I get 3.40 ₴ and not 5.00 ₴?" in under a minute | M7, T21 |
| **Fraud / risk** | Stop transaction cycling and buy-and-return abuse before payout, not after | M8, T19, T20 |
| **Marketing / program owner** | Change rates and categories without rewriting history | M6, T4, T5 |

---

## 3. Assumed Baseline (scale)

All numeric targets in §5 are derived from this baseline. **These figures are assumed, not measured** — they describe a mid-size neobank and are stated so the targets can be recomputed rather than re-guessed if reality differs.

| Assumption | Value | Consequence |
|---|---|---|
| Active cards | 2,000,000 | Payout batch size |
| Cleared transactions | 40,000,000 / month (≈ 15/s mean) | Ingest throughput floor |
| Peak multiplier (Black Friday) | ×6 | Ingest peak target |
| Currency | UAH only; amounts in **minor units (kopiyky)** | No FX in scope |
| Reward ledger rows retained | 7 years | Retention vs. erasure conflict (§5.6) |
| Rewards rate range | 0.5 % – 5 % (50–500 bps) by category | Rounding materiality |

---

## 4. Mid-Level Objectives

Each objective is phrased as an **observable change in the world**, and carries its own verification (how we know it is met). Low-level tasks in §9 are anchored back to these IDs — that anchor is the traceability contract of this spec.

### M1 — Earn: every cleared transaction is scored exactly once, deterministically, with a reason

A cleared card transaction is evaluated against exactly one rule version and yields either an accrual with an explicit rate and reason, or a **zero with a machine-readable reason code** — never a silent absence. Redelivery of the same event produces no second accrual.

**Verification.** Unit tests over a golden fixture set (§8.3) asserting amount *and* reason code per transaction; an integration test that replays the same clearing event 5× and asserts exactly one ledger entry; a property test asserting `accrual = round_half_up(eligible_amount × rate_bps / 10000)` for random inputs. Review checkpoint: every terminal branch of the rule engine emits a reason code (enforced by an exhaustiveness test, not by inspection).

### M2 — Two-stage visibility: pending on authorization, confirmed on clearing

The user sees `pending` cashback within seconds of paying, and `confirmed` cashback once the transaction clears. When the cleared amount differs from the authorized amount (tips, fuel pre-auth, partial capture), the pending accrual is **adjusted in place** to match the cleared reality rather than duplicated. An authorization that never clears drops its pending accrual without ever touching the ledger.

**Verification.** Integration tests for four sequences: auth→clear equal; auth→clear higher; auth→clear lower; auth→expiry. Each asserts final user-visible state and asserts that pending amounts never appear in the payable balance. Manual review checkpoint: pending is presented in the UI copy as an estimate, not a promise.

### M3 — Caps are enforced without races

Three caps apply — per transaction, per category per calendar month, per user per calendar month. Under concurrent transactions for the same user, the sum of accruals **never exceeds** the cap by even one kopiyka. When a cap truncates or blocks a reward, the user is told which cap and what the remaining headroom is.

**Verification.** A concurrency test firing 100 simultaneous qualifying transactions against a user with 1 ₴ of remaining headroom, asserting total accrued = exactly 1 ₴ and 99 transactions carry a `CAP_*` reason code. Review checkpoint: no read-then-write on cap counters anywhere in the codebase (grep-able, and asserted by T9's acceptance criteria).

### M4 — Clawback: a late reversal is always recoverable

A refund reverses cashback **proportionally to the refunded amount, at the rate and rule version of the original accrual** — not at today's rate. A chargeback reverses in full. If the cashback was already paid out, the reversal creates a **negative carry balance** that is recovered from future accruals; it is never silently debited from the user's main account balance.

**Verification.** Integration tests: partial refund (asserts proportional reversal at the historical rate even after a rate change), full refund post-payout (asserts negative carry, asserts main account untouched), chargeback (asserts full reversal + fraud signal). A reconciliation test asserting the ledger still sums correctly after each. Compliance review checkpoint: the negative-carry policy (§5.4) is signed off by compliance before launch.

### M5 — Payout: monthly, idempotent, resumable

A background run credits confirmed cashback to the user's account balance. **No user is paid twice; no eligible user is skipped**, including when the run crashes halfway and is restarted. Amounts below the minimum threshold roll over to the next run rather than being lost.

**Verification.** A kill-and-resume test: run the batch over 10,000 synthetic users, kill the process at a random point, restart, assert exactly one payout ledger entry per eligible user and a total equal to the pre-run payable sum. Reconciliation (M9) run immediately after payout must tie out to zero discrepancy.

### M6 — Rule versioning: rate changes never rewrite the past

The program owner can change rates, categories and caps. Every accrual permanently references the **rule version that produced it**, and activating a new version does not re-score already-evaluated transactions. A transaction is scored against the version that was active **at its authorization timestamp**, not at processing time.

**Verification.** Integration test: score a transaction, activate a new version with a different rate, replay/reprocess the transaction, assert the amount and `rule_version_id` are unchanged. Test: a transaction authorized before a version change but *cleared* after it is scored at the **old** rate. Review checkpoint: rule versions are immutable once activated (DB constraint, not convention).

### M7 — Audit, manual adjustment, and explainability

Every change to a reward balance carries an immutable record of actor, reason and correlation ID. Manual adjustments require **maker-checker**: a second, distinct human approves before money moves, and the adjustment references a support case. Support can retrieve, for any transaction, the full decision trace: which rule version, which rate, which caps applied, which reason code.

**Verification.** Test asserting an adjustment where maker == checker is rejected. Test asserting an adjustment without a case reference is rejected. Test asserting no ledger row can be UPDATEd or DELETEd (DB-level). Manual compliance review: a sampled adjustment is reconstructed end-to-end from the audit log alone, with no access to application logs.

### M8 — Abuse controls: hold before you pay, not after

Patterns indicating reward farming — high buy-and-return ratio, rapid transaction cycling with a single merchant, spend spikes wildly out of profile — place accruals into a `held` state that is **excluded from payout** and escalated to fraud. The user sees "under review", not a silent zero and not a payout.

**Verification.** Fixture-driven tests over labelled abuse scenarios (§8.3) asserting hold vs. pass. Test asserting held accruals are excluded from the payout query. Ops review checkpoint: every hold has an owner and an SLA (T20); a hold that nobody resolves is itself a defect.

### M9 — Finance can close the books

A daily reconciliation proves `Σ accruals − Σ reversals − Σ payouts = current outstanding liability`. Any discrepancy raises an alert **that same morning**, listing the offending records rather than just a number.

**Verification.** Reconciliation is itself tested: inject a deliberately corrupted ledger row into a test fixture and assert the job detects it, names it, and alerts. A monthly accrued-liability report is compared against the general ledger export in a manual finance checkpoint.

---

## 5. Non-Functional & Policy

### 5.1 Performance targets

These are **assumed targets** derived from §3 — the reasoning is given because a number without a reason cannot be renegotiated.

| Path | Target | Why this number |
|---|---|---|
| **Read** — reward balance + accrual list (50 rows) | p95 ≤ 200 ms, p99 ≤ 500 ms | An ordinary in-app screen; it competes with the balance screen, not with a payment. Past ~200 ms, scrolling stops feeling instant. |
| **Pending accrual visible** (auth event → in-app) | p95 ≤ 5 s | The user is looking at their phone at the till. Five seconds is "while I put my card away". Chasing sub-second here buys nothing: the amount is provisional anyway. |
| **Clearing event processing** | p95 ≤ 2 s, p99 ≤ 10 s | Internal budget; keeps the queue drainable at peak. |
| **Clearing → confirmed cashback visible** (end-to-end) | ≤ 24 h at p99 | Clearing itself arrives T+1…T+3 from the network. Promising the user seconds would be promising something we do not control. |
| **Event ingest** | 500 events/s sustained; 3,000 events/s peak; backlog drains ≤ 30 min after peak | 40 M/month ≈ 15/s mean, ×6 seasonal peak, ×3 headroom for retries and backfill. |
| **Payout batch** | 2,000,000 accounts in ≤ 4 h (≈ 140/s), resumable | Must finish inside the night window and before the morning traffic peak; "by end of day 5" is a promise the user can see. |
| **Reconciliation** | 30 M+ ledger rows in ≤ 30 min; alert on discrepancy > 1 kopiyka | Must complete before finance starts work, so a break is actionable the same morning. |
| **Explain-a-decision** (support tool) | p95 ≤ 300 ms | The agent has a customer on the line. |

**Pagination rule:** accrual history is cursor-paginated, page size default 50, max 200. Cursor is `(occurred_at DESC, id DESC)` so that concurrent inserts cannot cause a row to be skipped or repeated across pages.

**Rate limits:** explain-a-decision 10 req/s per support agent; user-facing reward endpoints 20 req/min per user.

**Read-after-write:** a user who triggers an action that changes their reward balance must observe the new balance on the next read (read-your-writes within 1 s). Cross-user consistency may lag up to 5 s.

### 5.2 Reliability

- **Effectively-once processing.** Every inbound event carries a stable event ID; processing is idempotent on that ID. At-least-once delivery is assumed from the bus; exactly-once is achieved at the sink, not in transit.
- **RPO = 0** for the reward ledger (it is financial record); **RTO ≤ 1 h**.
- **Availability:** earn path 99.9 % monthly (it is asynchronous and tolerates lag); read path 99.95 %; **the payout run has no availability SLO — it has a deadline:** it must complete before the end of day 5 of the month, retried as many times as needed.
- **Degradation:** if the rule service is unavailable, events are **parked, not dropped, and not scored with a default rate**. Guessing a rate is a monetary error; lagging is an inconvenience.

### 5.3 Money handling (binding)

- All monetary amounts are **integers in minor units** (kopiyky). Floating point is forbidden anywhere in the money path — including intermediate calculations, JSON payloads, and test fixtures.
- Rates are expressed in **basis points** (integer). `accrual = round_half_up(eligible_minor × rate_bps, 10000)`.
- Rounding happens **once, per transaction**, never on aggregates. The rounding remainder is recorded per accrual so that reconciliation can account for it rather than write it off.
- A reward amount is never negative on an accrual row; reversals are separate, signed ledger entries. "Negative cashback" exists only as a **carry balance**, never as a negative accrual.

### 5.4 Reward balance model

Four balances, and they are not interchangeable:

| Balance | Meaning | Payable? |
|---|---|---|
| `pending` | Authorized, not yet cleared. Provisional. | No |
| `confirmed` | Cleared and scored. Awaiting the next payout run. | Yes, after threshold |
| `paid` | Credited to the account balance. Left this system. | — |
| `negative_carry` | Cashback that was paid out and later invalidated. | Recovered from future accruals |

**Negative carry policy:** recovered by offsetting future accruals at 100 % until cleared. It is **never** debited from the user's main account balance. If a user closes their account with an outstanding carry, it is written off with finance approval above a threshold — collection is out of scope. This policy is deliberately conservative: clawing money out of a customer's current account for a refunded purchase is the kind of action that generates regulatory complaints, and the amounts involved (kopiyky to tens of hryvnia) do not justify the risk.

### 5.5 Security

- **Never log, store, or forward PAN, CVV, or full track data.** This system receives and stores only a `card_token` and `last4`. If a PAN appears in an inbound payload, it is a **defect in the producer**: drop the field, alert, do not persist. There is no configuration flag that enables PAN logging.
- Merchant name and MCC are transaction data and are treated as personal data by association: they may not be exported to analytics without aggregation.
- Manual adjustment endpoints require an ops role **and** maker-checker (§M7). Segregation of duties is enforced by the system, not by procedure: the same principal cannot occupy both roles on one adjustment.
- Every mutating operation carries a correlation ID that appears in the ledger row and in the audit log, so a support ticket, an application log line and a money movement can be joined.

### 5.6 Privacy, audit and retention

- Reward ledger entries and audit records are retained **7 years** (financial record-keeping obligation).
- **Erasure request conflict:** a GDPR/CCPA erasure request pseudonymizes the user's identity (profile fields, contact data) but **does not delete ledger rows**, which are retained under a legal obligation basis. The link is severed via a tombstone mapping. This conflict is explicit and expected; it must be documented in the privacy notice, not resolved by deleting financial records.
- Audit records are append-only, written in the **same transaction** as the money movement they describe. An audit write that fails rolls back the money movement — not the other way round.

### 5.7 Error semantics

- **User-visible errors** state what happened and what the user can do; they never expose internal reason codes verbatim. `CAP_CATEGORY_MONTH` becomes "You've reached this month's 200 ₴ limit for groceries."
- **Zero is never an error.** A transaction that earns nothing is a successful evaluation with a reason.
- Retryable vs. terminal failures are distinguished explicitly. A malformed event is terminal (dead-letter + alert). An unavailable dependency is retryable (park + backoff).
- Dead-lettered events are a **compliance concern**, not just an ops one: an event stuck in the DLQ is money not paid to a customer. DLQ depth > 0 for more than 1 h pages a human.

---

## 6. Implementation Notes (guardrails)

**Stack assumption.** TypeScript (Node 20), PostgreSQL 15 as the system of record, an event bus with at-least-once delivery (Kafka-shaped), Fastify for the internal HTTP surfaces. These are assumptions for the sake of concreteness; the *rules* below are stack-independent.

**Domain model (system of record).**

| Table | Role | Non-negotiable property |
|---|---|---|
| `reward_rule_version` | Rate/category/cap definitions | Immutable once `active`; has `effective_from` |
| `accrual` | One row per scored transaction | Unique on `transaction_id`; references `rule_version_id`; carries `reason_code` and `rounding_remainder_minor` |
| `reward_ledger_entry` | Double-entry, append-only money movement | `INSERT` only — no `UPDATE`, no `DELETE`, enforced by DB privileges and a trigger |
| `cap_counter` | Per-user/category/month consumption | Updated only via atomic conditional `UPDATE … WHERE consumed + :amt <= cap RETURNING` |
| `payout_run` / `payout` | Batch orchestration | `payout` unique on `(run_id, user_id)`; carries an idempotency key |
| `adjustment` | Manual correction | `maker_id <> checker_id` enforced by CHECK constraint |
| `processed_event` | Dedupe | Unique on `event_id`; written in the same transaction as its effect |

**Ledger entry types (the only four ways money moves):** `ACCRUAL` (+), `REVERSAL` (−), `PAYOUT` (−, leaves the system), `ADJUSTMENT` (±, requires maker-checker). A correction is **a new compensating entry, never an edit**.

**Reason codes (closed set — adding one is a spec change):**
`EARNED`, `NO_RULE_MATCH`, `EXCLUDED_MCC`, `INELIGIBLE_ACCOUNT_STATUS`, `CAP_TXN`, `CAP_CATEGORY_MONTH`, `CAP_USER_MONTH`, `ZERO_AFTER_ROUNDING`, `HELD_FRAUD_REVIEW`, `REVERSED_REFUND`, `REVERSED_CHARGEBACK`.

**Period attribution.** A transaction belongs to the reward period of its **authorization timestamp**, in `Europe/Kyiv` local time — because that is the date the user remembers making the purchase. A transaction authorized on 28 February but cleared on 2 March belongs to February's period, even though it will be paid in a later run. Period boundaries are local-midnight, not UTC-midnight.

**Idempotency.** Every write path is keyed: event consumers on `event_id`, payouts on `(run_id, user_id)`, adjustments on a client-supplied key. Writing the dedupe record and the effect must be **one transaction** — otherwise a crash between them either double-pays or loses money, and which one it is depends on the order, which is not a decision worth making twice.

**Never do these** (an AI agent violating any of these is producing a defect, not a style deviation):

1. Never use floating point for money.
2. Never read a cap counter and then write it in a separate statement.
3. Never re-score a transaction against the current rule version when correcting it.
4. Never mutate or delete a ledger row.
5. Never log PAN, CVV, or the full inbound payload of a card event.
6. Never debit the user's main account to recover cashback.
7. Never assign a default rate when the rule service is unavailable.
8. Never emit a zero accrual without a reason code.

---

## 7. Edge Cases and Failure Modes

Expected behavior is stated as **user-visible outcome** + **audit/compliance implication**. Anchored to the objective that owns it.

| # | Scenario | Expected behavior | Audit / compliance implication | Obj. |
|---|---|---|---|---|
| E1 | Clearing event redelivered 5× | Exactly one accrual; duplicates ack'd silently | Dedupe recorded; no ledger noise | M1 |
| E2 | Cleared amount **higher** than authorized (tip added) | Pending accrual adjusted upward in place; user sees the final figure | Single accrual row, amended once; delta visible in decision trace | M2 |
| E3 | Cleared amount **lower** than authorized (partial capture) | Pending adjusted downward; never negative | Same | M2 |
| E4 | Authorization never clears (expires) | Pending accrual disappears; **no ledger entry ever written** | Pending is not money; nothing to reconcile | M2 |
| E5 | 100 concurrent transactions, 1 ₴ of cap headroom left | Total accrued = exactly 1 ₴; the rest carry `CAP_*` | Cap enforcement provable from counters | M3 |
| E6 | Rate changes mid-month | Transactions authorized before the change keep the old rate | Each accrual names its `rule_version_id` forever | M6 |
| E7 | Transaction authorized before a rate change, cleared after | Scored at the **old** rate (authorization time wins) | Documented rule; testable | M6 |
| E8 | Refund of 50 % of a purchase | 50 % of the cashback reversed, **at the original rate** | Reversal entry references the original accrual | M4 |
| E9 | Refund arrives **after** payout | Negative carry balance created; recovered from future accruals; main account untouched | Explicit policy §5.4; user notified | M4 |
| E10 | Chargeback | Full reversal + fraud signal raised | Reversal reason `REVERSED_CHARGEBACK`; feeds M8 | M4, M8 |
| E11 | User closes account with negative carry | Written off with finance approval above threshold; no collection | Write-off is an `ADJUSTMENT` with maker-checker | M4 |
| E12 | Payout batch crashes at 60 % | Restart resumes; nobody paid twice, nobody skipped | `(run_id, user_id)` uniqueness is the proof | M5 |
| E13 | Confirmed cashback below the 10 ₴ threshold | Rolls over to the next run; user sees "will be paid when you reach 10 ₴" | No lost money; balance still on the books as liability | M5 |
| E14 | Accrual confirmed **after** its period's payout run already ran | Paid in the next run, but keeps its original period label | Period attribution stays honest for finance reporting | M5, M9 |
| E15 | Rule service unavailable during ingest | Events parked and retried; **no default rate applied** | Lag is visible; a wrong rate would be a monetary error | M1 |
| E16 | Rule version with an invalid rate (e.g. 150 %) submitted | Rejected at authoring time by validation; cannot be activated | Rule activation is itself maker-checker'd | M6 |
| E17 | Buy-and-return cycling on one merchant | Accruals move to `held`; user sees "under review"; excluded from payout | Fraud case opened with an owner and SLA | M8 |
| E18 | A `held` accrual nobody resolves for 30 days | Escalation fires; unresolved holds are reported as a defect, not left to rot | Ops SLA breach is auditable | M8 |
| E19 | Support agent tries to adjust their own case (maker == checker) | Rejected by the system | Segregation of duties enforced in code, not procedure | M7 |
| E20 | Adjustment submitted without a case reference | Rejected | Every money movement traces to a reason | M7 |
| E21 | Inbound event contains a PAN | Field dropped, alert raised, **never persisted or logged** | Producer defect reported; no PCI scope creep | §5.5 |
| E22 | Ledger row `UPDATE` attempted (bug or malice) | Fails at the database level | Append-only is a constraint, not a convention | M7 |
| E23 | Erasure request from a user with reward history | Profile pseudonymized; ledger rows retained 7 years | Documented lawful-basis conflict; not resolved by deletion | §5.6 |
| E24 | Reconciliation finds a 3 kopiyka discrepancy | Alert the same morning, listing the offending rows | Finance cannot close the books on an unexplained delta | M9 |
| E25 | Transaction in a currency other than UAH | Not scored; reason `NO_RULE_MATCH`; alert (out-of-scope input) | Fails loudly rather than guessing an FX rate | §3 |
| E26 | Rounding produces 0 kopiyky (e.g. 0.30 ₴ at 0.5 %) | Zero accrual with reason `ZERO_AFTER_ROUNDING` — not an empty result | Zero is a decision, and it is explainable | M1 |
| E27 | Two rule versions overlap in `effective_from` | Activation rejected; overlap is a constraint violation | Only one rule can ever score a transaction | M6 |
| E28 | Event arrives for a closed/frozen card | Scored normally if the transaction cleared — the card's state does not retroactively void a legitimate purchase; blocked only if the account is `INELIGIBLE_ACCOUNT_STATUS` at authorization time | Prevents accidental confiscation of earned rewards | M1 |

---

## 8. Context

### 8.1 Beginning context (what exists before work starts)

Hypothetical but specific — an agent should not have to guess where the world ends and this feature begins.

**Existing services (consumed, not built here):**
- `card-service` — issues cards; owns `card_token`, `last4`, card state.
- `ledger-service` — owns the user's **main account balance**; exposes `POST /credits` (idempotent, keyed) — the only way cashback money reaches a user.
- `transaction-stream` (Kafka-shaped) — emits: `card.authorized`, `card.cleared`, `card.auth_expired`, `card.refunded`, `dispute.chargeback_settled`. At-least-once delivery. Payloads carry `event_id`, `transaction_id`, `user_id`, `card_token`, `last4`, `mcc`, `merchant_name`, `amount_minor`, `currency`, `authorized_at`, `cleared_at`.
- `identity-service` — user identity, account status, erasure/tombstone registry.
- `fraud-service` — exposes risk signals; owns fraud cases and their SLAs.
- `notification-service` — user-facing messages.

**Existing infrastructure:** PostgreSQL 15, the event bus, an observability stack (metrics/traces/logs), a secrets manager. No rewards tables exist. No rules exist. **No cashback has ever been paid** — there is no historical balance to migrate, which is why this spec contains no backfill objective.

**Existing constraints inherited from the org:** PCI DSS scope is confined to `card-service`; this system must stay outside it (§5.5). Financial records retention is 7 years (§5.6).

### 8.2 Ending context (what exists after work is done)

**New service `rewards-service`:**

```
rewards-service/
├── src/
│   ├── domain/
│   │   ├── money.ts                  # minor units, round_half_up, no floats (T1)
│   │   ├── reason-codes.ts           # closed enum (T7)
│   │   ├── rule-version.ts           # resolution by authorized_at (T4)
│   │   ├── rule-engine.ts            # scoring → amount + reason (T7)
│   │   ├── eligibility.ts            # MCC/currency/status filters (T8)
│   │   ├── caps.ts                   # atomic cap enforcement (T9)
│   │   ├── clawback.ts               # proportional reversal, negative carry (T13–T15)
│   │   ├── fraud-hold.ts             # abuse patterns → held (T19)
│   │   └── balances.ts               # pending/confirmed/paid/negative_carry (T2)
│   ├── ingest/
│   │   ├── authorized.consumer.ts    # (T6)
│   │   ├── cleared.consumer.ts       # (T10)
│   │   ├── auth-expired.consumer.ts  # (T11)
│   │   ├── refunded.consumer.ts      # (T13)
│   │   └── chargeback.consumer.ts    # (T14)
│   ├── payout/
│   │   ├── run.orchestrator.ts       # resumable batch (T16)
│   │   └── credit.client.ts          # idempotent call to ledger-service (T17)
│   ├── ops/
│   │   ├── explain.handler.ts        # decision trace for support (T21)
│   │   ├── adjustment.handler.ts     # maker-checker (T22)
│   │   ├── rule-authoring.handler.ts # draft → activate, maker-checker (T5)
│   │   ├── fraud-escalation.ts       # case per hold, owner + SLA (T20)
│   │   └── erasure.handler.ts        # pseudonymize, retain ledger (T24)
│   ├── finance/
│   │   ├── reconciliation.job.ts     # (T25)
│   │   └── liability.report.ts       # (T26)
│   └── platform/
│       ├── idempotency.ts            # processed_event (T3)
│       ├── audit.ts                  # append-only audit writes (T23)
│       └── slo.ts                    # instrumentation (T27)
├── migrations/                       # tables + append-only triggers (T2), rule versions (T4), rounding remainder (T12)
├── fixtures/                         # golden decision cases, abuse cases (T28)
└── docs/
    ├── runbook-payout.md             # what to do when the batch fails
    └── privacy-retention.md          # erasure vs retention (T24)
```

**System state after:** rules can be authored and activated; cleared transactions accrue; refunds and chargebacks reverse; a monthly batch pays out; finance reconciles nightly; support can explain any decision; compliance can reconstruct any money movement from the audit log alone.

### 8.3 Test data / fixtures that must exist

- **Golden decision set:** ≥ 40 transactions covering every reason code, every cap boundary (just under, exactly at, just over), and the rounding boundary cases (0.005 ₴ up, 0.004 ₴ down, 0.30 ₴ at 0.5 % → zero).
- **Sequence fixtures:** the four auth→clear sequences of E2–E4, plus refund-before-payout and refund-after-payout.
- **Abuse fixtures:** labelled buy-and-return cycling, merchant cycling, and a legitimate high-spend user who must **not** be held (the false-positive case is the one that matters).
- **Reconciliation fixture:** a deliberately corrupted ledger, to prove the job detects rather than assumes.

---

## 9. Low-Level Tasks

Each task names the objective it serves (**traceability**), the prompt that would drive it, the file and function, the constraints, and an **acceptance criterion an implementer can tick off**. Tasks are ordered so that each depends only on those before it.

### Foundations

#### T1 — Money primitives
**Serves:** M1, §5.3
**Prompt:** "Implement money handling in minor units with half-up rounding and an explicit remainder, in TypeScript. No floating point anywhere, including in tests."
**File:** `src/domain/money.ts`
**Functions:** `applyRateBps(amountMinor: bigint, rateBps: number): { amountMinor: bigint; remainderMinor: bigint }`, `sumMinor`, `assertNonNegative`
**Details:** Integers (`bigint`) only. `round_half_up(amount × bps, 10000)`. Return the discarded remainder — the caller must persist it (§5.3). Reject negative rates and rates > 10000 bps.
**Acceptance criteria:**
- Property test over 10⁵ random `(amount, bps)` pairs: `amount × bps = result × 10000 + remainder × something` holds exactly; no precision loss.
- A lint rule fails the build if `number` is used for any variable named `*_minor` / `*Minor`.
- `applyRateBps(30n, 50)` (0.30 ₴ at 0.5 %) returns `0n` — a legitimate zero (E26).

#### T2 — Ledger and core schema, append-only
**Serves:** M1, M4, M5, M7, M9
**Prompt:** "Create migrations for `reward_ledger_entry`, `accrual`, `cap_counter`, `payout_run`, `payout`, `adjustment`, `processed_event`. The ledger must be physically append-only."
**File:** `migrations/001_rewards_core.sql`
**Details:** `reward_ledger_entry` is `INSERT`-only: revoke `UPDATE`/`DELETE` from the application role **and** add a `BEFORE UPDATE OR DELETE` trigger that raises. Entry types `ACCRUAL | REVERSAL | PAYOUT | ADJUSTMENT`. `accrual` unique on `transaction_id`. `adjustment` has `CHECK (maker_id <> checker_id)`.
**Acceptance criteria:**
- An integration test that attempts `UPDATE reward_ledger_entry` fails with a database error (not an application error) — E22.
- An attempt to insert two accruals for one `transaction_id` violates a unique constraint — E1.
- An adjustment with `maker_id = checker_id` is rejected by the database — E19.

#### T3 — Idempotent event processing
**Serves:** M1
**Prompt:** "Implement a consumer wrapper that records `event_id` in `processed_event` and executes the handler's effect **in the same transaction**."
**File:** `src/platform/idempotency.ts`
**Function:** `withIdempotency(eventId: string, fn: (tx) => Promise<void>): Promise<void>`
**Details:** Duplicate `event_id` → ack, no-op, no error. The dedupe insert and the effect share one DB transaction (§6). No "check then act".
**Acceptance criteria:** replaying an event 5× produces exactly one effect and five acks; killing the process between the effect and the ack results in **zero** duplicate effects on redelivery.

#### T4 — Rule versions and time-based resolution
**Serves:** M6
**Prompt:** "Implement rule version storage and a resolver that selects the version active at a transaction's `authorized_at`."
**Files:** `migrations/002_rule_versions.sql`, `src/domain/rule-version.ts`
**Function:** `resolveVersionAt(authorizedAt: Date): Promise<RuleVersion>`
**Details:** Versions are immutable once `active` (DB trigger). `effective_from` ranges may not overlap (exclusion constraint) — E27. Resolution uses `authorized_at`, never `now()` (E7).
**Acceptance criteria:**
- Activating a version whose range overlaps an existing one is rejected **by the database**.
- A transaction authorized 28 Feb and processed 2 Mar, across a 1 Mar rate change, resolves to the **February** version.
- `UPDATE` on an `active` rule version fails.

#### T5 — Rule authoring workflow (draft → activate) with maker-checker
**Serves:** M6, M7
**Prompt:** "Implement draft creation, validation, and two-person activation of a rule version."
**File:** `src/ops/rule-authoring.handler.ts`
**Functions:** `createDraft`, `validateDraft`, `activate`
**Details:** Validation rejects rates outside 0–500 bps, caps ≤ 0, unknown MCCs, and overlapping effective ranges (E16). Activation requires a second, distinct principal. Both actions are audited.
**Acceptance criteria:** a draft with a 150 % rate cannot be activated; activation by the drafting user alone is rejected; both events appear in the audit log with actor and correlation ID.

### Earn path

#### T6 — `card.authorized` → pending accrual
**Serves:** M2
**Prompt:** "Consume `card.authorized`, score it, and write a **pending** accrual — with no ledger entry."
**File:** `src/ingest/authorized.consumer.ts`
**Details:** Pending is **not money**: it produces no `reward_ledger_entry` (E4). Scored using the same engine as clearing, so pending and confirmed cannot diverge in logic.
**Acceptance criteria:** after an authorization, the user sees a pending amount within 5 s (p95, §5.1) and `reward_ledger_entry` count is unchanged.

#### T7 — Rule evaluation engine
**Serves:** M1
**Prompt:** "Implement scoring: given a transaction and a rule version, return an amount **and** a reason code. Every branch returns a reason."
**File:** `src/domain/rule-engine.ts`
**Function:** `score(txn: Transaction, version: RuleVersion, caps: CapState): ScoreResult`
**Details:** Closed reason-code set (§6). Pure function — no I/O, no clock, no randomness, so it is trivially testable and replayable.
**Acceptance criteria:**
- An exhaustiveness test asserts every terminal branch emits a reason code (a branch returning `0` with no reason fails the build).
- Golden fixture set (§8.3) passes on both amount and reason.
- Scoring the same input twice returns byte-identical output (determinism).

#### T8 — Eligibility filters
**Serves:** M1
**Prompt:** "Reject non-qualifying transactions with the correct reason before rate logic runs."
**File:** `src/domain/eligibility.ts`
**Details:** Excluded MCCs (gambling, cash advance, crypto, P2P transfers — these are not "spend"), non-UAH currency → `NO_RULE_MATCH` + alert (E25), ineligible account status **at authorization time** (E28).
**Acceptance criteria:** a USD transaction is not scored and raises an alert rather than guessing an FX rate; a card frozen *after* the purchase still earns its cashback (E28).

#### T9 — Cap enforcement (atomic)
**Serves:** M3
**Prompt:** "Enforce per-transaction, per-category-month, and per-user-month caps with a single atomic conditional update. Read-then-write is forbidden."
**File:** `src/domain/caps.ts`
**Function:** `consumeCap(userId, category, period, amountMinor): { granted: bigint; reason?: ReasonCode; headroomMinor: bigint }`
**Details:** One statement: `UPDATE cap_counter SET consumed = consumed + LEAST(:amt, cap - consumed) WHERE … RETURNING`. Partial grants are allowed (a transaction may be truncated by a cap) and must be reported as such, with the headroom, so the user can be told (M3).
**Acceptance criteria:**
- The 100-concurrent-transactions test (E5) yields **exactly** the cap, never a kopiyka more.
- A code search for a read of `cap_counter` followed by a write in a separate statement returns nothing.
- A truncated accrual carries both the granted amount and a `CAP_*` reason.

#### T10 — `card.cleared` → confirm / amend the accrual
**Serves:** M1, M2, M3
**Prompt:** "On clearing, confirm the pending accrual, amending it if the cleared amount differs; write the ledger entry."
**File:** `src/ingest/cleared.consumer.ts`
**Details:** Cleared > authorized (tip) → adjust up; cleared < authorized → adjust down (E2, E3). Amendment adjusts the **existing** accrual row and writes **one** `ACCRUAL` ledger entry for the final amount. Cap counters are adjusted by the delta, atomically.
**Acceptance criteria:** all four auth→clear sequences (§8.3) end in one accrual row and at most one ledger entry; a tip that pushes the user over a cap is truncated correctly.

#### T11 — `card.auth_expired` → drop pending
**Serves:** M2
**Prompt:** "Delete the pending accrual for an expired authorization. Assert no ledger entry exists."
**File:** `src/ingest/auth-expired.consumer.ts`
**Acceptance criteria:** pending disappears from the user's view; `reward_ledger_entry` count is zero for that transaction; cap headroom released (E4).

#### T12 — Rounding remainder accounting
**Serves:** M1, M9
**Prompt:** "Persist the rounding remainder per accrual and expose it to reconciliation."
**File:** `src/domain/money.ts` (extend), `migrations/003_rounding_remainder.sql`
**Details:** The remainder is recorded, not discarded (§5.3), so that reconciliation's residual is explainable rather than a mystery delta.
**Acceptance criteria:** reconciliation (T25) can account for every kopiyka of difference between `Σ(eligible × rate)` and `Σ(accrued)` using the stored remainders alone.

### Reversal path

#### T13 — `card.refunded` → proportional reversal
**Serves:** M4
**Prompt:** "Reverse cashback proportionally to the refunded amount, at the **original** accrual's rate and rule version."
**File:** `src/ingest/refunded.consumer.ts`
**Function:** `reverseProportional(originalAccrual, refundedMinor)`
**Details:** Never re-score against the current rules (§6, rule 3). Partial refunds reverse pro-rata; rounding uses the same half-up rule and the remainder is recorded. Writes a `REVERSAL` ledger entry, never edits the accrual (E8). Releases cap headroom.
**Acceptance criteria:** a 50 % refund after a rate change reverses exactly 50 % of the **original** cashback; the total of accrual + reversal ledger entries equals the correct net; the accrual row is unchanged.

#### T14 — `dispute.chargeback_settled` → full reversal + fraud signal
**Serves:** M4, M8
**Prompt:** "Reverse the full cashback for a charged-back transaction and emit a fraud signal."
**File:** `src/ingest/chargeback.consumer.ts`
**Acceptance criteria:** full reversal with reason `REVERSED_CHARGEBACK`; a signal reaches `fraud-service` with the correlation ID; if already paid out, T15's negative carry path is taken (E10).

#### T15 — Negative carry balance
**Serves:** M4
**Prompt:** "When a reversal exceeds the available confirmed balance, create a negative carry balance and recover it from future accruals. The main account must never be debited."
**File:** `src/domain/clawback.ts`
**Function:** `applyReversal(userId, amountMinor): { fromConfirmed; toNegativeCarry }`
**Details:** Recovery offsets future accruals at 100 % until cleared (§5.4). Account closure with an outstanding carry → write-off as an `ADJUSTMENT` with maker-checker above a threshold (E11). No call to `ledger-service` debit ever exists in this code path — its absence is the guarantee.
**Acceptance criteria:**
- Refund-after-payout produces a negative carry and **zero** calls to `ledger-service` debit (asserted by a test that fails if such a client method is even imported).
- The next accrual is fully consumed by the carry, and the user is notified.

### Payout

#### T16 — Payout run orchestration (resumable)
**Serves:** M5
**Prompt:** "Implement the monthly payout run: select eligible users, chunk, checkpoint, and resume from the last checkpoint after a crash."
**File:** `src/payout/run.orchestrator.ts`
**Details:** Eligible = confirmed accruals for the closed period, minus held (M8), minus negative carry, ≥ 10 ₴ threshold; below threshold rolls over (E13). Runs at 02:00 Kyiv on day 5. Chunked with checkpoints; `payout_run` has states `pending → running → completed | failed`.
**Acceptance criteria:** the kill-and-resume test (M5 verification) over 10,000 users produces exactly one payout per eligible user; the run meets the 4 h / 2 M-account target (§5.1) in a load test; a re-run after `completed` is a no-op.

#### T17 — Idempotent credit to the main account
**Serves:** M5
**Prompt:** "Credit `ledger-service` with an idempotency key of `(run_id, user_id)` and record the `PAYOUT` ledger entry in the same transaction as the confirmed remote credit."
**File:** `src/payout/credit.client.ts`
**Details:** The remote call may be retried; the key makes it safe. If the remote credit's outcome is **unknown** (timeout), the run must not guess: it re-drives the same key until it gets a definitive answer.
**Acceptance criteria:** injecting a timeout-then-success into the credit call results in exactly one credit and exactly one `PAYOUT` ledger entry (E12).

#### T18 — Late accruals
**Serves:** M5, M9
**Prompt:** "An accrual confirmed after its period's payout run must be paid in the next run while keeping its original period label."
**File:** `src/payout/run.orchestrator.ts` (extend)
**Acceptance criteria:** a transaction authorized in February but cleared on 6 March (after the run) is paid in the April run, still reported to finance under February (E14).

### Fraud

#### T19 — Abuse detection → `held`
**Serves:** M8
**Prompt:** "Place accruals matching abuse patterns into `held`, excluded from payout, and surface 'under review' to the user."
**File:** `src/domain/fraud-hold.ts`
**Details:** Patterns: buy-and-return ratio above threshold over a rolling window; repeated purchase/refund cycling with one merchant; spend spikes far outside the user's profile. **Thresholds are configuration, not code** — they will be tuned and must not require a deploy.
**Acceptance criteria:** labelled abuse fixtures are held; the legitimate high-spend fixture is **not** held (the false positive is the failure that matters, §8.3); held accruals are provably excluded from T16's eligibility query.

#### T20 — Fraud escalation and SLA
**Serves:** M8
**Prompt:** "Open a fraud case for every hold, with an owner and an SLA; escalate unresolved holds."
**File:** `src/ops/fraud-escalation.ts`
**Details:** A hold older than 30 days escalates (E18). Resolution outcomes: `release` (accrue and pay), `confirm_abuse` (reverse), `close_no_action`. Every outcome is audited.
**Acceptance criteria:** a hold with no resolution after 30 days raises an escalation; a released hold is paid in the next run; unresolved-hold count is a dashboard metric with an alert.

### Ops, compliance, support

#### T21 — Explain-a-decision
**Serves:** M7, M1
**Prompt:** "Given a transaction ID, return the full decision trace: rule version, matched rule, rate, eligible amount, caps applied with headroom, rounding remainder, reason code, and every subsequent ledger entry."
**File:** `src/ops/explain.handler.ts`
**Details:** p95 ≤ 300 ms (§5.1). The response must be sufficient to reconstruct the arithmetic **by hand**. Support-facing; PAN never appears (only `last4`).
**Acceptance criteria:** for any fixture transaction, a human can reproduce the final figure from the response alone; a load test meets the 300 ms p95; a response-shape test asserts no field can carry a PAN.

#### T22 — Manual adjustment (maker-checker)
**Serves:** M7
**Prompt:** "Implement a two-person manual adjustment: maker proposes with a reason and case reference, checker approves, and only then does money move."
**File:** `src/ops/adjustment.handler.ts`
**Details:** `maker_id <> checker_id` (T2). Case reference mandatory (E20). Amounts above a threshold require the compliance role. The money movement is an `ADJUSTMENT` ledger entry — never an edit (§6, rule 4).
**Acceptance criteria:** self-approval rejected (E19); missing case reference rejected (E20); an approved adjustment produces exactly one ledger entry and two audit records (proposal, approval).

#### T23 — Audit log
**Serves:** M7, §5.5
**Prompt:** "Write an append-only audit record — actor, action, reason, correlation ID, before/after — in the same transaction as every money movement. Never log PAN."
**File:** `src/platform/audit.ts`
**Details:** A failed audit write **rolls back the money movement** (§5.6). A field-level redaction layer drops PAN/CVV if a producer ever sends one, and alerts (E21).
**Acceptance criteria:** a forced audit-write failure leaves **no** ledger entry behind; an inbound payload containing a `pan` field results in an alert and a persisted record with no PAN anywhere (asserted by scanning the DB and the log sink in the test).

#### T24 — Erasure vs. retention
**Serves:** M7, §5.6
**Prompt:** "Handle an erasure request: pseudonymize identity, retain ledger rows for 7 years, sever the link via a tombstone."
**Files:** `src/ops/erasure.handler.ts`, `docs/privacy-retention.md`
**Details:** Ledger rows are **not** deleted (E23). The documented rationale (legal obligation basis) is part of the deliverable, because compliance will be asked about it and "the code does it" is not an answer.
**Acceptance criteria:** after erasure, the user is not identifiable from reward tables alone; ledger row count is unchanged; reconciliation (T25) still ties out; `docs/privacy-retention.md` states the conflict explicitly.

### Finance

#### T25 — Nightly reconciliation
**Serves:** M9
**Prompt:** "Prove nightly that `Σ ACCRUAL − Σ REVERSAL − Σ PAYOUT = outstanding liability`; alert with the offending rows on any discrepancy."
**File:** `src/finance/reconciliation.job.ts`
**Details:** ≤ 30 min over 30 M+ rows (§5.1). Alert threshold: any discrepancy > 1 kopiyka. The alert **names the rows** — a number alone is not actionable (E24). Rounding remainders (T12) must be accounted for, not written off.
**Acceptance criteria:** the corrupted-ledger fixture (§8.3) is detected, the offending rows are listed, and the alert reaches finance; the job completes within the window in a load test.

#### T26 — Accrued liability report
**Serves:** M9
**Prompt:** "Produce a monthly accrued-liability report: outstanding confirmed-but-unpaid cashback, by period, reconcilable against the general ledger."
**File:** `src/finance/liability.report.ts`
**Details:** Reported by the accrual's **period label** (T18/E14), not by processing date — otherwise late accruals silently move between accounting periods.
**Acceptance criteria:** a finance reviewer can tie the report to the general ledger export; late accruals appear under their original period.

### Cross-cutting

#### T27 — SLO instrumentation
**Serves:** §5.1
**Prompt:** "Instrument every path in the performance table with metrics and alerts on the stated targets."
**File:** `src/platform/slo.ts`
**Details:** DLQ depth > 0 for > 1 h pages a human — a stuck event is unpaid money (§5.7). Payout-run completion is alerted on **deadline**, not latency.
**Acceptance criteria:** every row of the §5.1 table has a corresponding metric and alert rule; a synthetic breach fires it.

#### T28 — Fixtures and load-test data
**Serves:** verification of M1–M9
**Prompt:** "Build the golden decision set, sequence fixtures, abuse fixtures, and a corrupted-ledger fixture."
**File:** `fixtures/`
**Details:** As enumerated in §8.3. Fixtures are **data, not code** — reviewable by compliance and by the program owner without reading TypeScript.
**Acceptance criteria:** every reason code appears in the golden set; every cap boundary has three cases (under / exactly at / over); the false-positive abuse case is present and passing.

---

## 10. Traceability matrix

| Objective | Tasks |
|---|---|
| **M1** Earn, once, with a reason | T1, T2, T3, T7, T8, T10, T12, T21 |
| **M2** Two-stage visibility | T6, T10, T11 |
| **M3** Caps without races | T9, T10 |
| **M4** Clawback | T2, T13, T14, T15 |
| **M5** Payout | T2, T16, T17, T18 |
| **M6** Rule versioning | T4, T5 |
| **M7** Audit, adjustment, explainability | T2, T5, T21, T22, T23, T24 |
| **M8** Abuse controls | T14, T19, T20 |
| **M9** Finance reconciliation | T2, T12, T18, T25, T26 |
| **Non-functional** (§5) | T1 (§5.3), T23 (§5.5), T24 (§5.6), T27 (§5.1) |
| **All objectives** | T28 — fixtures underpin the verification of M1–M9, so it is listed once here rather than repeated in every row |

Every task traces to at least one objective; every objective is served by at least two tasks. A task that cannot name its objective does not belong in this spec.

**This matrix is generated from the `Serves:` line of each task in §9 — it does not restate them.** If the two ever disagree, the task is right and the matrix is stale: the matrix is a view, not a second source of truth. Any task added to §9 without a `Serves:` line is incomplete and must not be implemented.
