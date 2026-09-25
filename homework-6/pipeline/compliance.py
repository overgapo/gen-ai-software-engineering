"""Stage 3 -- compliance screening.

Two obligations that are deliberately kept apart (spec §7.3): a watchlist match
*blocks*, a currency-transaction filing *records*. Conflating them -- holding a
transaction because it is reportable, or skipping the filing because it settled
-- is the defect this stage exists to avoid.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pipeline import config
from pipeline.audit import hash_account
from pipeline.models import (
    iso8601,
    next_envelope,
    terminal_envelope,
    to_decimal,
    utc_now,
)

STAGE = "compliance"
NEXT_STAGE = "settlement"


def screen_transaction(
    data: dict[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    """Pure screening decision. The clock is injected so tests are stable."""
    screened_at = iso8601(now or utc_now())
    normalized = data.get("normalized") or {}
    risk = data.get("risk") or {}

    accounts = {
        "source_account": str(data.get("source_account") or ""),
        "destination_account": str(data.get("destination_account") or ""),
    }
    # Screening happens on the account identifier; only the hash is kept, so a
    # result file is not a second copy of the account ledger.
    matches = [
        {"field": field, "account_hash": hash_account(account)}
        for field, account in accounts.items()
        if account in config.WATCHLIST_ACCOUNTS
    ]

    filings: list[dict[str, Any]] = []
    raw_usd = normalized.get("usd_equivalent")
    if raw_usd is not None and to_decimal(raw_usd) >= config.REPORTING_THRESHOLD:
        filings.append(
            {
                "type": "CTR",
                "threshold": str(config.REPORTING_THRESHOLD),
                "amount_usd": str(raw_usd),
                "filed_at": screened_at,
            }
        )
    if "STRUCTURING" in (risk.get("signals") or []):
        filings.append(
            {
                "type": "STRUCTURING_REFERRAL",
                "amount_usd": str(raw_usd) if raw_usd is not None else None,
                "filed_at": screened_at,
            }
        )

    return {
        "cleared": not matches,
        "watchlist_matches": matches,
        "filings": filings,
        "screened_at": screened_at,
    }


def process_transaction(record: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    data = record.get("data") or {}
    compliance = screen_transaction(data, now=now)

    if not compliance["cleared"]:
        fields = ", ".join(match["field"] for match in compliance["watchlist_matches"])
        return terminal_envelope(
            record,
            source_stage=STAGE,
            final_status="held",
            reason_code="WATCHLIST_MATCH",
            detail=f"watchlist match on {fields}",
            data_updates={"compliance": compliance},
            now=now,
        )

    return next_envelope(
        record,
        source_stage=STAGE,
        target_stage=NEXT_STAGE,
        data_updates={"status": "compliance_cleared", "compliance": compliance},
        now=now,
    )
