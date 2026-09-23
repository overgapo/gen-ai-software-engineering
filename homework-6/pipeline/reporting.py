"""Run summary built from the terminal records in ``shared/results/``."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pipeline import config
from pipeline.models import decimal_to_str, iso8601, load_record, to_decimal, utc_now


def iter_results(results_dir: Path):
    """Yield terminal records, skipping the summary file itself."""
    for path in sorted(Path(results_dir).glob("*.json")):
        if path.name == config.SUMMARY_FILENAME:
            continue
        yield load_record(path)


def build_summary(
    results_dir: Path,
    *,
    run_id: str = "",
    started_at: str = "",
    finished_at: str | None = None,
    expected_total: int | None = None,
) -> dict[str, Any]:
    by_status: dict[str, int] = {"settled": 0, "held": 0, "rejected": 0}
    gross = fee = net = Decimal("0")
    rejections: list[dict[str, Any]] = []
    holds: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []

    for record in iter_results(results_dir):
        data = record.get("data") or {}
        status = str(data.get("final_status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1

        normalized = data.get("normalized") or {}
        risk = data.get("risk") or {}
        settlement = data.get("settlement") or {}
        entry = {
            "transaction_id": data.get("transaction_id"),
            "final_status": status,
            "reason_code": data.get("reason_code"),
            "detail": data.get("detail"),
            "amount": normalized.get("amount") or data.get("amount"),
            "currency": normalized.get("currency") or data.get("currency"),
            "risk_score": risk.get("score"),
            "risk_band": risk.get("band"),
            "signals": risk.get("signals") or [],
            "decided_by": data.get("decided_by"),
            "settlement": settlement or None,
            "filings": [f["type"] for f in (data.get("compliance") or {}).get("filings", [])],
        }
        transactions.append(entry)

        if status == "settled" and settlement:
            gross += to_decimal(settlement["gross"])
            fee += to_decimal(settlement["fee"])
            net += to_decimal(settlement["net"])
        elif status == "rejected":
            rejections.append(
                {
                    "transaction_id": entry["transaction_id"],
                    "reason_code": entry["reason_code"],
                    "detail": entry["detail"],
                }
            )
        elif status == "held":
            holds.append(
                {
                    "transaction_id": entry["transaction_id"],
                    "reason_code": entry["reason_code"],
                    "risk_score": entry["risk_score"],
                    "detail": entry["detail"],
                }
            )

    transactions.sort(key=lambda row: str(row["transaction_id"]))
    total = len(transactions)
    return {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at or iso8601(utc_now()),
        "total": total,
        "expected_total": expected_total if expected_total is not None else total,
        "complete": expected_total is None or expected_total == total,
        "by_status": by_status,
        "totals": {
            "settlement_currency": config.SETTLEMENT_CURRENCY,
            "settled_gross": decimal_to_str(gross),
            "fees": decimal_to_str(fee),
            "settled_net": decimal_to_str(net),
        },
        "rejections": rejections,
        "holds": holds,
        "transactions": transactions,
    }
