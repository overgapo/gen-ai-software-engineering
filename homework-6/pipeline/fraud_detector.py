"""Stage 2 -- fraud detection.

Additive scoring over a closed signal set (spec §7.2). The score is never
returned on its own: a number nobody can explain is not actionable, so every
score carries the signals that produced it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pipeline import config
from pipeline.models import (
    iso8601,
    next_envelope,
    parse_iso8601,
    terminal_envelope,
    to_decimal,
    utc_now,
)

STAGE = "fraud_detector"
NEXT_STAGE = "compliance"


def _band(score: int) -> str:
    if score >= config.HIGH_RISK_HOLD_SCORE:
        return "HIGH"
    if score >= config.MEDIUM_RISK_SCORE:
        return "MEDIUM"
    return "LOW"


def score_transaction(
    normalized: dict[str, Any], metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Pure scoring. Signals are emitted in the order of the spec's table."""
    metadata = metadata or {}
    signals: list[str] = []

    raw_usd = normalized.get("usd_equivalent")
    # None means no published FX rate. Amount-based rules have nothing to
    # compare against; settlement holds the record rather than guessing a rate.
    usd: Decimal | None = to_decimal(raw_usd) if raw_usd is not None else None
    if usd is not None:
        if usd >= config.REPORTING_THRESHOLD:
            signals.append("HIGH_VALUE")
        if usd >= config.VERY_HIGH_VALUE_THRESHOLD:
            signals.append("VERY_HIGH_VALUE")
        # 9 000-9 999.99 sits just under the reporting threshold: the classic
        # structuring shape, and the reason this band exists at all.
        if config.STRUCTURING_FLOOR <= usd < config.REPORTING_THRESHOLD:
            signals.append("STRUCTURING")

    hour = parse_iso8601(str(normalized["timestamp"])).hour
    if config.UNUSUAL_HOUR_FIRST <= hour <= config.UNUSUAL_HOUR_LAST:
        signals.append("UNUSUAL_HOUR")

    country = metadata.get("country") or normalized.get("country")
    if country and country != config.HOME_COUNTRY:
        signals.append("CROSS_BORDER")

    channel = metadata.get("channel") or normalized.get("channel")
    if channel in config.UNATTENDED_CHANNELS:
        signals.append("UNATTENDED_CHANNEL")

    score = min(
        sum(config.RISK_SIGNAL_POINTS[signal] for signal in signals), config.MAX_RISK_SCORE
    )
    return {"score": score, "band": _band(score), "signals": signals}


def process_transaction(record: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    data = record.get("data") or {}
    normalized = data.get("normalized") or {}
    risk = score_transaction(normalized, data.get("metadata"))
    risk["scored_at"] = iso8601(now or utc_now())

    if risk["band"] == "HIGH":
        return terminal_envelope(
            record,
            source_stage=STAGE,
            final_status="held",
            reason_code="HIGH_RISK",
            detail=f"risk score {risk['score']} ({', '.join(risk['signals'])})",
            data_updates={"risk": risk},
            now=now,
        )

    return next_envelope(
        record,
        source_stage=STAGE,
        target_stage=NEXT_STAGE,
        data_updates={"status": "risk_scored", "risk": risk},
        now=now,
    )
