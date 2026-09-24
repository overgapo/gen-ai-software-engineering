"""Stage 4 tests -- exact amounts only.

pytest.approx has no place in a money test: an assertion that tolerates a
fraction of a cent is an assertion that will not notice the day a float creeps
into the money path.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline import config
from pipeline.models import to_decimal
from pipeline.settlement import process_transaction, settle_transaction, settlement_fee
from pipeline.validator import validate_transaction
from tests.conftest import FIXED_NOW, envelope, raw_transaction


def data_for(**overrides):
    raw = raw_transaction(**overrides)
    result = validate_transaction(raw)
    assert result.ok, result.reason_code
    data = dict(raw)
    data["normalized"] = result.normalized
    return data


def test_usd_settles_without_conversion():
    outcome = settle_transaction(data_for(amount="1500.00"), now=FIXED_NOW)
    settlement = outcome["settlement"]
    assert outcome["ok"] and settlement["gross"] == "1500.00"
    assert settlement["fee"] == "3.75" and settlement["net"] == "1496.25"
    assert settlement["fx"]["rate"] == "1" and settlement["fx"]["source_currency"] == "USD"


def test_eur_conversion_matches_the_spec_to_the_cent():
    # 500.00 EUR @ 1.0850 = 542.50; fee 542.50 * 0.0025 = 1.35625 -> 1.36.
    outcome = settle_transaction(data_for(amount="500.00", currency="EUR"), now=FIXED_NOW)
    settlement = outcome["settlement"]
    assert (settlement["gross"], settlement["fee"], settlement["net"]) == (
        "542.50",
        "1.36",
        "541.14",
    )
    assert settlement["fx"]["version"] == config.FX_RATES_VERSION


def test_rounding_is_half_up_not_half_even():
    # 1.35625 rounds to 1.36 under ROUND_HALF_UP; Python's default
    # ROUND_HALF_EVEN would also give 1.36 here, so use a value where they
    # differ: 0.125 -> 0.13 half-up, 0.12 half-even.
    assert settlement_fee(Decimal("50.00")) == config.FEE_MIN
    from pipeline.models import quantize_half_up

    assert quantize_half_up(Decimal("0.125"), 2) == Decimal("0.13")
    assert quantize_half_up(Decimal("0.135"), 2) == Decimal("0.14")


@pytest.mark.parametrize(
    "gross,expected",
    [
        ("1.00", "0.50"),      # floor
        ("200.00", "0.50"),    # 0.50 exactly at the floor
        ("200.01", "0.50"),
        ("1000.00", "2.50"),
        ("10000.00", "25.00"),  # exactly at the cap
        ("25000.00", "25.00"),  # clamped
    ],
)
def test_fee_floor_and_cap(gross, expected):
    assert settlement_fee(to_decimal(gross)) == to_decimal(expected)


@pytest.mark.parametrize(
    "amount,currency",
    [("1500.00", "USD"), ("500.00", "EUR"), ("9999.99", "USD"), ("0.01", "GBP"),
     ("1000", "JPY"), ("3200.00", "USD"), ("49999.99", "CHF")],
)
def test_gross_always_equals_net_plus_fee(amount, currency):
    # net is an exact subtraction of two already-rounded values, so this holds
    # with no tolerance at all.
    settlement = settle_transaction(data_for(amount=amount, currency=currency))["settlement"]
    gross, fee, net = (to_decimal(settlement[key]) for key in ("gross", "fee", "net"))
    assert gross == net + fee


def test_missing_rate_holds_rather_than_guessing():
    outcome = settle_transaction(data_for(currency="UAH"), now=FIXED_NOW)
    assert outcome["ok"] is False
    assert outcome["reason_code"] == "FX_RATE_UNAVAILABLE"
    assert "settlement" not in outcome


def test_process_transaction_settles_terminally():
    record = envelope(target_stage="settlement")
    record["data"] = data_for()
    out = process_transaction(record, now=FIXED_NOW)
    assert out["target_stage"] == config.TERMINAL_TARGET
    assert out["data"]["final_status"] == "settled"
    assert out["data"]["reason_code"] == "SETTLED"
    assert out["data"]["settlement"]["settled_at"] == "2026-03-16T12:00:00Z"


def test_process_transaction_holds_without_a_rate():
    record = envelope(target_stage="settlement", currency="UAH")
    record["data"] = data_for(currency="UAH")
    out = process_transaction(record, now=FIXED_NOW)
    assert out["data"]["final_status"] == "held"
    assert out["data"]["reason_code"] == "FX_RATE_UNAVAILABLE"


def test_every_supported_currency_either_settles_or_holds_explicitly():
    for currency in config.SUPPORTED_CURRENCIES:
        amount = "1000" if currency == "JPY" else "1000.00"
        outcome = settle_transaction(data_for(amount=amount, currency=currency))
        assert outcome["ok"] is (currency in config.FX_RATES)
        assert outcome["reason_code"] in {"SETTLED", "FX_RATE_UNAVAILABLE"}
