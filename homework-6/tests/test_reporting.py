"""Run-summary tests."""

from __future__ import annotations

import json

from pipeline import config
from pipeline.reporting import build_summary, iter_results
from tests.conftest import FIXED_NOW


def write_result(results_dir, txn_id, **data):
    payload = {
        "message_id": "m",
        "timestamp": "2026-03-16T12:00:00Z",
        "source_stage": data.pop("decided_by", "settlement"),
        "target_stage": config.TERMINAL_TARGET,
        "message_type": "transaction",
        "data": {"transaction_id": txn_id, **data},
    }
    (results_dir / f"{txn_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_empty_results_directory(shared_root):
    summary = build_summary(shared_root / "results")
    assert summary["total"] == 0
    assert summary["by_status"] == {"settled": 0, "held": 0, "rejected": 0}
    assert summary["totals"]["settled_gross"] == "0"


def test_counts_totals_and_lists(shared_root):
    results = shared_root / "results"
    write_result(
        results, "TXN001", final_status="settled", reason_code="SETTLED",
        normalized={"amount": "1500.00", "currency": "USD"},
        settlement={"gross": "1500.00", "fee": "3.75", "net": "1496.25"},
    )
    write_result(
        results, "TXN002", final_status="settled", reason_code="SETTLED",
        normalized={"amount": "500.00", "currency": "EUR"},
        settlement={"gross": "542.50", "fee": "1.36", "net": "541.14"},
        compliance={"filings": [{"type": "CTR"}]},
    )
    write_result(
        results, "TXN005", final_status="held", reason_code="HIGH_RISK",
        risk={"score": 60, "band": "HIGH", "signals": ["HIGH_VALUE"]},
    )
    write_result(
        results, "TXN006", final_status="rejected", reason_code="UNSUPPORTED_CURRENCY",
        detail="'XYZ' is not supported", amount="200.00", currency="XYZ",
    )

    summary = build_summary(results, run_id="r1", started_at="2026-03-16T12:00:00Z")
    assert summary["by_status"] == {"settled": 2, "held": 1, "rejected": 1}
    assert summary["totals"]["settled_gross"] == "2042.50"
    assert summary["totals"]["fees"] == "5.11"
    assert summary["totals"]["settled_net"] == "2037.39"
    assert [r["transaction_id"] for r in summary["rejections"]] == ["TXN006"]
    assert summary["holds"][0]["risk_score"] == 60
    assert summary["transactions"][1]["filings"] == ["CTR"]
    assert summary["run_id"] == "r1"


def test_summary_file_is_not_counted_as_a_result(shared_root):
    results = shared_root / "results"
    write_result(results, "TXN001", final_status="settled", reason_code="SETTLED")
    (results / config.SUMMARY_FILENAME).write_text(json.dumps({"total": 99}), encoding="utf-8")
    assert build_summary(results)["total"] == 1
    assert [r["data"]["transaction_id"] for r in iter_results(results)] == ["TXN001"]


def test_incomplete_run_is_flagged(shared_root):
    results = shared_root / "results"
    write_result(results, "TXN001", final_status="settled", reason_code="SETTLED")
    summary = build_summary(results, expected_total=3)
    assert summary["complete"] is False and summary["expected_total"] == 3


def test_transactions_are_sorted(shared_root):
    results = shared_root / "results"
    for txn in ("TXN003", "TXN001", "TXN002"):
        write_result(results, txn, final_status="rejected", reason_code="MALFORMED_RECORD")
    ids = [row["transaction_id"] for row in build_summary(results)["transactions"]]
    assert ids == ["TXN001", "TXN002", "TXN003"]
