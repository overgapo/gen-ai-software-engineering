"""File-protocol mechanics: claiming, routing, failure handling.

These paths are the ones a happy-path run never exercises, which is exactly
why they need tests -- a stage that crashes on a bad record in production is a
transaction nobody is looking for.
"""

from __future__ import annotations

import json

import pytest

from pipeline import config, validator
from pipeline.audit import audit_path
from pipeline.models import build_envelope, load_record
from pipeline.stage_runner import ResultCollision, inbox_dir, run_stage
from tests.conftest import FIXED_NOW, raw_transaction, write_input


def test_first_stage_reads_input_and_later_stages_read_output(shared_root):
    assert inbox_dir(shared_root, "validator").name == "input"
    for stage in config.STAGE_ORDER[1:]:
        assert inbox_dir(shared_root, stage).name == "output"


def test_valid_record_is_forwarded_and_the_inbox_is_drained(shared_root):
    record = build_envelope(
        raw_transaction(), source_stage="orchestrator", target_stage="validator", now=FIXED_NOW
    )
    write_input(shared_root, record)

    outputs = run_stage(shared_root, "validator", validator.process_transaction, now=FIXED_NOW)

    assert len(outputs) == 1 and outputs[0]["target_stage"] == "fraud_detector"
    assert list((shared_root / "input").glob("*.json")) == []
    assert list((shared_root / "processing").glob("*.json")) == []
    assert (shared_root / "output" / "TXN100.json").exists()


def test_unreadable_file_becomes_a_terminal_rejection(shared_root):
    (shared_root / "input" / "TXN999.json").write_text("{not json", encoding="utf-8")

    run_stage(shared_root, "validator", validator.process_transaction, now=FIXED_NOW)

    data = load_record(shared_root / "results" / "TXN999.json")["data"]
    assert data["final_status"] == "rejected"
    assert data["reason_code"] == "MALFORMED_RECORD"
    assert data["detail"] == "JSONDecodeError"
    assert list((shared_root / "input").glob("*.json")) == []


def test_a_stage_that_raises_produces_a_terminal_record_not_a_crash(shared_root):
    write_input(
        shared_root,
        build_envelope(
            raw_transaction(), source_stage="orchestrator", target_stage="validator",
            now=FIXED_NOW,
        ),
    )

    def exploding_stage(record, now=None):
        raise ZeroDivisionError("account balance / 0")

    outputs = run_stage(shared_root, "validator", exploding_stage, now=FIXED_NOW)

    data = outputs[0]["data"]
    assert data["final_status"] == "rejected" and data["reason_code"] == "STAGE_ERROR"
    # The exception *type* is recorded; the message could carry payload data.
    assert data["detail"] == "ZeroDivisionError"
    assert "balance" not in json.dumps(data)


def test_records_addressed_elsewhere_are_left_alone(shared_root):
    record = build_envelope(
        raw_transaction(), source_stage="validator", target_stage="settlement", now=FIXED_NOW
    )
    path = shared_root / "output" / "TXN100.json"
    path.write_text(json.dumps(record), encoding="utf-8")

    assert run_stage(shared_root, "compliance", validator.process_transaction) == []
    assert path.exists()  # still waiting for settlement


def test_a_result_is_never_overwritten(shared_root):
    (shared_root / "results" / "TXN100.json").write_text("{}", encoding="utf-8")
    write_input(
        shared_root,
        build_envelope(
            raw_transaction(currency="XYZ"), source_stage="orchestrator",
            target_stage="validator", now=FIXED_NOW,
        ),
    )
    with pytest.raises(ResultCollision, match="TXN100"):
        run_stage(shared_root, "validator", validator.process_transaction, now=FIXED_NOW)


def test_every_processed_record_leaves_an_audit_line(shared_root):
    for txn_id, currency in (("TXN100", "USD"), ("TXN101", "XYZ")):
        write_input(
            shared_root,
            build_envelope(
                raw_transaction(transaction_id=txn_id, currency=currency),
                source_stage="orchestrator", target_stage="validator", now=FIXED_NOW,
            ),
        )

    run_stage(shared_root, "validator", validator.process_transaction, now=FIXED_NOW)

    lines = [json.loads(line) for line in audit_path(shared_root).read_text().splitlines()]
    outcomes = {line["transaction_id"]: line["outcome"] for line in lines}
    assert outcomes == {"TXN100": "forwarded:fraud_detector", "TXN101": "rejected"}
    assert all(line["source_account"].startswith("acct_") for line in lines)
