# Transaction Processing Pipeline — Specification

> Ingest the information from this file, implement the Low-Level Tasks, and generate the code that
> will satisfy the High- and Mid-Level Objectives.

**Project**: Homework 6 capstone — AI-powered transaction processing pipeline
**Author**: Andrii Shukailo ([@overgapo](https://github.com/overgapo))
**Status**: Specification frozen before any pipeline code is written (Task 1 / Agent 1)
**Companion documents**: [`agents.md`](./agents.md) (agent behaviour contract), [`research-notes.md`](./research-notes.md) (context7 queries), [`HOWTORUN.md`](./HOWTORUN.md)

---

## 1. High-Level Objective

Build a file-based, four-stage transaction processing pipeline that ingests raw payment records from
`sample-transactions.json`, and validates, risk-scores, compliance-screens and settles each one into
an auditable final outcome in `shared/results/`, with a web dashboard, a queryable MCP server, and a
push-blocking coverage gate around it.

---

## 2. Stakeholders

| Stakeholder | What they need from the system | Where it shows up |
|---|---|---|
| **Payment operations** | To see, per run, what settled, what was held, and what was rejected — without reading JSON by hand | Front-end dashboard (§8.6), run summary (§8.5) |
| **Fraud analyst** | A risk score with the *signals that produced it*, not just a number | `risk.signals[]` on every scored record (§7.2) |
| **Compliance officer** | An immutable audit trail with no plaintext account numbers, and a filing record for reportable transactions | `shared/logs/audit.log` (§6.4), `compliance.filings[]` (§7.3) |
| **Support** | To answer "what happened to TXN003?" in one call | MCP tool `get_transaction_status` (§8.7) |
| **Reviewer (course)** | Reproducible run, ≥ 80 % coverage gate, documented AI workflow | §10, §11, `README.md` |

---

## 3. Mid-Level Objectives

Five concrete, testable requirements. Each is traced to a Low-Level Task in §10.

1. **Every input record reaches a terminal outcome.** All 8 transactions in `sample-transactions.json`
   produce exactly one file in `shared/results/` with `final_status ∈ {settled, held, rejected}` — no
   record is silently dropped, and the count of result files equals the count of input records.
2. **Malformed records are rejected with a machine-readable reason and never scored.** A transaction
   with an unsupported currency (`TXN006`, `XYZ`) or a non-positive amount (`TXN007`, `-100.00`) exits
   at the validator with a `reason_code` from the closed set in §7.1 and never reaches fraud detection.
3. **Transactions at or above the 10 000 USD reporting threshold are flagged with a risk score and a
   signal list, and those scoring ≥ 60 are held rather than settled.** `TXN005` (75 000 USD) is
   `held` with `HIGH_VALUE` + `VERY_HIGH_VALUE`; `TXN002` (25 000 USD) is scored `MEDIUM` and settles
   with a currency-transaction filing attached.
4. **Money is exact and auditable end to end.** All amounts are `decimal.Decimal` from parse to
   result, FX conversion and fee calculation use `ROUND_HALF_UP` to the target currency's ISO 4217
   exponent, and no `float` appears anywhere in the money path (enforced by a test, §11.3).
5. **Every stage transition is logged with an ISO 8601 UTC timestamp, stage name, transaction ID and
   outcome — and no PII.** Account numbers appear in logs only as `acct_<sha256[:12]>`; names,
   descriptions and raw payloads are never logged (enforced by a test, §11.3).

---

## 4. Implementation Notes

Guardrails. These are constraints on *how* the code is written, not features.

**Money**
- Monetary values are `decimal.Decimal`, constructed **from the string** in the source record
  (`Decimal("1500.00")`), never via `float`. `Decimal(1500.00)` is also a defect — it launders a
  float through the constructor.
- Rounding is **`ROUND_HALF_UP`, applied once**, at the point a value becomes an output amount
  (converted amount, fee, net). Never round an intermediate and then round again.
- Amount scale must match the currency's ISO 4217 minor-unit exponent: 2 for USD/EUR/GBP, **0 for
  JPY**. `"1000.5" JPY` is invalid input, not a value to be rounded.
- Serialization to JSON uses `str(Decimal)`, never `float(Decimal)`. Deserialization goes straight
  back to `Decimal`.

**Currency**
- ISO 4217 alphabetic codes only, from the supported set in §6.3. An unknown code is a rejection, not
  a pass-through.

**Time**
- All timestamps are ISO 8601 with an explicit offset, normalized to UTC (`...Z`) on write.
- The "unusual hour" fraud signal is evaluated against the transaction's **UTC** hour (§7.2). The spec
  does not model local time zones; if that changes, it changes here first.

**PII and logging**
- `source_account`, `destination_account` and `description` are sensitive. Logs and audit records
  carry `acct_<sha256 hex[:12]>` for accounts and **omit** description entirely.
- There is no debug flag, environment variable, or "local only" branch that logs a raw account number
  or a raw record. Do not add one.

**Pipeline mechanics**
- Stages communicate **only** through JSON files in `shared/` (§6.1). A stage never imports another
  stage's internals or calls it directly.
- Each stage is a pure decision function (`validate_transaction`, `score_transaction`,
  `screen_transaction`, `settle_transaction`) wrapped by a thin `process_transaction(record) -> dict`
  that does the envelope bookkeeping. The decision functions take data and return data: no I/O, no
  clock, no randomness — that is what makes them testable and replayable.
- The wall clock is injected (`now: datetime | None = None`) so tests are deterministic.

**Dependencies**
- Standard library for the pipeline core (`decimal`, `json`, `hashlib`, `datetime`, `pathlib`, `uuid`).
- `fastapi` + `uvicorn` for the front-end, `fastmcp` for the MCP server, `pytest` + `pytest-cov` for
  tests. Nothing else without a note in `research-notes.md`.

**Style**
- Type hints on every public function. Comments explain *why a rule exists* (`# 9 000–9 999.99 sits
  just under the CTR threshold — classic structuring shape`), never what the line does.
- Reason codes and signal codes are **closed sets** (§7). Adding one is a change to this spec.

---

## 5. Context

### 5.1 Beginning context

Files that exist before any implementation work:

```
homework-6/
├── TASKS.md                     # assignment brief (given)
├── sample-transactions.json     # 8 raw transaction records (given)
├── specification.md             # this file (Agent 1 output)
├── agents.md                    # agent behaviour contract (Agent 1 output)
└── .claude/commands/write-spec.md   # the skill that generates this kind of spec
```

The input data deliberately contains edge cases: two transactions above the reporting threshold
(`TXN002`, `TXN005`), one just below it (`TXN003`, 9 999.99), one at 02:47 UTC from an unattended API
channel in another country (`TXN004`), one with an unassigned currency code (`TXN006`, `XYZ`), and one
with a negative amount (`TXN007`). Every one of these must have a defined outcome (§9).

### 5.2 Ending context

```
homework-6/
├── orchestrator.py              # run-all entry point
├── pipeline/
│   ├── __init__.py
│   ├── config.py                # thresholds, supported currencies, FX rates, watchlist
│   ├── models.py                # envelope build/parse, Decimal <-> JSON helpers
│   ├── audit.py                 # audit logger + PII hashing
│   ├── validator.py             # stage 1
│   ├── fraud_detector.py        # stage 2
│   ├── compliance.py            # stage 3
│   ├── settlement.py            # stage 4
│   └── reporting.py             # run summary builder
├── frontend/
│   ├── app.py                   # FastAPI: serves dashboard + /api/*, triggers a run
│   └── static/index.html        # single-page dashboard (no build step)
├── mcp/server.py                # FastMCP: get_transaction_status, list_pipeline_results, pipeline://summary
├── mcp.json                     # context7 + pipeline-status
├── tests/                       # unit tests per stage + integration test, >= 90% coverage
├── shared/                      # runtime artifacts (gitignored except .gitkeep)
│   ├── input/ processing/ output/ results/ logs/
├── .claude/
│   ├── commands/{write-spec,run-pipeline,validate-transactions}.md
│   └── settings.json            # coverage gate hook (blocks push below 80%)
├── research-notes.md  README.md  HOWTORUN.md
└── docs/presentation.pdf  docs/screenshots/*.png
```

Expected end state after `python orchestrator.py`:

- 8 files in `shared/results/` plus `shared/results/summary.json`
- 4 settled, 2 held, 2 rejected (§9)
- `shared/logs/audit.log` with one JSON line per stage transition, no plaintext accounts
- `pytest --cov=pipeline` reports **≥ 90 %** line coverage; the push hook fails below **80 %**

---

## 6. Architecture

### 6.1 File-based stage protocol

```
sample-transactions.json
        │  orchestrator: split into one envelope per transaction
        ▼
   shared/input/ ──▶ [validator] ──▶ shared/output/ ──▶ [fraud_detector] ──▶ shared/output/
                          │                                    │
                          └── rejected ──────────┐             ├──▶ [compliance] ──▶ [settlement]
                                                 ▼             │                          │
                                          shared/results/ ◀────┴──────────────────────────┘
```

- A stage **claims** a record by moving it from its inbox into `shared/processing/` (so a crash leaves
  evidence of what was in flight), writes its result to `shared/output/`, and deletes the processing
  copy on success.
- A **terminal** outcome (`rejected`, `held`, `settled`) is written to `shared/results/<transaction_id>.json`
  and does not continue down the chain.
- Every write is atomic: write `<name>.json.tmp`, `os.replace()` onto the final name. A half-written
  JSON file must never be visible to the next stage.

### 6.2 Message envelope

Exactly the format given in the brief:

```json
{
  "message_id": "uuid4-string",
  "timestamp": "2026-03-16T10:00:00Z",
  "source_stage": "validator",
  "target_stage": "fraud_detector",
  "message_type": "transaction",
  "data": {
    "transaction_id": "TXN001",
    "amount": "1500.00",
    "currency": "USD",
    "status": "validated"
  }
}
```

- `message_id` is a fresh uuid4 per hop; `correlation_id` (added to `data`) is stable for the life of
  the transaction and is what ties the audit trail together.
- `data` accumulates: the validator adds `status` and `normalized`, the fraud detector adds `risk`,
  compliance adds `compliance`, settlement adds `settlement` and `final_status`.
- `data.amount` is always a **decimal string**, never a JSON number.

### 6.3 Configuration constants (`pipeline/config.py`)

| Constant | Value | Rationale |
|---|---|---|
| `SETTLEMENT_CURRENCY` | `USD` | Single settlement ledger |
| `HOME_COUNTRY` | `US` | Anything else is cross-border |
| `SUPPORTED_CURRENCIES` | `USD, EUR, GBP, JPY, CHF, CAD, AUD, PLN, UAH` with exponents (`JPY: 0`, rest `2`) | ISO 4217 subset; unknown code = rejection |
| `REPORTING_THRESHOLD` | `Decimal("10000.00")` USD-equivalent | Currency-transaction filing trigger |
| `STRUCTURING_BAND` | `[9000.00, 10000.00)` USD-equivalent | Amounts parked just under the threshold |
| `UNUSUAL_HOURS_UTC` | `00:00–04:59` | Off-hours signal |
| `HIGH_RISK_HOLD_SCORE` | `60` | At or above this, hold instead of settle |
| `FX_RATES` | static table to USD (`EUR: 1.0850`, `GBP: 1.2700`, `JPY: 0.0067`, …) | No network call in a homework pipeline; rates are config, and the table is versioned via `FX_RATES_VERSION` so a settlement can be reconstructed |
| `WATCHLIST_ACCOUNTS` | `{"ACC-9999"}` | Sanctions/watchlist stand-in |
| `FEE_RATE` | `Decimal("0.0025")` (25 bps) | Settlement fee |
| `FEE_MIN` / `FEE_MAX` | `0.50` / `25.00` USD | Floor and cap |
| `MAX_AMOUNT` | `Decimal("1000000000")` | Sanity bound |

### 6.4 Audit trail (`pipeline/audit.py`)

One JSON line per stage transition appended to `shared/logs/audit.log`:

```json
{"ts":"2026-03-16T10:00:03Z","stage":"fraud_detector","transaction_id":"TXN005",
 "correlation_id":"…","outcome":"held","reason_code":"HIGH_RISK","risk_score":60,
 "source_account":"acct_9f2b1c4ae0d3"}
```

Rules: accounts hashed (`sha256(account)[:12]`, prefixed `acct_`), `description` never present, amounts
allowed (they are not PII), append-only — the pipeline never rewrites a line.

---

## 7. Stage decision rules

### 7.1 Stage 1 — Validation (`pipeline/validator.py`)

Checks, in order; **first failure wins** and the record is rejected immediately.

| # | Check | Reason code |
|---|---|---|
| 1 | All of `transaction_id, timestamp, source_account, destination_account, amount, currency, transaction_type` present and non-empty | `MISSING_FIELD` |
| 2 | `timestamp` parses as ISO 8601 with offset | `INVALID_TIMESTAMP` |
| 3 | Accounts match `^ACC-\d{4}$` | `INVALID_ACCOUNT_FORMAT` |
| 4 | `source_account != destination_account` | `SAME_ACCOUNT` |
| 5 | `currency` in `SUPPORTED_CURRENCIES` | `UNSUPPORTED_CURRENCY` |
| 6 | `amount` parses as `Decimal` (string input, finite, not NaN/Inf) | `MALFORMED_AMOUNT` |
| 7 | `amount > 0` | `NON_POSITIVE_AMOUNT` |
| 8 | Decimal places ≤ currency exponent | `AMOUNT_SCALE_MISMATCH` |
| 9 | `amount <= MAX_AMOUNT` | `AMOUNT_OUT_OF_RANGE` |
| 10 | `transaction_type` in `{transfer, wire_transfer, payment, refund, payout}` | `UNSUPPORTED_TRANSACTION_TYPE` |

**Design decision — refunds.** A refund is a positive amount with `transaction_type="refund"`; a
negative amount is a malformed producer payload, not a direction indicator. `TXN007` is therefore
rejected with `NON_POSITIVE_AMOUNT`. This is a policy choice and is stated here so nobody "fixes" it
downstream by taking `abs()`.

On pass, the validator writes `status: "validated"` and a `normalized` block (UTC timestamp, upper-cased
currency, canonicalized amount at the currency's exponent, `usd_equivalent`).

### 7.2 Stage 2 — Fraud detection (`pipeline/fraud_detector.py`)

Additive scoring over the closed signal set. Score is capped at 100.

| Signal | Condition | Points |
|---|---|---|
| `HIGH_VALUE` | `usd_equivalent >= 10 000` | 40 |
| `VERY_HIGH_VALUE` | `usd_equivalent >= 50 000` (in addition to `HIGH_VALUE`) | 20 |
| `STRUCTURING` | `9 000 <= usd_equivalent < 10 000` — parked just under the reporting threshold | 25 |
| `UNUSUAL_HOUR` | UTC hour in `00:00–04:59` | 20 |
| `CROSS_BORDER` | `metadata.country != "US"` | 15 |
| `UNATTENDED_CHANNEL` | `metadata.channel == "api"` | 10 |

Bands: **LOW** `0–24`, **MEDIUM** `25–59`, **HIGH** `60–100`.

`HIGH` → terminal `held` with `reason_code: HIGH_RISK`, written to `shared/results/`, never settled.
`LOW`/`MEDIUM` → continue to compliance with the full `risk` block attached (`score`, `band`,
`signals[]`) so the decision is explainable after the fact.

### 7.3 Stage 3 — Compliance screening (`pipeline/compliance.py`)

1. **Watchlist screening.** If `source_account` or `destination_account` ∈ `WATCHLIST_ACCOUNTS` →
   terminal `held`, `reason_code: WATCHLIST_MATCH`. Screening happens on the account identifier; the
   audit record carries the hash, not the account.
2. **Currency-transaction filing.** If `usd_equivalent >= REPORTING_THRESHOLD` → append
   `{"type": "CTR", "threshold": "10000.00", "filed_at": …}` to `compliance.filings[]`. This does not
   block settlement — it is a record-keeping obligation, and conflating the two is exactly the bug
   this note exists to prevent.
3. **Structuring referral.** If the fraud stage raised `STRUCTURING`, append
   `{"type": "STRUCTURING_REFERRAL", …}` to `filings[]` and continue.

Output: `compliance: {"cleared": bool, "filings": [...], "screened_at": …}`.

### 7.4 Stage 4 — Settlement (`pipeline/settlement.py`)

1. Convert to `SETTLEMENT_CURRENCY` using `FX_RATES` — `gross = round_half_up(amount * rate, 2)`;
   rate `1` and no conversion when already USD. Record `fx: {rate, version, source_currency}`.
2. `fee = clamp(round_half_up(gross * 0.0025, 2), 0.50, 25.00)`.
3. `net = gross - fee`.
4. Terminal `settled`, `reason_code: SETTLED`, written to `shared/results/`.

Rounding happens exactly twice — once on `gross`, once on `fee` — and never on `net`, which is an exact
subtraction of two already-rounded values.

### 7.5 Reporting (`pipeline/reporting.py`)

Aggregates `shared/results/*.json` (excluding `summary.json`) into `shared/results/summary.json`:

```json
{"run_id":"…","started_at":"…","finished_at":"…","total":8,
 "by_status":{"settled":4,"held":2,"rejected":2},
 "totals":{"settled_gross_usd":"…","fees_usd":"…","net_usd":"…"},
 "rejections":[{"transaction_id":"TXN006","reason_code":"UNSUPPORTED_CURRENCY","detail":"…"}],
 "holds":[{"transaction_id":"TXN005","reason_code":"HIGH_RISK","risk_score":60}]}
```

---

## 8. Interfaces

- **8.5 Orchestrator** — `python orchestrator.py [--input sample-transactions.json] [--clean]`:
  prepares `shared/`, fans records into `shared/input/`, runs the four stages in order, writes the
  summary, prints a formatted table, exits `0` when every input reached a terminal state and `1`
  otherwise (a stuck record is a failure, not a warning).
- **8.6 Front-end** — FastAPI on `:8000`: `GET /` serves the dashboard, `GET /api/results`,
  `GET /api/summary`, `POST /api/run` triggers a pipeline run. The dashboard shows counts by status,
  a per-transaction table (ID, amount, currency, status, risk score, reason), and colour-coded rows.
  No build step, no framework bundle — one HTML file with `fetch()`.
- **8.7 MCP server** — `mcp/server.py` (FastMCP): tool `get_transaction_status(transaction_id: str)`,
  tool `list_pipeline_results()`, resource `pipeline://summary`. Read-only: the MCP server never
  mutates `shared/`.

---

## 9. Expected outcomes for the sample data

This table is an **acceptance fixture**. The integration test asserts it row by row.

| TXN | Amount | Stage that decides | Outcome | Signals / reason |
|---|---|---|---|---|
| TXN001 | 1 500.00 USD | settlement | `settled` | risk 0 (LOW) |
| TXN002 | 25 000.00 USD | settlement | `settled` | risk 40 (MEDIUM) `HIGH_VALUE`; CTR filed |
| TXN003 | 9 999.99 USD → ACC-9999 | compliance | `held` | `WATCHLIST_MATCH`; risk 25 `STRUCTURING` |
| TXN004 | 500.00 EUR, 02:47, DE, api | settlement | `settled` | risk 45 (MEDIUM) `UNUSUAL_HOUR`+`CROSS_BORDER`+`UNATTENDED_CHANNEL`; FX applied |
| TXN005 | 75 000.00 USD | fraud_detector | `held` | risk 60 (HIGH) `HIGH_VALUE`+`VERY_HIGH_VALUE` |
| TXN006 | 200.00 **XYZ** | validator | `rejected` | `UNSUPPORTED_CURRENCY` |
| TXN007 | **-100.00** GBP | validator | `rejected` | `NON_POSITIVE_AMOUNT` |
| TXN008 | 3 200.00 USD | settlement | `settled` | risk 0 (LOW) |

Totals: **4 settled, 2 held, 2 rejected, 8 results**.

Settlement arithmetic the tests pin exactly: `TXN001` fee 3.75 / net 1 496.25 · `TXN002` fee
**25.00 (cap reached** — 25 bps of 25 000 is 62.50, clamped by `FEE_MAX`) / net 24 975.00 ·
`TXN004` gross 542.50 (500.00 EUR @ 1.0850) / fee 1.36 (1.35625 → `ROUND_HALF_UP`) / net 541.14 ·
`TXN008` fee 8.00 / net 3 192.00.

### 9.1 Failure modes the implementation must handle

| Situation | Required behaviour |
|---|---|
| A record is unreadable / not JSON | Move to `shared/results/` as `rejected` with `MALFORMED_RECORD`; never crash the run |
| A stage raises unexpectedly | Catch at the stage boundary, write terminal `rejected` with `STAGE_ERROR`, log the exception type — never the payload |
| `shared/` already has files from a previous run | `--clean` wipes it; without `--clean`, refuse to start if `shared/input/` is non-empty rather than mixing runs |
| Duplicate `transaction_id` in the input | Second occurrence is `rejected` with `DUPLICATE_TRANSACTION_ID` — a result file is never overwritten |
| Currency has no FX rate but passed validation | `held` with `FX_RATE_UNAVAILABLE`. Never substitute a default rate: a lagging settlement is an inconvenience, a guessed rate is a monetary error |
| Amount is a JSON number rather than a string | Accept it, but convert via `Decimal(str(value))` and raise `AMOUNT_SCALE_MISMATCH` if precision was already lost |

---

## 10. Low-Level Tasks

Ordered. Each is a single prompt handed to the code-generation agent (Agent 2) or the test agent
(Agent 3). Format is the one required by the brief.

---

**Task: Shared foundation (config, envelope, audit)**
Prompt: "Create `pipeline/config.py` with the constants in §6.3 of specification.md (settlement currency, home country, ISO 4217 supported-currency map with minor-unit exponents, reporting threshold, structuring band, unusual-hours window, hold score, versioned FX rate table, watchlist, fee rate/floor/cap, max amount) — all monetary constants as `decimal.Decimal` built from strings. Then create `pipeline/models.py` with `build_envelope`, `next_envelope`, `load_record`, `write_record_atomic`, `to_decimal`, `quantize_half_up`, and `decimal_to_str`, matching the envelope in §6.2; JSON amounts must round-trip as decimal strings, never floats. Then create `pipeline/audit.py` with `hash_account` (sha256 hex, first 12 chars, `acct_` prefix) and `log_event(stage, transaction_id, correlation_id, outcome, **fields)` appending one JSON line to `shared/logs/audit.log` with an ISO 8601 UTC timestamp; it must refuse to serialize a `description` field."
File to CREATE: `pipeline/config.py`, `pipeline/models.py`, `pipeline/audit.py`
Function to CREATE: `to_decimal(value) -> Decimal`, `quantize_half_up(value: Decimal, exponent: int) -> Decimal`, `write_record_atomic(path: Path, record: dict) -> None`, `hash_account(account: str) -> str`, `log_event(...) -> None`
Details: All money as `Decimal` from strings; atomic writes via `.tmp` + `os.replace`; audit lines are append-only and PII-free; no module here imports a stage module.

---

**Task: Validation Stage**
Prompt: "Create `pipeline/validator.py` implementing the ten ordered checks in §7.1 of specification.md with first-failure-wins semantics and the exact reason codes given. Expose a pure `validate_transaction(data: dict) -> tuple[bool, str | None, dict]` and a `process_transaction(record: dict) -> dict` that wraps it in the envelope protocol: pass → `status='validated'` plus a `normalized` block (UTC timestamp, upper-cased currency, amount quantized to the currency exponent, `usd_equivalent` via the config FX table), target stage `fraud_detector`; fail → terminal `rejected` record with the reason code, written to `shared/results/`. Support `--dry-run` on the command line: read `sample-transactions.json`, validate every record without writing to `shared/`, and print a table of total/valid/invalid with reasons. Negative amounts are rejected, never `abs()`-ed."
File to CREATE: `pipeline/validator.py`
Function to CREATE: `process_transaction(record: dict) -> dict`
Details: Serves Mid-Level Objectives 1, 2, 4. `TXN006` → `UNSUPPORTED_CURRENCY`, `TXN007` → `NON_POSITIVE_AMOUNT`. The `--dry-run` mode is what `/validate-transactions` calls.

---

**Task: Fraud Detection Stage**
Prompt: "Create `pipeline/fraud_detector.py` implementing the additive scoring table in §7.2 of specification.md. Expose a pure `score_transaction(normalized: dict, metadata: dict) -> dict` returning `{'score': int, 'band': str, 'signals': [...]}` with the score capped at 100 and signals in table order, and a `process_transaction(record: dict) -> dict` that attaches the risk block and routes: band HIGH (score ≥ 60) → terminal `held` with `reason_code='HIGH_RISK'` in `shared/results/`; otherwise → `compliance`. The unusual-hour check uses the UTC hour of the normalized timestamp. Accept an injectable `now` parameter so tests are deterministic."
File to CREATE: `pipeline/fraud_detector.py`
Function to CREATE: `process_transaction(record: dict) -> dict`
Details: Serves Mid-Level Objective 3. `TXN005` → 60 → `held`; `TXN004` → 45 (`UNUSUAL_HOUR`+`CROSS_BORDER`+`UNATTENDED_CHANNEL`); `TXN003` → 25 (`STRUCTURING`). A score with an empty `signals[]` is a bug — the score must always be explainable.

---

**Task: Compliance Check Stage**
Prompt: "Create `pipeline/compliance.py` implementing §7.3 of specification.md: watchlist screening on both accounts (match → terminal `held`, `reason_code='WATCHLIST_MATCH'`), a `CTR` filing appended when `usd_equivalent >= 10000` **without** blocking settlement, and a `STRUCTURING_REFERRAL` filing when the fraud stage raised `STRUCTURING`. Expose a pure `screen_transaction(data: dict) -> dict` and `process_transaction(record: dict) -> dict`. Audit entries must contain hashed accounts only."
File to CREATE: `pipeline/compliance.py`
Function to CREATE: `process_transaction(record: dict) -> dict`
Details: Serves Mid-Level Objectives 1, 5. `TXN003` → `held` (`WATCHLIST_MATCH` on `ACC-9999`); `TXN002` and `TXN005` produce CTR filings. Filing ≠ blocking: a CTR is record-keeping, and treating it as a hold is a defect.

---

**Task: Settlement Processing Stage**
Prompt: "Create `pipeline/settlement.py` implementing §7.4 of specification.md: FX-convert to USD using the versioned rate table with `ROUND_HALF_UP` to two places, compute a 25 bps fee clamped to [0.50, 25.00], and `net = gross - fee` with no third rounding. Expose a pure `settle_transaction(data: dict) -> dict` and `process_transaction(record: dict) -> dict` writing the terminal `settled` record to `shared/results/`. A currency with no rate in the table is `held` with `FX_RATE_UNAVAILABLE` — never fall back to a default rate. Record the rate and `FX_RATES_VERSION` on the result so the arithmetic can be reconstructed."
File to CREATE: `pipeline/settlement.py`
Function to CREATE: `process_transaction(record: dict) -> dict`
Details: Serves Mid-Level Objective 4. `TXN004` (500.00 EUR @ 1.0850) → gross 542.50, fee 1.36, net 541.14. No `float` anywhere; a property test asserts `gross == net + fee` exactly.

---

**Task: Reporting and Orchestration**
Prompt: "Create `pipeline/reporting.py` with `build_summary(results_dir: Path) -> dict` producing the summary in §7.5 (counts by status, USD totals, rejection and hold lists), and `orchestrator.py` which prepares `shared/`, loads `sample-transactions.json`, writes one envelope per record to `shared/input/`, runs validator → fraud_detector → compliance → settlement in order, writes `shared/results/summary.json`, prints a formatted table, and exits non-zero if any input record failed to reach a terminal state. Support `--input` and `--clean`; without `--clean`, refuse to start when `shared/input/` is non-empty."
File to CREATE: `pipeline/reporting.py`, `orchestrator.py`
Function to CREATE: `build_summary(results_dir: Path) -> dict`, `run_pipeline(input_path: Path, shared_root: Path, clean: bool = False) -> dict`
Details: Serves Mid-Level Objective 1. `run_pipeline` takes `shared_root` so the integration test can point it at `tmp_path` instead of the real `shared/`.

---

**Task: Front-end dashboard**
Prompt: "Create `frontend/app.py` (FastAPI) serving `frontend/static/index.html` at `/`, plus `GET /api/results`, `GET /api/summary` and `POST /api/run` which invokes `run_pipeline`. Create the dashboard as a single HTML file with inline CSS and vanilla `fetch()`: status counts, a per-transaction table (ID, amount, currency, final status, risk score, reason code), colour-coded rows for settled/held/rejected, and a 'Run pipeline' button. No build step and no CDN dependency."
File to CREATE: `frontend/app.py`, `frontend/static/index.html`
Function to CREATE: `get_results()`, `get_summary()`, `trigger_run()`
Details: Use context7 for the FastAPI static-files and background-task patterns and record the queries in `research-notes.md`. Amounts stay decimal strings across the API boundary — no `float` in a response model.

---

**Task: Custom MCP server**
Prompt: "Create `mcp/server.py` using FastMCP exposing tool `get_transaction_status(transaction_id: str) -> dict` (reads `shared/results/<id>.json`, returns status, reason code, risk score, amounts, or a not-found result), tool `list_pipeline_results() -> dict` (summary of all processed transactions, excluding `summary.json`), and resource `pipeline://summary` returning the latest run summary as text. Read-only. Then create `mcp.json` configuring both `context7` and this `pipeline-status` server."
File to CREATE: `mcp/server.py`, `mcp.json`
Function to CREATE: `get_transaction_status(transaction_id: str) -> dict`, `list_pipeline_results() -> dict`, `pipeline_summary() -> str`
Details: Look up the FastMCP tool/resource decorator API via context7 and document it in `research-notes.md`. No `__init__.py` in `mcp/` — the directory must not shadow the installed `mcp` package.

---

**Task: Test suite and coverage gate**
Prompt: "Create `tests/` with unit tests per stage (validator reason codes including every row of §7.1, fraud scoring bands and signal combinations, compliance filing-vs-hold behaviour, settlement rounding and FX), plus `tests/test_integration.py` running the whole pipeline against `sample-transactions.json` in `tmp_path` and asserting the §9 acceptance table row by row. Add `tests/test_guardrails.py` asserting no `float` in the money path and no plaintext account number in `shared/logs/audit.log`. Configure `pytest-cov` with `fail_under = 80` and add `.claude/settings.json` with a PreToolUse hook that runs the coverage check and blocks `git push` when coverage is below 80 %."
File to CREATE: `tests/test_validator.py`, `tests/test_fraud_detector.py`, `tests/test_compliance.py`, `tests/test_settlement.py`, `tests/test_reporting.py`, `tests/test_integration.py`, `tests/test_guardrails.py`, `pytest.ini`, `.claude/settings.json`
Function to CREATE: pytest test functions + `shared_root` fixture using `tmp_path`
Details: Serves Mid-Level Objectives 1–5 and the §11 coverage requirement. Tests never touch the real `shared/`. Target ≥ 90 % on `pipeline/`; the hook gate is 80 %.

---

## 11. Verification

### 11.1 Definition of done per stage
A stage is done when its acceptance rows in §9 pass **and** its unit tests cover every reason code or
signal it can emit. Code that compiles is not done.

### 11.2 Coverage
- Gate (hook, blocks push): **80 %**
- Target: **≥ 90 %** on `pipeline/`
- Measured with `pytest --cov=pipeline --cov-report=term-missing`

### 11.3 Guardrail tests (assert the absence of things)
- No `float(` and no `Decimal(` applied to a float literal in `pipeline/` (AST scan).
- `shared/logs/audit.log` contains no substring matching `ACC-\d{4}` after a full run.
- No `description` key in any audit line.

These are deliberately tests about what the code *must not* contain. Do not "fix" a failure here by
relaxing the assertion — see [`agents.md`](./agents.md) §8.

---

## 12. Traceability

| Mid-Level Objective | Low-Level Tasks | Verified by |
|---|---|---|
| 1 — every record reaches a terminal outcome | Validation, Fraud, Compliance, Settlement, Reporting/Orchestration | `test_integration.py::test_all_records_terminal`, §9 table |
| 2 — malformed rejected with a reason, never scored | Validation | `test_validator.py` (all §7.1 codes) |
| 3 — threshold flagging, hold at ≥ 60 | Fraud Detection | `test_fraud_detector.py`, `test_integration.py::test_txn005_held` |
| 4 — exact money, `ROUND_HALF_UP`, no float | Shared foundation, Settlement | `test_settlement.py`, `test_guardrails.py::test_no_float_in_money_path` |
| 5 — audit trail with timestamps and no PII | Shared foundation, all stages | `test_guardrails.py::test_audit_log_has_no_plaintext_accounts` |
