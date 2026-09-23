"""Stage 1 -- validation.

Ten ordered checks, first failure wins (spec §7.1). A record that fails here is
terminal: it is never risk-scored, never screened and never settled.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - `python pipeline/validator.py`
    # Direct script execution puts pipeline/ on sys.path, not the project root,
    # so the absolute imports below would fail. The brief documents this exact
    # invocation, so support it rather than insisting on `python -m`.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config
from pipeline.models import (
    decimal_places,
    decimal_to_str,
    iso8601,
    parse_iso8601,
    quantize_half_up,
    terminal_envelope,
    next_envelope,
    to_decimal,
)

STAGE = "validator"
NEXT_STAGE = "fraud_detector"

REQUIRED_FIELDS = (
    "transaction_id",
    "timestamp",
    "source_account",
    "destination_account",
    "amount",
    "currency",
    "transaction_type",
)


class ValidationResult:
    """Outcome of validating one record."""

    __slots__ = ("ok", "reason_code", "detail", "normalized")

    def __init__(
        self,
        ok: bool,
        reason_code: str | None = None,
        detail: str | None = None,
        normalized: dict[str, Any] | None = None,
    ) -> None:
        self.ok = ok
        self.reason_code = reason_code
        self.detail = detail
        self.normalized = normalized or {}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ValidationResult(ok={self.ok}, reason_code={self.reason_code!r})"


def _usd_equivalent(amount: Decimal, currency: str) -> Decimal | None:
    """Amount in settlement currency, or ``None`` when no rate is published.

    A missing rate is not an error here -- the record still needs screening --
    but it means the amount-based rules downstream have nothing to compare
    against, and settlement will hold it (spec §9.1).
    """
    rate = config.FX_RATES.get(currency)
    if rate is None:
        return None
    return quantize_half_up(
        amount * rate, config.currency_exponent(config.SETTLEMENT_CURRENCY)
    )


def validate_transaction(data: dict[str, Any]) -> ValidationResult:
    """Pure validation of one raw transaction. No I/O, no clock."""
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationResult(False, "MISSING_FIELD", f"field '{field}' is missing or empty")

    try:
        moment = parse_iso8601(str(data["timestamp"]))
    except (ValueError, TypeError) as exc:
        return ValidationResult(False, "INVALID_TIMESTAMP", str(exc))

    source = str(data["source_account"]).strip()
    destination = str(data["destination_account"]).strip()
    for label, account in (("source_account", source), ("destination_account", destination)):
        if not config.ACCOUNT_PATTERN.match(account):
            return ValidationResult(
                False, "INVALID_ACCOUNT_FORMAT", f"{label} does not match ACC-NNNN"
            )

    if source == destination:
        return ValidationResult(False, "SAME_ACCOUNT", "source and destination are identical")

    currency = str(data["currency"]).strip().upper()
    if currency not in config.SUPPORTED_CURRENCIES:
        return ValidationResult(
            False, "UNSUPPORTED_CURRENCY", f"'{currency}' is not a supported ISO 4217 code"
        )

    try:
        amount = to_decimal(data["amount"])
    except (ValueError, ArithmeticError, InvalidOperation) as exc:
        return ValidationResult(False, "MALFORMED_AMOUNT", str(exc))

    # A negative amount is a malformed producer payload, not a direction
    # indicator. Refunds are positive with transaction_type="refund" (spec
    # §7.1) -- never abs() this.
    if amount <= 0:
        return ValidationResult(False, "NON_POSITIVE_AMOUNT", "amount must be greater than zero")

    exponent = config.currency_exponent(currency)
    if decimal_places(amount) > exponent:
        return ValidationResult(
            False,
            "AMOUNT_SCALE_MISMATCH",
            f"{currency} allows {exponent} decimal place(s)",
        )

    if amount > config.MAX_AMOUNT:
        return ValidationResult(False, "AMOUNT_OUT_OF_RANGE", "amount exceeds the accepted maximum")

    transaction_type = str(data["transaction_type"]).strip().lower()
    if transaction_type not in config.SUPPORTED_TRANSACTION_TYPES:
        return ValidationResult(
            False, "UNSUPPORTED_TRANSACTION_TYPE", f"'{transaction_type}' is not accepted"
        )

    canonical = quantize_half_up(amount, exponent)
    metadata = data.get("metadata") or {}
    normalized = {
        "timestamp": iso8601(moment),
        "currency": currency,
        "amount": decimal_to_str(canonical),
        "usd_equivalent": (
            decimal_to_str(usd) if (usd := _usd_equivalent(canonical, currency)) is not None else None
        ),
        "transaction_type": transaction_type,
        "country": metadata.get("country"),
        "channel": metadata.get("channel"),
    }
    return ValidationResult(True, normalized=normalized)


def process_transaction(record: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Envelope bookkeeping around :func:`validate_transaction`."""
    data = record.get("data") or {}
    result = validate_transaction(data)
    if not result.ok:
        return terminal_envelope(
            record,
            source_stage=STAGE,
            final_status="rejected",
            reason_code=result.reason_code or "MALFORMED_RECORD",
            detail=result.detail,
            now=now,
        )
    return next_envelope(
        record,
        source_stage=STAGE,
        target_stage=NEXT_STAGE,
        data_updates={"status": "validated", "normalized": result.normalized},
        now=now,
    )


# --- CLI (used by the /validate-transactions skill) --------------------------


def dry_run(input_path: Path) -> dict[str, Any]:
    """Validate every record in a raw input file without touching ``shared/``."""
    with Path(input_path).open("r", encoding="utf-8") as handle:
        records = json.load(handle)
    rows = []
    for raw in records:
        if not isinstance(raw, dict):
            rows.append({"transaction_id": "UNKNOWN", "valid": False,
                         "reason_code": "MALFORMED_RECORD", "detail": "record is not an object"})
            continue
        result = validate_transaction(raw)
        rows.append(
            {
                "transaction_id": raw.get("transaction_id", "UNKNOWN"),
                "amount": raw.get("amount"),
                "currency": raw.get("currency"),
                "valid": result.ok,
                "reason_code": result.reason_code,
                "detail": result.detail,
            }
        )
    valid = sum(1 for row in rows if row["valid"])
    return {"total": len(rows), "valid": valid, "invalid": len(rows) - valid, "rows": rows}


def _print_dry_run(report: dict[str, Any]) -> None:
    print(f"{'TXN':<10} {'AMOUNT':>12} {'CUR':<4} {'RESULT':<9} REASON")
    print("-" * 78)
    for row in report["rows"]:
        verdict = "VALID" if row["valid"] else "INVALID"
        reason = row["reason_code"] or ""
        if row["detail"] and not row["valid"]:
            reason = f"{reason} ({row['detail']})"
        print(
            f"{row['transaction_id']:<10} {str(row.get('amount') or ''):>12} "
            f"{str(row.get('currency') or ''):<4} {verdict:<9} {reason}"
        )
    print("-" * 78)
    print(f"total={report['total']}  valid={report['valid']}  invalid={report['invalid']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transaction validation stage")
    parser.add_argument("--dry-run", action="store_true", help="validate without writing to shared/")
    parser.add_argument("--input", default="sample-transactions.json", type=Path)
    args = parser.parse_args(argv)

    if not args.dry_run:
        parser.error("this stage runs inside the pipeline; use --dry-run for standalone checks")

    report = dry_run(args.input)
    _print_dry_run(report)
    return 0 if report["invalid"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
