---
description: What "done" means. Test categories required for money-path changes. Apply when writing or changing tests.
globs:
  - "**/*.test.ts"
  - "**/*.spec.ts"
  - "fixtures/**"
---

# Testing rules

**Done means the acceptance criteria in §9 of the spec are met** — not that the code compiles and not that a happy path passes.

## Required test categories

| When the change involves… | You owe… | Because… |
|---|---|---|
| Arithmetic (rounding, proportional reversal, cap truncation) | a **property test** | example tests confirm what you already believed; property tests find the case you did not consider |
| A database constraint (append-only, unique, exclusion, atomic conditional update) | an **integration test against real PostgreSQL** (Testcontainers) | half the guarantees live *in the database*; a mock will let you violate every one of them and stay green |
| Shared mutable state (cap counters, payout idempotency) | a **concurrency test** | "I clicked it twice and it was fine" is not a concurrency test |
| A multi-step process that moves money (the payout run) | a **crash-and-resume test** | kill it mid-run; assert nobody was paid twice and nobody was skipped |
| A fraud rule | a **false-positive fixture** | a suite where every abuse case is caught and no legitimate user is checked will happily ship a rule that freezes half the customer base |

## Fixtures are data, not code

Golden decision cases live in `fixtures/` as plain data so that compliance and the program owner can review them **without reading TypeScript**. Every reason code appears at least once. Every cap boundary has three cases: just under, exactly at, just over.

## Tests that assert absence

Some acceptance criteria assert that code **does not exist** — for example, the clawback module must not import a debit client (spec T15). This is deliberate: a guarantee that relies on nobody ever calling a function is stronger when the function is unreachable.

Do not "fix" such a test by relaxing it.

## Never weaken a test to make it pass

If a test fails, either the code is wrong or the spec is wrong. Both are worth saying out loud. Neither is fixed by loosening an assertion, adding a tolerance to a money comparison, or marking it skipped.

There is no acceptable rounding tolerance in a monetary assertion. The expected value is exact, in minor units, or the test is not testing anything.
