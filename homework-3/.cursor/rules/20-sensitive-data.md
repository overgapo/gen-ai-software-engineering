---
description: Card data, PII, logging, audit and retention. Apply when touching consumers, logging, HTTP handlers, or anything that persists or emits data.
globs:
  - "src/ingest/**"
  - "src/ops/**"
  - "src/platform/**"
  - "fixtures/**"
---

# Sensitive data rules

## Card data — the hard line

This service is **outside PCI DSS scope and must stay there**. It receives and stores a `card_token` and `last4`. Nothing else.

- **Never log, persist, forward, or fixture a PAN, CVV, or track data.**
- If an inbound payload contains a PAN, that is a **producer defect**: drop the field, raise an alert, do not persist it, do not put it in the error message, do not put it in the dead-letter payload.
- There is **no debug flag, no local-development exception, and no temporary branch** that enables PAN logging. Do not add one. Do not ask.
- Never log a full inbound card event. Log identifiers — `event_id`, `transaction_id`, correlation ID — not contents.

## PII by association

Merchant name and MCC reveal where a person was and what they bought. Treat them as personal data:

- Not exported to analytics without aggregation.
- Not included in error messages that leave the service.
- Fine to store and to show back to the user who made the purchase — they already know.

## Audit

Every money movement writes an audit record **in the same database transaction**: actor, action, reason, correlation ID, before/after.

- If the audit write fails, **the money movement rolls back**. Never the other way round.
- Audit records are append-only, like the ledger.
- The audit log must be sufficient to reconstruct a money movement **without application logs** — compliance will not have them.

## Segregation of duties

Manual adjustments and rule activations need **two distinct principals** (maker ≠ checker), enforced by a database constraint, not by convention.

- Do not add an admin override, a bypass flag, or a "system principal" that can occupy both roles.
- If a test is awkward because of this, the test needs two principals — the code does not need a back door.
- Every adjustment carries a support case reference. No reference, no money.

## Retention and erasure

- Ledger and audit records are retained **7 years**.
- An erasure request **pseudonymizes identity and retains the financial records** under a legal-obligation basis. It does not delete ledger rows.
- If asked to "implement account deletion", implement pseudonymization, and say why it is not deletion. This conflict is expected, documented, and not yours to resolve by deleting.
