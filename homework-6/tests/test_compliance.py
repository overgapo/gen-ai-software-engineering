"""Stage 3 tests.

The load-bearing assertion in this file is that a filing does not block
settlement. Conflating the two is the defect the stage exists to avoid.
"""

from __future__ import annotations

import pytest

from pipeline import config
from pipeline.audit import hash_account
from pipeline.compliance import process_transaction, screen_transaction
from pipeline.validator import validate_transaction
from tests.conftest import FIXED_NOW, envelope, raw_transaction

WATCHLISTED = sorted(config.WATCHLIST_ACCOUNTS)[0]


def data_for(risk_signals=None, **overrides):
    raw = raw_transaction(**overrides)
    result = validate_transaction(raw)
    assert result.ok, result.reason_code
    data = dict(raw)
    data["normalized"] = result.normalized
    data["risk"] = {"score": 0, "band": "LOW", "signals": risk_signals or []}
    return data


def test_clean_transaction_clears_with_no_filings():
    compliance = screen_transaction(data_for(), now=FIXED_NOW)
    assert compliance["cleared"] is True
    assert compliance["filings"] == [] and compliance["watchlist_matches"] == []
    assert compliance["screened_at"] == "2026-03-16T12:00:00Z"


@pytest.mark.parametrize("field", ["source_account", "destination_account"])
def test_watchlist_match_on_either_side(field):
    compliance = screen_transaction(data_for(**{field: WATCHLISTED}), now=FIXED_NOW)
    assert compliance["cleared"] is False
    assert [m["field"] for m in compliance["watchlist_matches"]] == [field]


def test_watchlist_match_records_only_the_hash():
    compliance = screen_transaction(data_for(destination_account=WATCHLISTED), now=FIXED_NOW)
    match = compliance["watchlist_matches"][0]
    assert match["account_hash"] == hash_account(WATCHLISTED)
    assert WATCHLISTED not in str(match)


@pytest.mark.parametrize(
    "amount,filed", [("9999.99", False), ("10000.00", True), ("25000.00", True)]
)
def test_ctr_filing_threshold(amount, filed):
    compliance = screen_transaction(data_for(amount=amount), now=FIXED_NOW)
    types = [f["type"] for f in compliance["filings"]]
    assert ("CTR" in types) is filed


def test_ctr_filing_does_not_block_settlement():
    # A currency-transaction filing is a record-keeping obligation. Holding the
    # transaction because it is reportable would be a defect.
    compliance = screen_transaction(data_for(amount="25000.00"), now=FIXED_NOW)
    assert compliance["cleared"] is True
    assert compliance["filings"][0]["type"] == "CTR"
    assert compliance["filings"][0]["threshold"] == str(config.REPORTING_THRESHOLD)


def test_structuring_referral_is_filed():
    compliance = screen_transaction(
        data_for(risk_signals=["STRUCTURING"], amount="9999.99"), now=FIXED_NOW
    )
    assert [f["type"] for f in compliance["filings"]] == ["STRUCTURING_REFERRAL"]
    assert compliance["cleared"] is True


def test_both_filings_can_coexist_with_a_hold():
    data = data_for(
        risk_signals=["STRUCTURING"], amount="9999.99", destination_account=WATCHLISTED
    )
    compliance = screen_transaction(data, now=FIXED_NOW)
    assert compliance["cleared"] is False
    assert [f["type"] for f in compliance["filings"]] == ["STRUCTURING_REFERRAL"]


def test_no_filing_without_a_usd_figure():
    compliance = screen_transaction(data_for(currency="UAH"), now=FIXED_NOW)
    assert compliance["filings"] == [] and compliance["cleared"] is True


def test_process_transaction_holds_on_match():
    record = envelope(target_stage="compliance", destination_account=WATCHLISTED)
    record["data"] = data_for(destination_account=WATCHLISTED)
    out = process_transaction(record, now=FIXED_NOW)
    assert out["target_stage"] == config.TERMINAL_TARGET
    assert out["data"]["final_status"] == "held"
    assert out["data"]["reason_code"] == "WATCHLIST_MATCH"
    assert "destination_account" in out["data"]["detail"]


def test_process_transaction_forwards_cleared_record():
    record = envelope(target_stage="compliance")
    record["data"] = data_for(amount="25000.00")
    out = process_transaction(record, now=FIXED_NOW)
    assert out["target_stage"] == "settlement"
    assert out["data"]["status"] == "compliance_cleared"
    assert out["data"]["compliance"]["filings"][0]["type"] == "CTR"
