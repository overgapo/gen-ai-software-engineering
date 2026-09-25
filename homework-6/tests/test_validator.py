"""Stage 1 tests -- every reason code in spec §7.1 has a case here.

A closed set of reason codes is only closed if something checks that, which is
why this file is parametrized over the whole table rather than spot-checking.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from pipeline import config
from pipeline.validator import (
    REQUIRED_FIELDS,
    dry_run,
    main,
    process_transaction,
    validate_transaction,
)
from tests.conftest import envelope, raw_transaction


def test_valid_record_passes():
    result = validate_transaction(raw_transaction())
    assert result.ok
    assert result.reason_code is None


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_field_is_rejected(field):
    record = raw_transaction()
    del record[field]
    result = validate_transaction(record)
    assert not result.ok and result.reason_code == "MISSING_FIELD"
    assert field in (result.detail or "")


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_field_counts_as_missing(blank):
    assert validate_transaction(raw_transaction(currency=blank)).reason_code == "MISSING_FIELD"


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-03-16T09:00:00",  # no offset -- guessing one would move the fraud hour
        "16/03/2026 09:00",
        "not-a-timestamp",
        "",
    ],
)
def test_invalid_timestamp(timestamp):
    result = validate_transaction(raw_transaction(timestamp=timestamp))
    assert not result.ok
    assert result.reason_code in {"INVALID_TIMESTAMP", "MISSING_FIELD"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_account", "1001"),
        ("source_account", "ACC-10011"),
        ("destination_account", "ACCT-2001"),
        ("destination_account", "ACC-20a1"),
    ],
)
def test_invalid_account_format(field, value):
    result = validate_transaction(raw_transaction(**{field: value}))
    assert result.reason_code == "INVALID_ACCOUNT_FORMAT"
    assert field in (result.detail or "")


def test_same_account_is_rejected():
    result = validate_transaction(
        raw_transaction(source_account="ACC-1001", destination_account="ACC-1001")
    )
    assert result.reason_code == "SAME_ACCOUNT"


@pytest.mark.parametrize("currency", ["XYZ", "US", "usdt", "ZZZ"])
def test_unsupported_currency(currency):
    assert validate_transaction(raw_transaction(currency=currency)).reason_code == (
        "UNSUPPORTED_CURRENCY"
    )


def test_currency_is_case_normalized():
    result = validate_transaction(raw_transaction(currency="eur"))
    assert result.ok and result.normalized["currency"] == "EUR"


@pytest.mark.parametrize("amount", ["abc", "1,500.00", "NaN", "Infinity", "12.3.4", True])
def test_malformed_amount(amount):
    assert validate_transaction(raw_transaction(amount=amount)).reason_code == "MALFORMED_AMOUNT"


@pytest.mark.parametrize("amount", ["-100.00", "0", "0.00", "-0.01"])
def test_non_positive_amount_is_rejected_never_absolved(amount):
    # A negative amount is a malformed producer payload, not a direction
    # indicator: abs() here would silently settle a reversal as a payment.
    result = validate_transaction(raw_transaction(amount=amount, currency="GBP"))
    assert result.reason_code == "NON_POSITIVE_AMOUNT"


@pytest.mark.parametrize(
    "amount,currency",
    [("1000.5", "JPY"), ("1.005", "USD"), ("0.001", "EUR")],
)
def test_amount_scale_mismatch(amount, currency):
    result = validate_transaction(raw_transaction(amount=amount, currency=currency))
    assert result.reason_code == "AMOUNT_SCALE_MISMATCH"


def test_jpy_accepts_whole_units():
    result = validate_transaction(raw_transaction(amount="1000", currency="JPY"))
    assert result.ok and result.normalized["amount"] == "1000"


def test_amount_out_of_range():
    too_big = str(config.MAX_AMOUNT + Decimal("1"))
    assert validate_transaction(raw_transaction(amount=too_big)).reason_code == (
        "AMOUNT_OUT_OF_RANGE"
    )


@pytest.mark.parametrize("kind", ["deposit", "crypto_swap", "", "TRANSFERS"])
def test_unsupported_transaction_type(kind):
    result = validate_transaction(raw_transaction(transaction_type=kind))
    assert result.reason_code in {"UNSUPPORTED_TRANSACTION_TYPE", "MISSING_FIELD"}


@pytest.mark.parametrize("kind", sorted(config.SUPPORTED_TRANSACTION_TYPES))
def test_every_supported_type_passes(kind):
    assert validate_transaction(raw_transaction(transaction_type=kind)).ok


def test_first_failure_wins():
    # Broken currency *and* a negative amount: the currency check comes first
    # in the table, so that is the code the operator sees.
    result = validate_transaction(raw_transaction(currency="XYZ", amount="-5.00"))
    assert result.reason_code == "UNSUPPORTED_CURRENCY"


def test_normalized_block_shape():
    result = validate_transaction(
        raw_transaction(amount="500.00", currency="EUR", timestamp="2026-03-16T02:47:00+01:00")
    )
    normalized = result.normalized
    assert normalized["timestamp"] == "2026-03-16T01:47:00Z"  # normalized to UTC
    assert normalized["usd_equivalent"] == "542.50"
    assert normalized["country"] == "US" and normalized["channel"] == "online"


def test_usd_equivalent_is_none_without_a_published_rate():
    # UAH is supported but has no settlement rate: the amount is carried
    # forward unconverted rather than guessed.
    result = validate_transaction(raw_transaction(currency="UAH"))
    assert result.ok and result.normalized["usd_equivalent"] is None


def test_process_transaction_routes_valid_record_onward():
    out = process_transaction(envelope())
    assert out["target_stage"] == "fraud_detector"
    assert out["data"]["status"] == "validated"
    assert out["source_stage"] == "validator"


def test_process_transaction_rejects_terminally():
    out = process_transaction(envelope(currency="XYZ"))
    assert out["target_stage"] == config.TERMINAL_TARGET
    assert out["data"]["final_status"] == "rejected"
    assert out["data"]["reason_code"] == "UNSUPPORTED_CURRENCY"
    assert out["data"]["decided_by"] == "validator"


def test_correlation_id_survives_the_hop():
    record = envelope()
    assert process_transaction(record)["data"]["correlation_id"] == (
        record["data"]["correlation_id"]
    )


def test_dry_run_over_the_sample_file(sample_input):
    report = dry_run(sample_input)
    assert (report["total"], report["valid"], report["invalid"]) == (8, 6, 2)
    codes = {row["transaction_id"]: row["reason_code"] for row in report["rows"]}
    assert codes["TXN006"] == "UNSUPPORTED_CURRENCY"
    assert codes["TXN007"] == "NON_POSITIVE_AMOUNT"


def test_dry_run_handles_a_non_object_record(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
    report = dry_run(path)
    assert report["rows"][0]["reason_code"] == "MALFORMED_RECORD"


def test_cli_exit_code_reports_invalid_records(sample_input, capsys):
    assert main(["--dry-run", "--input", str(sample_input)]) == 1
    out = capsys.readouterr().out
    assert "UNSUPPORTED_CURRENCY" in out and "total=8" in out


def test_cli_requires_dry_run(sample_input):
    with pytest.raises(SystemExit):
        main(["--input", str(sample_input)])
