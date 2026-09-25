# `agents.md` — How AI agents must behave in the Transaction Processing Pipeline project

This file governs every AI agent working in `homework-6/` — Claude Code, Cursor, Copilot, or an
autonomous coding agent. It is the behaviour contract that sits alongside
[`specification.md`](./specification.md), which is the *product* contract.

It is not style advice. This pipeline moves money and makes compliance decisions. Most rules below
exist because breaking them produces a **monetary or compliance defect that looks, in a diff, exactly
like ordinary working code** — a `float` where a `Decimal` belonged, an account number in a log line,
a filing treated as a hold.

---

## 1. The prime directive

**`specification.md` is the source of truth. No agent has authority to invent policy about money.**

When the spec is silent on a monetary, privacy, routing or audit question — how to round, whether a
filing blocks settlement, what to do with an unparseable record, what a negative amount means — **stop
and ask**. Do not pick a reasonable-looking default. A blocked task is visible; a wrong rounding mode
is not.

When the spec and existing code disagree, the spec wins and the code is a bug worth reporting.

When you believe the spec itself is wrong, say so and propose the amendment. Changing behaviour
without changing §7 of the spec is how the two drift apart, and after that neither can be trusted.

---

## 2. The four agents and their boundaries

| Agent | Owns | Must not |
|---|---|---|
| **Agent 1 — Specification** | `specification.md`, `agents.md`, `.claude/commands/write-spec.md` | Write pipeline code. The spec is frozen before implementation begins. |
| **Agent 2 — Code generation** | `pipeline/`, `orchestrator.py`, `frontend/`, `mcp/server.py`, `mcp.json`, `research-notes.md` | Write its own tests, or relax a spec rule to make code simpler. Must use context7 for framework lookups and record ≥ 2 queries in `research-notes.md`. |
| **Agent 3 — Unit tests** | `tests/`, `pytest.ini`, `.claude/settings.json` (coverage gate), `.claude/commands/run-pipeline.md`, `.claude/commands/validate-transactions.md` | Edit `pipeline/` to make a test pass. If a test fails, report it — the fix belongs to Agent 2. |
| **Agent 4 — Documentation** | `README.md`, `HOWTORUN.md`, `docs/` | Document behaviour it has not observed. Every command in `HOWTORUN.md` must have been run. |

Cross-boundary edits are allowed only when the owning agent's work is complete and the change is named
explicitly in the commit message.

---

## 3. Stack assumptions

- **Python 3.12**, standard library for the pipeline core (`decimal`, `json`, `hashlib`, `datetime`,
  `pathlib`, `uuid`). Type hints on every public function.
- **FastAPI + uvicorn** for the front-end only. **FastMCP** for the MCP server only. Neither may be
  imported by `pipeline/` — the pipeline runs headless.
- **pytest + pytest-cov** for tests. `fail_under = 80` is the gate; ≥ 90 % is the target.
- New third-party dependencies require a line in `research-notes.md` explaining why the standard
  library was insufficient.

---

## 4. Money rules (non-negotiable)

These restate §4 and §7.4 of the spec. If you are about to write code that contradicts one of these,
you have misunderstood the task.

1. **Money is `decimal.Decimal`, constructed from a string.** Never `float`. `Decimal(1500.00)` is a
   defect too — it launders a float through the constructor. Use `Decimal("1500.00")` or
   `Decimal(str(value))`.
2. **`ROUND_HALF_UP`, applied once**, at the point a value becomes an output amount. Never round an
   intermediate and then round the result again.
3. **Scale follows the currency's ISO 4217 exponent** — 2 for USD/EUR/GBP, **0 for JPY**. An amount
   with more decimal places than its currency allows is invalid input, not a value to be rounded down
   to fit.
4. **JSON carries decimal strings.** `str(Decimal)` on the way out, `Decimal(str(...))` on the way in.
   A JSON number in the money path is a defect even when the test passes.
5. **Never substitute a default FX rate.** A missing rate is `FX_RATE_UNAVAILABLE` and a hold. A
   lagging settlement is an inconvenience; a guessed rate is a monetary error that reconciliation
   finds weeks later.
6. **Never take `abs()` of an amount.** A negative amount is a malformed producer payload
   (`NON_POSITIVE_AMOUNT`), not a direction indicator. Refunds are positive amounts with
   `transaction_type="refund"`.
