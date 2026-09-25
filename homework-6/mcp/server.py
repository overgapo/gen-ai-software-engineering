#!/usr/bin/env python3
"""Custom MCP server: makes a pipeline run queryable.

Read-only by design. It answers questions about what the pipeline already
decided and never mutates ``shared/`` -- a status tool that can change status
is not a status tool.

There is deliberately **no** ``__init__.py`` in this directory: running
``python mcp/server.py`` puts ``mcp/`` on ``sys.path``, and a package named
``mcp`` here would shadow the installed ``mcp`` library that fastmcp imports.

API shape (``@mcp.tool`` bare, ``@mcp.resource`` with a fixed URI, ``run()``
defaulting to stdio) was confirmed against the FastMCP docs via context7 --
see research-notes.md, query 3.

State: none. FastMCP's stdio transport means the client spawns a fresh process
per session, so every call reads ``shared/results/`` from disk. That is also
why this server can never serve a stale answer after a new pipeline run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP  # noqa: E402

from pipeline import config  # noqa: E402
from pipeline.models import load_record  # noqa: E402
from pipeline.reporting import build_summary  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "shared" / "results"
SUMMARY_PATH = RESULTS_DIR / config.SUMMARY_FILENAME

mcp = FastMCP(name="pipeline-status")

# Fields a status answer may carry. Account numbers and the customer
# description live in the result files but are not status -- the same line the
# dashboard API draws (agents.md §5).
_PUBLIC_FIELDS = (
    "transaction_id",
    "final_status",
    "reason_code",
    "detail",
    "amount",
    "currency",
    "risk_score",
    "risk_band",
    "signals",
    "decided_by",
    "settlement",
    "filings",
)


def _latest_summary() -> dict | None:
    """The stored summary, or one rebuilt from the result files."""
    if SUMMARY_PATH.exists():
        return load_record(SUMMARY_PATH)
    if RESULTS_DIR.exists() and any(RESULTS_DIR.glob("*.json")):
        return build_summary(RESULTS_DIR)
    return None


def _project(row: dict) -> dict:
    return {key: row.get(key) for key in _PUBLIC_FIELDS if row.get(key) is not None}


@mcp.tool
def get_transaction_status(transaction_id: str) -> dict:
    """Current pipeline status of one transaction.

    Returns its final status (settled / held / rejected), the reason code, the
    stage that decided it, the risk score with the signals that produced it,
    and the settlement amounts when it settled.
    """
    summary = _latest_summary()
    if summary is None:
        return {
            "found": False,
            "transaction_id": transaction_id,
            "error": "no pipeline run found; run the pipeline first",
        }

    for row in summary.get("transactions", []):
        if row.get("transaction_id") == transaction_id:
            return {"found": True, **_project(row)}

    known = [row.get("transaction_id") for row in summary.get("transactions", [])]
    return {
        "found": False,
        "transaction_id": transaction_id,
        "error": f"{transaction_id} is not in the latest run",
        "known_transaction_ids": known,
    }


@mcp.tool
def list_pipeline_results() -> dict:
    """Summary of every transaction in the latest pipeline run.

    Counts by final status, settlement totals, and one row per transaction with
    its status, reason code and risk score.
    """
    summary = _latest_summary()
    if summary is None:
        return {"total": 0, "error": "no pipeline run found; run the pipeline first"}

    return {
        "run_id": summary.get("run_id"),
        "finished_at": summary.get("finished_at"),
        "total": summary.get("total", 0),
        "complete": summary.get("complete"),
        "by_status": summary.get("by_status", {}),
        "totals": summary.get("totals", {}),
        "transactions": [_project(row) for row in summary.get("transactions", [])],
    }


@mcp.resource("pipeline://summary")
def pipeline_summary() -> str:
    """The latest pipeline run summary as readable text."""
    summary = _latest_summary()
    if summary is None:
        return "No pipeline run found. Run `python orchestrator.py --clean` first."

    counts = summary.get("by_status", {})
    totals = summary.get("totals", {})
    lines = [
        f"Pipeline run {summary.get('run_id') or '(unknown)'}",
        f"Finished: {summary.get('finished_at') or '(unknown)'}",
        f"Total: {summary.get('total', 0)}  "
        f"settled={counts.get('settled', 0)}  "
        f"held={counts.get('held', 0)}  "
        f"rejected={counts.get('rejected', 0)}",
        f"Settled gross {totals.get('settled_gross', '0')} "
        f"{totals.get('settlement_currency', config.SETTLEMENT_CURRENCY)} · "
        f"fees {totals.get('fees', '0')} · net {totals.get('settled_net', '0')}",
        "",
    ]

    for row in summary.get("transactions", []):
        risk = row.get("risk_score")
        risk_text = "" if risk is None else f" risk={risk}"
        signals = ", ".join(row.get("signals") or [])
        lines.append(
            f"{row.get('transaction_id'):<12} {str(row.get('amount') or ''):>12} "
            f"{row.get('currency') or '':<4} {row.get('final_status'):<9} "
            f"{row.get('reason_code') or ''}{risk_text}"
            + (f" [{signals}]" if signals else "")
        )

    if not summary.get("complete", True):
        lines.append("")
        lines.append(
            f"WARNING: incomplete run — {summary.get('expected_total')} accepted, "
            f"{summary.get('total')} reached a terminal state"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
