"""Stage 4 -- settlement.

FX conversion, fee, net. Rounding happens exactly twice -- once on the
converted gross, once on the fee -- and never on the net, which is an exact
subtraction of two already-rounded values (spec §7.4).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pipeline import config
from pipeline.models import (
    decimal_to_str,
    iso8601,
    quantize_half_up,
    terminal_envelope,
    to_decimal,
    utc_now,
)

STAGE = "settlement"

_EXPONENT = config.currency_exponent(config.SETTLEMENT_CURRENCY)


def settlement_fee(gross: Decimal) -> Decimal:
    """25 bps of the settled gross, clamped to [FEE_MIN, FEE_MAX]."""
    fee = quantize_half_up(gross * config.FEE_RATE, _EXPONENT)
    return min(max(fee, config.FEE_MIN), config.FEE_MAX)


def settle_transaction(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Pure settlement decision.

    Returns ``{"ok": False, "reason_code": ...}`` when no FX rate is published:
    a lagging settlement is an inconvenience, a guessed rate is a monetary
    error that reconciliation finds weeks later (agents.md §4.5).
    """
    normalized = data.get("normalized") or {}
    currency = str(normalized.get("currency") or "")
    amount = to_decimal(normalized["amount"])

    rate = config.FX_RATES.get(currency)
    if rate is None:
        return {
            "ok": False,
            "reason_code": "FX_RATE_UNAVAILABLE",
            "detail": f"no published {config.SETTLEMENT_CURRENCY} rate for {currency}",
        }

    gross = quantize_half_up(amount * rate, _EXPONENT)
    fee = settlement_fee(gross)
    net = gross - fee

    return {
        "ok": True,
        "reason_code": "SETTLED",
        "settlement": {
            "currency": config.SETTLEMENT_CURRENCY,
            "gross": decimal_to_str(gross),
            "fee": decimal_to_str(fee),
            "net": decimal_to_str(net),
            "fee_rate": decimal_to_str(config.FEE_RATE),
            "fx": {
                "source_currency": currency,
                "rate": decimal_to_str(rate),
                "version": config.FX_RATES_VERSION,
            },
            "settled_at": iso8601(now or utc_now()),
        },
    }


def process_transaction(record: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    data = record.get("data") or {}
    outcome = settle_transaction(data, now=now)

    if not outcome["ok"]:
        return terminal_envelope(
            record,
            source_stage=STAGE,
            final_status="held",
            reason_code=outcome["reason_code"],
            detail=outcome.get("detail"),
            now=now,
        )

    return terminal_envelope(
        record,
        source_stage=STAGE,
        final_status="settled",
        reason_code="SETTLED",
        data_updates={"settlement": outcome["settlement"]},
        now=now,
    )
