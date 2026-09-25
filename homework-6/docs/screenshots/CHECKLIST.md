# Screenshot capture checklist

Six screenshots are required. **`frontend.png` is already captured** (real browser, dashboard at
`127.0.0.1:8000` showing all 8 transactions). The other five need your own terminal or Claude Code
window — capture them with `cmd+shift+4`, save into this directory under the exact filename given.

Run everything from `homework-6/`. Take the shots in this order: 1 and 2 leave a completed run behind,
which 5 needs.

---

## 1. `pipeline-run.png` — the pipeline running

```bash
.venv/bin/python orchestrator.py --clean
```

**Frame must show**: the command you typed, the full 8-row table, and the two summary lines
(`total=8  settled=4  held=2  rejected=2` and `settled gross=30242.50 USD  fees=38.11  net=30204.39`).

Make the window tall enough that the command and the last line are both in shot — that is what shows
a reviewer this is one run rather than a stitched-together screenshot.

---

## 2. `test-coverage.png` — coverage at or above the gate

```bash
.venv/bin/python -m pytest
```

**Frame must show**: the per-module coverage table, the `TOTAL … 100%` row, the line
`Required test coverage of 80% reached. Total coverage: 100.00%`, and `231 passed, 6 skipped`.

---

## 3. `skill-run-pipeline.png` — the `/run-pipeline` skill executing

In Claude Code, from `homework-6/`:

```
/run-pipeline
```

**Frame must show**: the typed `/run-pipeline` command **and** Claude's response — the pipeline
output plus the report of what did not settle. Both the invocation and the result need to be visible;
a screenshot of only the output does not show that the skill was what produced it.

---

## 4. `hook-trigger.png` — the coverage gate blocking a push

The gate fires on `git push` and blocks when the suite is red or coverage is under 80 %. Make it fail
on purpose:

```bash
./docs/screenshots/gate_demo.sh break     # adds a temporary failing test
```

Then, in Claude Code, ask it to push (for example: `run git push`). The hook intercepts the Bash call
before anything is sent to the remote — **nothing gets pushed**.

**Frame must show**: `PUSH BLOCKED by the coverage gate (minimum 80%)` and the failing test below it.

Clean up immediately afterwards:

```bash
./docs/screenshots/gate_demo.sh restore
.venv/bin/python -m pytest -q                # confirm 231 passed again
```

> Do not commit `tests/test_zz_gate_demo.py`. If you already did, remove it before opening the PR.

---

## 5. `mcp-interaction.png` — context7 **and** the custom MCP server

Both must be visible — one screenshot showing both calls, or one screenshot scrolled so both fit.

**Prerequisites**: a completed pipeline run (step 1), and a Claude Code **restart** so
`pipeline-status` connects. Check with `/mcp` — both `context7` and `pipeline-status` should show as
connected.

In Claude Code, ask for both in one message, for example:

```
Use context7 to look up how FastMCP registers a resource, then use the
pipeline-status MCP server to get the status of TXN005.
```

**Frame must show**:
- a **context7** call with its result (a library ID such as `/prefecthq/fastmcp` and a doc excerpt)
- a **pipeline-status** tool call with its result — `get_transaction_status("TXN005")` returns
  `held` / `HIGH_RISK` / risk 60 / signals `HIGH_VALUE, VERY_HIGH_VALUE`

`list_pipeline_results()` (8 transactions, 4/2/2) works equally well for the second half.

---

## Already captured

| File | Status |
|---|---|
| `frontend.png` | ✅ Dashboard at `127.0.0.1:8000`, all 8 rows, signal chips, totals line |

Retake it if you prefer your own window — start the server with
`.venv/bin/python -m uvicorn frontend.app:app` and open `http://127.0.0.1:8000`.