7. **A filing is not a hold.** A currency-transaction filing is a record-keeping obligation. Blocking
   settlement on it is a defect, and so is skipping the filing because the transaction settled.

---

## 5. Privacy and audit constraints

**Account numbers, names and descriptions are sensitive.**

- Logs and audit records carry `acct_<sha256 hex[:12]>`, never `ACC-1001`.
- `description` never reaches a log line, an audit record, an exception message, or a test fixture
  that gets logged. It is free text a customer typed; treat it as if it contains anything.
- There is **no** debug flag, environment variable, or "just for local development" branch that logs a
  raw record. Do not add one. Do not add one temporarily.
- When a stage fails unexpectedly, log the exception **type** and the transaction ID. Never the
  payload.

**The audit log is append-only.** A correction is a new line, never an edit to an old one. If you find
yourself opening `audit.log` in a mode other than append, stop.

**Every stage transition writes an audit line** — timestamp (ISO 8601 UTC), stage, transaction ID,
correlation ID, outcome. A stage that decides something without leaving a trace has made the decision
unreviewable, which in this domain is the same as not having made it correctly.

---

## 6. Pipeline mechanics

1. **Stages talk through files, never through imports.** `fraud_detector.py` must not import
   `validator.py`. If you need a shared helper, it belongs in `pipeline/models.py`.
2. **Decision functions are pure.** `validate_transaction`, `score_transaction`, `screen_transaction`
   and `settle_transaction` take data and return data — no file I/O, no `datetime.now()`, no
   randomness. The wall clock is injected (`now: datetime | None = None`). This is what makes a
   decision replayable and a test deterministic.
3. **Writes are atomic**: `<name>.json.tmp` then `os.replace()`. A half-written file must never be
   visible to the next stage.
4. **A result file is never overwritten.** A duplicate transaction ID is `DUPLICATE_TRANSACTION_ID`,
   not a silent replacement.
5. **Terminal is terminal.** Once a record lands in `shared/results/`, no later stage touches it.
6. **Nothing writes into the real `shared/` during tests** — use `tmp_path`. A test that pollutes the
   demo state will be discovered during the screenshot run, at the worst possible moment.

---

## 7. Testing expectations

A task is done when its acceptance rows in **§9 of the spec** pass — not when the code compiles.

- **Every reason code and every fraud signal needs a test.** A closed set is only closed if something
  checks that.
- **Rounding needs an exact-value test**, not an approximate one. `assert net == Decimal("541.14")`,
  never `pytest.approx`. `approx` in a money test is a defect in the test.
- **The integration test asserts the §9 table row by row** — status, reason code and risk score for
  all 8 sample transactions. That table is the contract with the reviewer.
- **Some tests assert the absence of code** (§11.3 of the spec): no `float` in the money path, no
  `ACC-\d{4}` in the audit log. These are deliberate. A guarantee that depends on nobody ever writing
  a line is stronger when a test refuses to let them.
- **Never weaken a test to make it pass.** If a test fails, either the code is wrong or the spec is
  wrong. Both are worth saying out loud. Neither is fixed by loosening an assertion or lowering
  `fail_under`.

---

## 8. Default postures for anything not covered

| Situation | Default posture |
|---|---|
| Ambiguous monetary behaviour | **Stop and ask.** Do not pick a default. |
| An unparseable or unexpected record | **Terminal `rejected` with a reason code.** Never silently drop, never crash the run. |
| A missing external fact (FX rate, watchlist) | **Hold and say why.** Never substitute a plausible value. |
| A decision that produces no action | **Emit it with a reason.** "Cleared" is a decision and gets recorded like any other. |
| Something a reviewer might dispute | **Persist the trace** — rate, version, signals, score — so the arithmetic can be reconstructed by hand. |
| A rule that feels inconvenient to implement | It is probably load-bearing. Read the spec section it comes from before working around it. |

---

## 9. When asked to do something this file forbids

Name the rule, say why it exists, and propose the compliant alternative:

> "§4.6 forbids `abs()` on amounts — a negative amount is `NON_POSITIVE_AMOUNT` by spec §7.1. If
> refunds should carry a sign, that is a spec change to §7.1 and I can draft it."

Do not comply quietly. Do not comply with a `# TODO: revisit before production` comment. In this
domain, that comment is how the defect ships.
