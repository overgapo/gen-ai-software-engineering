# Transaction Processing Pipeline — Homework 6 Capstone

> **Created by Andrii Shukailo** ([@overgapo](https://github.com/overgapo)) · SET University, GenAI Software Engineering

A file-based transaction processing pipeline built end to end by four AI workflow agents: one wrote
the specification, one the code, one the tests and coverage gate, one the documentation. The pipeline
ingests raw payment records, then validates, risk-scores, compliance-screens and settles each one into
an auditable final outcome — with a web dashboard over it, an MCP server that makes a run queryable,
and a push-blocking coverage gate around it.

The interesting part of this project is not that the code works. It is that **every decision is
explainable after the fact**: each transaction carries the signals that produced its risk score, the
FX rate and rate-table version used to settle it, and the stage that decided its fate — and the audit
trail records all of it without ever writing an account number in plaintext.

---

## What it does

Eight sample transactions go in. Four settle, two are held, two are rejected — and each outcome has a
machine-readable reason:

```
TXN                AMOUNT CUR         RISK  REASON
----------------------------------------------------------------------------------------
TXN001            1500.00 USD  OK        0  SETTLED
TXN002           25000.00 USD  OK       40  SETTLED [HIGH_VALUE]
TXN003            9999.99 USD  HOLD     25  WATCHLIST_MATCH [STRUCTURING]
TXN004             500.00 EUR  OK       45  SETTLED [UNUSUAL_HOUR, CROSS_BORDER, UNATTENDED_CHANNEL]
TXN005           75000.00 USD  HOLD     60  HIGH_RISK [HIGH_VALUE, VERY_HIGH_VALUE]
TXN006             200.00 XYZ  REJ          UNSUPPORTED_CURRENCY ('XYZ' is not a supported ISO 4217 code)
TXN007            -100.00 GBP  REJ          NON_POSITIVE_AMOUNT (amount must be greater than zero)
TXN008            3200.00 USD  OK        0  SETTLED
----------------------------------------------------------------------------------------
total=8  settled=4  held=2  rejected=2
settled gross=30242.50 USD  fees=38.11  net=30204.39
```

Three of those rows are worth a second look:

- **TXN003** (9 999.99) sits just under the 10 000 reporting threshold — the classic structuring
  shape — so it is flagged, and separately held because its destination account is watchlisted.
- **TXN004** is a 02:47 UTC cross-border transfer over an unattended API channel: three independent
  signals, none of them individually alarming, adding up to a MEDIUM score that still settles.
- **TXN007** carries `-100.00`. The pipeline rejects it rather than taking `abs()` — a negative
  amount is a malformed producer payload, not a direction indicator.

---

## Architecture

```
                         sample-transactions.json
                                    │
                                    ▼
                           ┌────────────────┐
                           │  orchestrator  │  one envelope per record
                           └────────┬───────┘
                                    ▼
                            shared/input/
                                    │
              ┌─────────────────────▼─────────────────────┐
              │  1. VALIDATOR                             │
              │  10 ordered checks, first failure wins    │──── rejected ──┐
              └─────────────────────┬─────────────────────┘                │
                                    ▼                                      │
              ┌───────────────────────────────────────────┐                │
              │  2. FRAUD DETECTOR                        │                │
              │  additive score 0-100 + signal list       │──── held ──────┤
              └─────────────────────┬─────────────────────┘   (score ≥ 60) │
                                    ▼                                      │
              ┌───────────────────────────────────────────┐                │
              │  3. COMPLIANCE                            │                │
              │  watchlist screen + CTR / structuring     │──── held ──────┤
              └─────────────────────┬─────────────────────┘  (watchlist)   │
                                    ▼                                      │
              ┌───────────────────────────────────────────┐                │
              │  4. SETTLEMENT                            │                │
              │  FX → USD, 25 bps fee, net                │──── settled ───┤
              └───────────────────────────────────────────┘                │
                                                                           ▼
                                                                  shared/results/
                                                                  + summary.json
                                    │                                      │
        shared/logs/audit.log ◀─────┘                                      │
        (one line per transition,          ┌───────────────────────────────┤
         accounts hashed, never plaintext) │                               │
                                           ▼                               ▼
                                  frontend (FastAPI)              mcp/server.py
                                  dashboard + /api/*              tools + pipeline://summary
```

Stages communicate **only through JSON files**. A stage claims a record by moving it into
`shared/processing/`, writes its output atomically (`.tmp` + `os.replace`), and never imports a
sibling stage — a constraint enforced by an AST test, not just by convention.

---

## Pipeline stages

- **Validation** — ten ordered checks with first-failure-wins semantics: required fields, ISO 8601
  timestamp with an explicit offset, account format, same-account, ISO 4217 currency, parseable
  `Decimal` amount, positive amount, decimal scale matching the currency's minor unit (2 for USD,
  **0 for JPY**), range, and transaction type. Emits one of ten closed reason codes.
- **Fraud detection** — additive scoring over six signals (`HIGH_VALUE`, `VERY_HIGH_VALUE`,
  `STRUCTURING`, `UNUSUAL_HOUR`, `CROSS_BORDER`, `UNATTENDED_CHANNEL`), capped at 100, banded
  LOW / MEDIUM / HIGH. A score is never returned alone — the signals that produced it travel with it,
  because a number nobody can explain is not actionable.
- **Compliance** — watchlist screening that *blocks*, and currency-transaction filings that *record*.
  Keeping those apart is the whole point of the stage: holding a transaction because it is reportable
  is as much a defect as skipping the filing because it settled.
- **Settlement** — FX conversion against a **versioned** rate table, a 25 bps fee clamped to
  [0.50, 25.00], and `net = gross − fee`. Rounding happens exactly twice and never on the net, which
  is an exact subtraction of two already-rounded values. A currency with no published rate is held
  with `FX_RATE_UNAVAILABLE` — never settled at a guessed rate.
- **Reporting** — aggregates the terminal records into `shared/results/summary.json` and reconciles:
  if any accepted record failed to reach a terminal state, the run exits non-zero. A stuck
  transaction is money nobody is looking for.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.13 | `decimal.Decimal` in the standard library, and the assignment's reference stack |
| Pipeline core | standard library only (`decimal`, `json`, `hashlib`, `datetime`, `pathlib`, `uuid`) | Nothing in the money path should depend on a package that can change under it |
| Money | `decimal.Decimal`, `ROUND_HALF_UP` | Exact arithmetic; a `float` here is a monetary defect that looks like working code |
| Front-end | FastAPI + uvicorn, one static HTML page | No build step, no bundle, no CDN dependency |
| MCP server | FastMCP 4.0.5 (stdio) | Two tools + one resource, read-only and stateless |
| Docs lookup | context7 MCP | Framework APIs checked against current docs rather than recalled — see `research-notes.md` |
| Tests | pytest + pytest-cov | 231 tests, 100 % coverage on `pipeline/` and `orchestrator.py` |
| Coverage gate | Claude Code `PreToolUse` hook + `.githooks/pre-push` | Blocks `git push` below 80 % |

---

## The four agents

| Agent | Role | Its "plus" | Output |
|---|---|---|---|
| **1 — Specification** | Wrote `specification.md` before any code | **Skill** `/write-spec` | Spec with a §9 acceptance table giving all 8 records a defined outcome |
| **2 — Code generation** | Built the pipeline, dashboard, MCP server | **MCP context7**, 3 documented queries | `pipeline/`, `orchestrator.py`, `frontend/`, `mcp/`, `research-notes.md` |
| **3 — Unit tests** | Wrote the suite and the gate | **Hook** blocking push below 80 % | `tests/`, `.claude/hooks/coverage_gate.py` |
| **4 — Documentation** | Wrote the docs and deck | **Requirement**: author named | `README.md`, `HOWTORUN.md`, `docs/` |

`agents.md` is the behaviour contract all four work under: ownership boundaries, money rules, PII
rules, and the rule that a failing test is never fixed by loosening the assertion.

---

## Guarantees the tests actually enforce

Some tests assert the **absence** of things, which is deliberate — a guarantee that depends on nobody
ever writing a particular line is stronger when a test refuses to let them:

- no `float()` call and no float literal anywhere in `pipeline/` (AST scan)
- no stage module imports a sibling stage (AST scan)
- no `ACC-NNNN` and no `description` in a full run's audit log
- no JSON float in any result file
- `log_event` **raises** rather than writing a line carrying a plaintext account or a description

The coverage gate was verified by breaking things rather than by reading it: 160 untested functions
dropped coverage to 63.64 % and the hook exited 2; one sabotaged assertion did the same; a non-push
Bash command exits 0 without running the suite at all.

---

## Documents

| File | What it holds |
|---|---|
| [`specification.md`](./specification.md) | The frozen spec — objectives, decision rules, §9 acceptance table, low-level tasks |
| [`agents.md`](./agents.md) | Behaviour contract for any AI agent working in this project |
| [`research-notes.md`](./research-notes.md) | The three context7 queries, and what each one changed in the code |
| [`HOWTORUN.md`](./HOWTORUN.md) | Setup → pipeline → front-end → tests → MCP, step by step |
| [`docs/presentation.pdf`](./docs/presentation.pdf) | Capstone deck: architecture, stages, demo, lessons |
| [`docs/screenshots/`](./docs/screenshots/) | Evidence for each step |

---

## Quick start

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python orchestrator.py --clean          # run the pipeline
.venv/bin/python -m uvicorn frontend.app:app      # dashboard at http://127.0.0.1:8000
.venv/bin/python -m pytest                        # 231 tests, coverage gate at 80 %
```

Full instructions, including the MCP servers and the coverage hook, are in
[`HOWTORUN.md`](./HOWTORUN.md).
