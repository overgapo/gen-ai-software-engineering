"""End-to-end pipeline tests.

The table below is the acceptance fixture from specification.md §9. It is the
contract with the reviewer, so it is asserted row by row rather than summarised
into counts.
"""

from __future__ import annotations

import json

import pytest

import orchestrator
from pipeline import config
from pipeline.audit import audit_path
from pipeline.models import load_record
from orchestrator import PipelineStateError, main, run_pipeline
from tests.conftest import FIXED_NOW

# transaction_id -> (final_status, reason_code, decided_by, risk_score, signals)
ACCEPTANCE = {
    "TXN001": ("settled", "SETTLED", "settlement", 0, []),
    "TXN002": ("settled", "SETTLED", "settlement", 40, ["HIGH_VALUE"]),
    "TXN003": ("held", "WATCHLIST_MATCH", "compliance", 25, ["STRUCTURING"]),
    "TXN004": ("settled", "SETTLED", "settlement", 45,
               ["UNUSUAL_HOUR", "CROSS_BORDER", "UNATTENDED_CHANNEL"]),
    "TXN005": ("held", "HIGH_RISK", "fraud_detector", 60,
               ["HIGH_VALUE", "VERY_HIGH_VALUE"]),
    "TXN006": ("rejected", "UNSUPPORTED_CURRENCY", "validator", None, None),
    "TXN007": ("rejected", "NON_POSITIVE_AMOUNT", "validator", None, None),
    "TXN008": ("settled", "SETTLED", "settlement", 0, []),
}


@pytest.fixture
def completed_run(shared_root, sample_input):
    return run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW), shared_root


@pytest.mark.parametrize("txn_id", sorted(ACCEPTANCE))
def test_acceptance_table_row(completed_run, txn_id):
    _, shared_root = completed_run
    data = load_record(shared_root / "results" / f"{txn_id}.json")["data"]
    status, reason, decided_by, score, signals = ACCEPTANCE[txn_id]
    assert data["final_status"] == status
    assert data["reason_code"] == reason
    assert data["decided_by"] == decided_by
    if score is None:
        assert "risk" not in data  # rejected records are never scored
    else:
        assert data["risk"]["score"] == score
        assert data["risk"]["signals"] == signals


def test_every_record_reaches_a_terminal_state(completed_run):
    summary, shared_root = completed_run
    results = {p.stem for p in (shared_root / "results").glob("*.json")}
    assert results == set(ACCEPTANCE) | {config.SUMMARY_FILENAME.removesuffix(".json")}
    assert summary["total"] == 8 and summary["complete"] is True


def test_status_counts_and_totals(completed_run):
    summary, _ = completed_run
    assert summary["by_status"] == {"settled": 4, "held": 2, "rejected": 2}
    assert summary["totals"]["settled_gross"] == "30242.50"
    assert summary["totals"]["fees"] == "38.11"
    assert summary["totals"]["settled_net"] == "30204.39"


def test_working_directories_drain_empty(completed_run):
    _, shared_root = completed_run
    for sub in ("input", "processing", "output"):
        assert list((shared_root / sub).glob("*.json")) == [], f"{sub} still holds records"


def test_summary_file_is_written(completed_run):
    summary, shared_root = completed_run
    stored = load_record(shared_root / "results" / config.SUMMARY_FILENAME)
    assert stored["by_status"] == summary["by_status"]


def test_ctr_filed_for_reportable_transactions(completed_run):
    _, shared_root = completed_run
    data = load_record(shared_root / "results" / "TXN002.json")["data"]
    assert [f["type"] for f in data["compliance"]["filings"]] == ["CTR"]
    # ...and it did not stop the money moving.
    assert data["final_status"] == "settled"


def test_audit_trail_covers_every_stage_transition(completed_run):
    _, shared_root = completed_run
    lines = [json.loads(line) for line in audit_path(shared_root).read_text().splitlines()]
    assert len(lines) == 23  # 8 validated + 6 scored + 5 screened + 4 settled
    assert {line["stage"] for line in lines} == set(config.STAGE_ORDER)
    for line in lines:
        assert line["ts"].endswith("Z") and line["transaction_id"] and line["correlation_id"]


