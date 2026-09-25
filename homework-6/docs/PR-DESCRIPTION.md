# PR description — ready to paste

> Paste the section below into the pull request body. Where it says
> `<!-- drop image here -->`, drag the PNG from `homework-6/docs/screenshots/` into the GitHub editor —
> GitHub uploads it and replaces the line with a working image URL. Relative repo paths do **not**
> render in a PR body, which is why the images are dropped rather than linked.

---

## Homework 6 — Transaction Processing Pipeline (capstone)

**Created by Andrii Shukailo** ([@overgapo](https://github.com/overgapo))

A four-stage, file-based payment pipeline built end to end by four AI workflow agents. Eight sample
transactions go in; **4 settle, 2 are held, 2 are rejected**, and every outcome carries a
machine-readable reason, the stage that decided it, and — where relevant — the signals and FX rate
version behind it.

📊 **Presentation:** [`homework-6/docs/presentation.pdf`](./homework-6/docs/presentation.pdf) — 9 slides:
architecture, stages, demo, verification, MCP, lessons learned.

---

### Agent 1 — Specification

[`specification.md`](./homework-6/specification.md) · [`agents.md`](./homework-6/agents.md) ·
skill [`/write-spec`](./homework-6/.claude/commands/write-spec.md)

Written and frozen before any pipeline code. Twelve sections including closed sets of reason codes and
fraud signals, a versioned FX/fee config table, and a **§9 acceptance fixture** assigning each of the
8 sample records a defined outcome. Three policy decisions are stated *as decisions* so they are not
quietly "fixed" later: a negative amount is rejected rather than `abs()`-ed, a currency-transaction
filing does not block settlement, and a missing FX rate holds rather than falling back to a default.

### Agent 2 — Pipeline, front-end, MCP server

[`pipeline/`](./homework-6/pipeline) · [`orchestrator.py`](./homework-6/orchestrator.py) ·
[`frontend/`](./homework-6/frontend) · [`research-notes.md`](./homework-6/research-notes.md)

Validation → fraud detection → compliance → settlement, communicating **only through JSON files** in
`shared/`, with atomic writes and an append-only audit log that hashes account numbers. Money is
`decimal.Decimal` with `ROUND_HALF_UP` end to end.

**context7** was used during code generation — three queries documented with library IDs and what each
changed. One of them **corrected code that already worked**: `POST /api/run` used Starlette's
`run_in_threadpool` from an `async def`, hand-rolling what FastAPI does from the function signature.

**Pipeline run**

<!-- drop pipeline-run.png here -->

**Front-end** — dashboard with status counts, per-transaction risk scores, signal chips and
rejection reasons:

![Dashboard](./homework-6/docs/screenshots/frontend.png)
<!-- if the image above does not render, drop frontend.png here instead -->

### Agent 3 — Tests, coverage gate, skills

[`tests/`](./homework-6/tests) · [`.claude/hooks/coverage_gate.py`](./homework-6/.claude/hooks/coverage_gate.py) ·
[`/run-pipeline`](./homework-6/.claude/commands/run-pipeline.md) ·
[`/validate-transactions`](./homework-6/.claude/commands/validate-transactions.md)

**231 tests, 100 % coverage** on `pipeline/` and `orchestrator.py` (gate 80 %, spec target 90 %).
The integration test asserts the §9 acceptance table row by row. Several tests assert the **absence**
of things: no `float()` or float literal in `pipeline/` (AST scan), no stage importing a sibling, no
`ACC-NNNN` or `description` in a run's audit log.

The gate was verified by breaking it, not by reading it: 160 untested functions dropped coverage to
63.64 % → hook exited 2; a sabotaged assertion → exited 2; a non-push command → exited 0 without
running the suite.

**Coverage**

<!-- drop test-coverage.png here -->

**`/run-pipeline` skill executing**

<!-- drop skill-run-pipeline.png here -->

**Coverage gate blocking a push**

<!-- drop hook-trigger.png here -->

### Task 4 — MCP integration

[`mcp.json`](./homework-6/mcp.json) · [`mcp/server.py`](./homework-6/mcp/server.py)

Both servers configured: **context7** (consumed during code generation) and **pipeline-status**
(built here). The custom server exposes `get_transaction_status(transaction_id)`,
`list_pipeline_results()` and the resource `pipeline://summary`. Read-only and stateless — stdio
spawns a fresh process per session, so it can never serve a stale answer after a new run. Verified
over real stdio with a JSON-RPC driver, not just through the client.

**context7 query + custom MCP tool call**

<!-- drop mcp-interaction.png here -->

### Agent 4 — Documentation

[`README.md`](./homework-6/README.md) (author named, ASCII architecture diagram, tech stack table) ·
[`HOWTORUN.md`](./homework-6/HOWTORUN.md) (setup → pipeline → front-end → tests → gate → MCP, every
command verified by running it) · [`docs/presentation.pdf`](./homework-6/docs/presentation.pdf)

---

### Run it

```bash
cd homework-6
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python orchestrator.py --clean          # 4 settled, 2 held, 2 rejected
.venv/bin/python -m uvicorn frontend.app:app      # dashboard on :8000
.venv/bin/python -m pytest                        # 231 tests, gate at 80 %
```

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01Jdpx2NKvJryX8fwE7sr4ti
