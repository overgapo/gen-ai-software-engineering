"""Stage 2 tests -- every signal, every band boundary.

A score is only useful if it is explainable, so these tests assert the signal
list as well as the number.
"""

from __future__ import annotations

import pytest

from pipeline import config
from pipeline.fraud_detector import process_transaction, score_transaction
from pipeline.validator import validate_transaction
from tests.conftest import FIXED_NOW, envelope, raw_transaction


def normalized_for(**overrides):
    result = validate_transaction(raw_transaction(**overrides))
    assert result.ok, result.reason_code
    return result.normalized


def test_clean_transaction_scores_zero():
    risk = score_transaction(normalized_for(), {"country": "US", "channel": "online"})
    assert risk == {"score": 0, "band": "LOW", "signals": []}


@pytest.mark.parametrize(
    "overrides,metadata,expected",
    [
        ({"amount": "10000.00"}, {}, ["HIGH_VALUE"]),
        ({"amount": "25000.00"}, {}, ["HIGH_VALUE"]),
        ({"amount": "50000.00"}, {}, ["HIGH_VALUE", "VERY_HIGH_VALUE"]),
        ({"amount": "9000.00"}, {}, ["STRUCTURING"]),
        ({"amount": "9999.99"}, {}, ["STRUCTURING"]),
        ({"timestamp": "2026-03-16T02:47:00Z"}, {}, ["UNUSUAL_HOUR"]),
        ({"timestamp": "2026-03-16T04:59:00Z"}, {}, ["UNUSUAL_HOUR"]),
        ({"timestamp": "2026-03-16T00:00:00Z"}, {}, ["UNUSUAL_HOUR"]),
        ({}, {"country": "DE"}, ["CROSS_BORDER"]),
        ({}, {"channel": "api"}, ["UNATTENDED_CHANNEL"]),
    ],
)
def test_each_signal_fires_on_its_own(overrides, metadata, expected):
    risk = score_transaction(normalized_for(**overrides), metadata)
    assert risk["signals"] == expected
    assert risk["score"] == sum(config.RISK_SIGNAL_POINTS[s] for s in expected)


@pytest.mark.parametrize(
    "amount,expected",
    [("8999.99", []), ("9000.00", ["STRUCTURING"]), ("9999.99", ["STRUCTURING"]),
     ("10000.00", ["HIGH_VALUE"]), ("49999.99", ["HIGH_VALUE"])],
)
def test_amount_band_boundaries(amount, expected):
    # The structuring band is [9 000, 10 000): at exactly 10 000 the
    # transaction is reportable, so it is HIGH_VALUE, not structuring.
    assert score_transaction(normalized_for(amount=amount), {})["signals"] == expected


@pytest.mark.parametrize("hour,fires", [(0, True), (4, True), (5, False), (9, False), (23, False)])
def test_unusual_hour_window(hour, fires):
    normalized = normalized_for(timestamp=f"2026-03-16T{hour:02d}:30:00Z")
    assert ("UNUSUAL_HOUR" in score_transaction(normalized, {})["signals"]) is fires


def test_home_country_is_not_cross_border():
    risk = score_transaction(normalized_for(), {"country": config.HOME_COUNTRY})
    assert "CROSS_BORDER" not in risk["signals"]


def test_signals_accumulate():
    risk = score_transaction(
        normalized_for(amount="500.00", currency="EUR", timestamp="2026-03-16T02:47:00Z"),
        {"country": "DE", "channel": "api"},
    )
    assert risk["signals"] == ["UNUSUAL_HOUR", "CROSS_BORDER", "UNATTENDED_CHANNEL"]
    assert risk["score"] == 45 and risk["band"] == "MEDIUM"


def test_score_is_capped():
    risk = score_transaction(
        normalized_for(amount="75000.00", timestamp="2026-03-16T03:00:00Z"),
        {"country": "DE", "channel": "api"},
    )
    assert risk["score"] == min(105, config.MAX_RISK_SCORE) == 100


@pytest.mark.parametrize(
    "score,band",
    [(0, "LOW"), (24, "LOW"), (25, "MEDIUM"), (59, "MEDIUM"), (60, "HIGH"), (100, "HIGH")],
)
def test_band_boundaries(score, band, monkeypatch):
    from pipeline import fraud_detector

    assert fraud_detector._band(score) == band


def test_missing_fx_rate_suppresses_amount_signals():
    # No published rate means no USD figure to compare: the amount rules are
    # skipped rather than evaluated against the raw foreign amount.
    normalized = normalized_for(amount="75000.00", currency="UAH")
    risk = score_transaction(normalized, {"country": "US", "channel": "online"})
    assert risk["signals"] == [] and risk["score"] == 0


def test_high_band_is_held_terminally():
    record = envelope(target_stage="fraud_detector", amount="75000.00")
    record["data"]["normalized"] = normalized_for(amount="75000.00")
    out = process_transaction(record, now=FIXED_NOW)
    assert out["target_stage"] == config.TERMINAL_TARGET
    assert out["data"]["final_status"] == "held"
    assert out["data"]["reason_code"] == "HIGH_RISK"
    assert "HIGH_VALUE" in out["data"]["detail"]


def test_medium_band_continues_to_compliance():
    record = envelope(target_stage="fraud_detector", amount="25000.00")
    record["data"]["normalized"] = normalized_for(amount="25000.00")
    out = process_transaction(record, now=FIXED_NOW)
    assert out["target_stage"] == "compliance"
    assert out["data"]["risk"]["score"] == 40
    assert out["data"]["status"] == "risk_scored"


def test_risk_block_records_when_it_was_scored():
    record = envelope(target_stage="fraud_detector")
    record["data"]["normalized"] = normalized_for()
    out = process_transaction(record, now=FIXED_NOW)
    assert out["data"]["risk"]["scored_at"] == "2026-03-16T12:00:00Z"