def test_correlation_id_is_stable_across_stages(completed_run):
    _, shared_root = completed_run
    lines = [json.loads(line) for line in audit_path(shared_root).read_text().splitlines()]
    txn004 = {line["correlation_id"] for line in lines if line["transaction_id"] == "TXN004"}
    assert len(txn004) == 1  # one id across all four stages


def test_duplicate_transaction_id_does_not_overwrite(shared_root, tmp_path):
    raw = json.loads((orchestrator.DEFAULT_INPUT).read_text())
    doubled = tmp_path / "doubled.json"
    doubled.write_text(json.dumps(raw + [raw[0]]), encoding="utf-8")

    summary = run_pipeline(doubled, shared_root, clean=True, now=FIXED_NOW)
    assert summary["total"] == 9 and summary["complete"] is True
    original = load_record(shared_root / "results" / "TXN001.json")["data"]
    assert original["final_status"] == "settled"
    duplicate = next(r for r in summary["transactions"] if r["transaction_id"].endswith("DUP008"))
    assert duplicate["reason_code"] == "DUPLICATE_TRANSACTION_ID"


def test_non_object_record_is_rejected_not_dropped(shared_root, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(["nonsense", {"transaction_id": "TXN900",
                                             "timestamp": "2026-03-16T09:00:00Z",
                                             "source_account": "ACC-1001",
                                             "destination_account": "ACC-2001",
                                             "amount": "10.00", "currency": "USD",
                                             "transaction_type": "transfer"}]), encoding="utf-8")
    summary = run_pipeline(path, shared_root, clean=True, now=FIXED_NOW)
    assert summary["total"] == 2 and summary["complete"] is True
    assert summary["rejections"][0]["reason_code"] == "MALFORMED_RECORD"


def test_refuses_to_mix_runs(shared_root, sample_input):
    (shared_root / "input" / "LEFTOVER.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PipelineStateError, match="previous run"):
        run_pipeline(sample_input, shared_root, clean=False, now=FIXED_NOW)


def test_clean_keeps_the_committed_directory_skeleton(shared_root, sample_input):
    keep = shared_root / "results" / ".gitkeep"
    keep.touch()
    run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW)
    assert keep.exists()


def test_input_must_be_a_json_array(shared_root, tmp_path):
    path = tmp_path / "object.json"
    path.write_text(json.dumps({"transaction_id": "TXN001"}), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        run_pipeline(path, shared_root, clean=True, now=FIXED_NOW)


def test_cli_succeeds_on_a_complete_run(shared_root, sample_input, capsys):
    exit_code = main(["--input", str(sample_input), "--shared", str(shared_root), "--clean"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "settled=4" in out and "held=2" in out and "rejected=2" in out
    assert "WATCHLIST_MATCH" in out


def test_cli_json_output(shared_root, sample_input, capsys):
    main(["--input", str(sample_input), "--shared", str(shared_root), "--clean", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["by_status"]["settled"] == 4


def test_cli_refuses_a_dirty_shared_directory(shared_root, sample_input, capsys):
    (shared_root / "output" / "LEFTOVER.json").write_text("{}", encoding="utf-8")
    exit_code = main(["--input", str(sample_input), "--shared", str(shared_root)])
    assert exit_code == 2
    assert "refusing to start" in capsys.readouterr().err


def test_clean_removes_stray_directories_too(shared_root, sample_input):
    stray = shared_root / "processing" / "half-finished-batch"
    stray.mkdir()
    (stray / "TXN001.json").write_text("{}", encoding="utf-8")
    leftover_file = shared_root / "output" / "TXN999.json"
    leftover_file.write_text("{}", encoding="utf-8")

    run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW)

    assert not stray.exists() and not leftover_file.exists()


def test_cli_reports_an_incomplete_run(shared_root, sample_input, capsys, monkeypatch):
    # A record that never reaches results/ must fail the run loudly: a stuck
    # transaction is money nobody is looking for.
    incomplete = dict(run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW))
    incomplete["complete"] = False
    incomplete["expected_total"] = 9
    monkeypatch.setattr(orchestrator, "run_pipeline", lambda *a, **k: incomplete)

    exit_code = main(["--input", str(sample_input), "--shared", str(shared_root), "--clean"])

    assert exit_code == 1
    assert "INCOMPLETE" in capsys.readouterr().err
