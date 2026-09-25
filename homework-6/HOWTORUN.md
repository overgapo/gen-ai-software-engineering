# How to run

Every command below was run from `homework-6/` on macOS with Python 3.13, and the output shown is the
real output. If something behaves differently for you, that is a bug worth reporting — not a step to
skip.

---

## 1. Set up

```bash
cd homework-6
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Python **3.10+** is required (the code uses `X | None` type syntax). The pipeline core itself needs
only the standard library — the dependencies are for the front-end, the MCP server and the tests.

> If your default `python3` is older (mine is 3.9), use an explicit interpreter to create the venv,
> as above. Everything afterwards uses `.venv/bin/python`, so the system Python never matters again.

---

## 2. Run the pipeline

```bash
.venv/bin/python orchestrator.py --clean
```

Expected output:

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

Exit code is `0` only when every accepted record reached a terminal state.

**Flags**

| Flag | Effect |
|---|---|
| `--clean` | Wipe `shared/` contents before running (keeps the committed directory skeleton) |
| `--input <path>` | Use a different input file (default `sample-transactions.json`) |
| `--shared <path>` | Use a different working directory (default `shared/`) |
| `--json` | Print the run summary as JSON instead of the table |

Without `--clean`, the orchestrator **refuses to start** if `shared/input|processing|output` still
holds records — mixing a new run into the leftovers of an old one would make the summary a lie.

**What the run produces**

```
shared/results/TXN001.json … TXN008.json   one terminal record per transaction
shared/results/summary.json                counts, totals, rejections, holds
shared/logs/audit.log                      23 lines, one per stage transition
```

---

## 3. Validate without processing

```bash
.venv/bin/python pipeline/validator.py --dry-run
```

Writes nothing — safe to run against a finished run you do not want to disturb. Exits `1` when any
record is invalid, which is the expected result for `sample-transactions.json` (it deliberately
contains two bad records).

---

## 4. Run the front-end

```bash
.venv/bin/python -m uvicorn frontend.app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. The dashboard shows counts by status, a per-transaction table with
risk scores and signals, and a **Run pipeline** button that re-runs everything and refreshes in place.

| Endpoint | Returns |
|---|---|
| `GET /` | The dashboard |
| `GET /api/results` | Counts, totals and one row per transaction |
| `GET /api/summary` | The full run summary |
| `GET /api/results/{id}` | One transaction, `404` if it is not in the latest run |
| `POST /api/run` | Runs the pipeline (clean) and returns the new summary |

The API returns the **summary projection**, not raw result records: account numbers and customer
descriptions stay server-side.

If no run exists yet, every read endpoint returns `404` with
`"no pipeline run found; run the pipeline first"` — press **Run pipeline** or run step 2.

---

## 5. Run the tests

```bash
.venv/bin/python -m pytest
```

Expected: **232 passed**, coverage **100 %** on `pipeline/` and `orchestrator.py`
(`pytest.ini` fails the run below 80 %).

```bash
.venv/bin/python -m pytest --cov-report=html   # htmlcov/index.html for a browsable report
.venv/bin/python -m pytest tests/test_integration.py -v   # just the §9 acceptance table
```

Tests never touch the real `shared/` — each one gets its own `tmp_path`.

> If a test fails immediately after you restore or switch a file, clear stale bytecode first:
> `find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +`. Python validates
> `.pyc` files by size and mtime, so a same-length edit with an older timestamp can be cached.

---

## 6. The coverage gate

The gate blocks `git push` when the suite fails or coverage drops below **80 %**.

**In Claude Code** it is wired as a `PreToolUse` hook in `.claude/settings.json` and fires on any
Bash command containing `git … push`. Nothing else runs the suite, so normal commands are unaffected.

Try it by hand:

```bash
# allowed — not a push, exits 0 without running anything
echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' | .claude/hooks/coverage_gate.py

# runs the suite, exits 0 when green
echo '{"tool_name":"Bash","tool_input":{"command":"git push"}}' | .claude/hooks/coverage_gate.py
```

**Outside Claude Code**, install the git hook once:

```bash
git config core.hooksPath homework-6/.githooks   # from the repository root
```

The threshold is passed to pytest by the gate itself rather than read from `pytest.ini` — a gate that
can be lowered by editing the file it reads is not a gate.

---

## 7. The MCP servers

`mcp.json` configures both. `.mcp.json` is a symlink to it, which is the filename Claude Code loads.

```bash
claude mcp add context7 -- npx -y @upstash/context7-mcp@latest   # or rely on .mcp.json
```

Restart Claude Code, then `/mcp` should show `context7` and `pipeline-status` connected.

**context7** provides up-to-date library documentation (`resolve-library-id` → `query-docs`). The
three queries made while building this project are written up in
[`research-notes.md`](./research-notes.md).

**pipeline-status** is this project's own server:

| Surface | What it answers |
|---|---|
| `get_transaction_status(transaction_id)` | Final status, reason code, deciding stage, risk score and signals, settlement amounts |
| `list_pipeline_results()` | Counts by status, settlement totals, one row per transaction |
| `pipeline://summary` (resource) | The latest run summary as readable text |

It is read-only and holds no state: stdio spawns a fresh process per session, so every call reads
`shared/results/` from disk and can never serve a stale answer. Run the pipeline (step 2) before
querying it, or every answer will be `"no pipeline run found"`.

Check it without Claude Code:

```bash
.venv/bin/python mcp/server.py    # speaks JSON-RPC on stdin/stdout
```

---

## 8. Regenerate the presentation

```bash
.venv/bin/python docs/build_presentation.py
```

Rebuilds `docs/presentation.pdf` from `docs/presentation.html` using headless Chrome.
