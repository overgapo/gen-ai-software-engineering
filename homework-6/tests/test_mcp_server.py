"""Custom MCP server tests.

The server is loaded by path rather than imported as ``mcp.server``: the
directory is deliberately not a package, because a package named ``mcp`` here
would shadow the installed ``mcp`` library that fastmcp depends on.

Every test points the server at a ``tmp_path`` results directory -- none of
them read the project's real ``shared/``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastmcp import Client

from orchestrator import run_pipeline
from tests.conftest import FIXED_NOW

SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp" / "server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("pipeline_mcp_server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def server(shared_root, sample_input, monkeypatch):
    """Server wired to a fresh run in tmp_path."""
    run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW)
    module = load_server()
    results = shared_root / "results"
    monkeypatch.setattr(module, "RESULTS_DIR", results)
    monkeypatch.setattr(module, "SUMMARY_PATH", results / "summary.json")
    return module


@pytest.fixture
def empty_server(tmp_path, monkeypatch):
    """Server with no run at all -- the cold-start case."""
    module = load_server()
    monkeypatch.setattr(module, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(module, "SUMMARY_PATH", tmp_path / "results" / "summary.json")
    return module


def call_tool(module, name: str, arguments: dict | None = None) -> dict:
    async def go():
        async with Client(module.mcp) as client:
            result = await client.call_tool(name, arguments or {})
            return json.loads(result.content[0].text)

    return asyncio.run(go())


def read_summary_resource(module) -> str:
    async def go():
        async with Client(module.mcp) as client:
            contents = await client.read_resource("pipeline://summary")
            return contents[0].text

    return asyncio.run(go())


def test_both_tools_and_the_resource_are_registered(server):
    async def go():
        async with Client(server.mcp) as client:
            tools = {t.name for t in await client.list_tools()}
            resources = {str(r.uri) for r in await client.list_resources()}
            return tools, resources

    tools, resources = asyncio.run(go())
    assert tools == {"get_transaction_status", "list_pipeline_results"}
    assert resources == {"pipeline://summary"}


def test_get_transaction_status_for_a_settled_transaction(server):
    out = call_tool(server, "get_transaction_status", {"transaction_id": "TXN001"})
    assert out["found"] is True
    assert out["final_status"] == "settled" and out["reason_code"] == "SETTLED"
    assert out["settlement"]["net"] == "1496.25"
    assert out["decided_by"] == "settlement"


def test_get_transaction_status_explains_a_hold(server):
    out = call_tool(server, "get_transaction_status", {"transaction_id": "TXN005"})
    assert out["final_status"] == "held" and out["reason_code"] == "HIGH_RISK"
    assert out["risk_score"] == 60
    assert out["signals"] == ["HIGH_VALUE", "VERY_HIGH_VALUE"]


def test_get_transaction_status_explains_a_rejection(server):
    out = call_tool(server, "get_transaction_status", {"transaction_id": "TXN006"})
    assert out["final_status"] == "rejected"
    assert out["reason_code"] == "UNSUPPORTED_CURRENCY"
    assert "risk_score" not in out  # rejected records are never scored


def test_unknown_transaction_lists_what_is_known(server):
    out = call_tool(server, "get_transaction_status", {"transaction_id": "TXN999"})
    assert out["found"] is False
    assert "not in the latest run" in out["error"]
    assert "TXN001" in out["known_transaction_ids"]


def test_get_transaction_status_without_a_run(empty_server):
    out = call_tool(empty_server, "get_transaction_status", {"transaction_id": "TXN001"})
    assert out["found"] is False and "no pipeline run" in out["error"]


def test_list_pipeline_results(server):
    out = call_tool(server, "list_pipeline_results")
    assert out["total"] == 8 and out["complete"] is True
    assert out["by_status"] == {"settled": 4, "held": 2, "rejected": 2}
    assert out["totals"]["settled_net"] == "30204.39"
    assert len(out["transactions"]) == 8


def test_list_pipeline_results_without_a_run(empty_server):
    out = call_tool(empty_server, "list_pipeline_results")
    assert out["total"] == 0 and "no pipeline run" in out["error"]


@pytest.mark.parametrize("tool", ["get_transaction_status", "list_pipeline_results"])
def test_no_tool_exposes_pii(server, tool):
    args = {"transaction_id": "TXN004"} if tool == "get_transaction_status" else {}
    payload = call_tool(server, tool, args)
    text = json.dumps(payload)

    # No account number and no customer description, anywhere.
    assert not re.search(r"ACC-\d{4}", text)
    assert "Invoice #4471" not in text  # TXN004's description

    # And no row carries the sensitive fields as keys. (The *words* may appear
    # in a reason string -- "watchlist match on destination_account" names the
    # field that matched, which is the useful part, and carries no account.)
    rows = payload.get("transactions") or [payload]
    for row in rows:
        assert not {"source_account", "destination_account", "description"} & set(row)


def test_summary_resource_is_readable_text(server):
    text = read_summary_resource(server)
    assert "settled=4" in text and "held=2" in text and "rejected=2" in text
    assert "TXN003" in text and "WATCHLIST_MATCH" in text
    assert "30204.39" in text
    assert "ACC-" not in text


def test_summary_resource_without_a_run(empty_server):
    assert "No pipeline run found" in read_summary_resource(empty_server)


def test_summary_resource_warns_about_an_incomplete_run(server, shared_root):
    summary_path = shared_root / "results" / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["complete"] = False
    summary["expected_total"] = 9
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    text = read_summary_resource(server)
    assert "WARNING: incomplete run" in text and "9 accepted" in text


def test_summary_is_rebuilt_when_the_summary_file_is_missing(server, shared_root):
    (shared_root / "results" / "summary.json").unlink()
    out = call_tool(server, "list_pipeline_results")
    assert out["total"] == 8  # rebuilt from the result files
