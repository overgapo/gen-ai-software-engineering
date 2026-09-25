"""Envelope, decimal and file-write helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from pipeline import config
from pipeline.audit import hash_account
from pipeline.models import (
    build_envelope,
    decimal_places,
    decimal_to_str,
    iso8601,
    is_terminal,
    json_default,
    load_record,
    next_envelope,
    parse_iso8601,
    quantize_half_up,
    terminal_envelope,
    to_decimal,
    utc_now,
    write_record_atomic,
)
from tests.conftest import FIXED_NOW, raw_transaction


@pytest.mark.parametrize(
    "value,expected",
    [("1500.00", "1500.00"), (1500, "1500"), (Decimal("1.5"), "1.5"), (" 2.50 ", "2.50")],
)
def test_to_decimal_accepts_safe_inputs(value, expected):
    assert decimal_to_str(to_decimal(value)) == expected


def test_to_decimal_takes_the_shortest_repr_of_a_float():
    # Producers do send JSON numbers. Decimal(0.1) would give
    # 0.1000000000000000055511151231257827; repr() keeps what was meant.
    assert to_decimal(0.1) == Decimal("0.1")


@pytest.mark.parametrize("value", [True, False, None, [], {}, "abc", "NaN", "Infinity"])
def test_to_decimal_rejects_everything_else(value):
    with pytest.raises((ValueError, ArithmeticError)):
        to_decimal(value)


@pytest.mark.parametrize(
    "value,exponent,expected",
    [("1.35625", 2, "1.36"), ("0.125", 2, "0.13"), ("2.345", 2, "2.35"),
     ("1000.5", 0, "1001"), ("-0.125", 2, "-0.13")],
)
def test_quantize_half_up(value, exponent, expected):
    assert decimal_to_str(quantize_half_up(Decimal(value), exponent)) == expected


@pytest.mark.parametrize("value,places", [("1500", 0), ("1500.0", 1), ("1.005", 3)])
def test_decimal_places(value, places):
    assert decimal_places(Decimal(value)) == places


@pytest.mark.parametrize(
    "value,expected_hour",
    [("2026-03-16T09:00:00Z", 9), ("2026-03-16T09:00:00z", 9),
     ("2026-03-16T10:00:00+01:00", 9), ("2026-03-16T04:00:00-05:00", 9)],
)
def test_parse_iso8601_normalizes_to_utc(value, expected_hour):
    assert parse_iso8601(value).hour == expected_hour


def test_parse_iso8601_rejects_a_naive_timestamp():
    with pytest.raises(ValueError, match="offset"):
        parse_iso8601("2026-03-16T09:00:00")


def test_iso8601_always_ends_in_z():
    assert iso8601(datetime(2026, 3, 16, 9, tzinfo=timezone.utc)) == "2026-03-16T09:00:00Z"
    assert utc_now().tzinfo is timezone.utc


def test_json_default_serializes_decimal_and_datetime():
    assert json_default(Decimal("1.50")) == "1.50"
    assert json_default(FIXED_NOW) == "2026-03-16T12:00:00Z"
    with pytest.raises(TypeError):
        json_default(object())


def test_build_envelope_shape():
    record = build_envelope(
        raw_transaction(), source_stage="orchestrator", target_stage="validator", now=FIXED_NOW
    )
    assert set(record) == {
        "message_id", "timestamp", "source_stage", "target_stage", "message_type", "data",
    }
    assert record["message_type"] == "transaction"
    assert record["timestamp"] == "2026-03-16T12:00:00Z"
    assert record["data"]["correlation_id"]


def test_next_envelope_keeps_correlation_but_refreshes_message_id():
    first = build_envelope(
        raw_transaction(), source_stage="orchestrator", target_stage="validator", now=FIXED_NOW
    )
    second = next_envelope(
        first, source_stage="validator", target_stage="fraud_detector",
        data_updates={"status": "validated"}, now=FIXED_NOW,
    )
    assert second["data"]["correlation_id"] == first["data"]["correlation_id"]
    assert second["message_id"] != first["message_id"]
    assert second["data"]["status"] == "validated"
    assert not is_terminal(second)


def test_terminal_envelope_records_who_decided_and_why():
    record = build_envelope(
        raw_transaction(), source_stage="orchestrator", target_stage="validator", now=FIXED_NOW
    )
    out = terminal_envelope(
        record, source_stage="validator", final_status="rejected",
        reason_code="UNSUPPORTED_CURRENCY", detail="XYZ", now=FIXED_NOW,
    )
    assert is_terminal(out) and out["target_stage"] == config.TERMINAL_TARGET
    assert out["data"]["decided_by"] == "validator"
    assert out["data"]["decided_at"] == "2026-03-16T12:00:00Z"
    assert out["data"]["detail"] == "XYZ"


def test_write_record_atomic_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "nested" / "TXN001.json"
    write_record_atomic(path, {"data": {"amount": Decimal("1500.00")}})
    assert json.loads(path.read_text())["data"]["amount"] == "1500.00"
    assert list(tmp_path.rglob("*.tmp")) == []
    assert load_record(path)["data"]["amount"] == "1500.00"


def test_load_record_rejects_a_non_object(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_record(path)


def test_hash_account_is_stable_and_opaque():
    assert hash_account("ACC-1001") == hash_account("ACC-1001")
    assert hash_account("ACC-1001") != hash_account("ACC-1002")
    assert hash_account("ACC-1001").startswith("acct_")
    assert "ACC-1001" not in hash_account("ACC-1001")


def test_decimal_places_rejects_a_non_finite_value():
    # Decimal('NaN').as_tuple().exponent is the string 'n', not an int.
    with pytest.raises(ValueError, match="not finite"):
        decimal_places(Decimal("NaN"))
