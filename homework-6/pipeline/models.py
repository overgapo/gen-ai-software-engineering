"""Envelope, JSON and decimal helpers shared by every stage.

This module is the only place stages are allowed to share code (agents.md §6.1)
-- it holds no decision logic, only the mechanics of moving a record from one
stage to the next without losing precision or leaving a half-written file
behind.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from pipeline import config

MESSAGE_TYPE = "transaction"


# --- Time -------------------------------------------------------------------


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso8601(moment: datetime) -> str:
    """ISO 8601 in UTC with a ``Z`` suffix, seconds precision."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO 8601 timestamp that carries an explicit offset.

    A naive timestamp is rejected: "10:00" means nothing without an offset, and
    guessing one would silently move a transaction between fraud-scoring hours.
    """
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no UTC offset")
    return parsed.astimezone(timezone.utc)


# --- Money ------------------------------------------------------------------


def to_decimal(value: Any) -> Decimal:
    """Build a ``Decimal`` without ever routing through ``float``.

    A JSON number is accepted (``Decimal(str(value))``) because producers get
    this wrong, but the validator separately rejects it when its precision no
    longer matches the currency -- see spec §9.1.
    """
    if isinstance(value, bool):
        raise ValueError("boolean is not an amount")
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, (str, int)):
        amount = Decimal(str(value).strip())
    elif isinstance(value, float):
        amount = Decimal(repr(value))
    else:
        raise ValueError(f"unsupported amount type: {type(value).__name__}")
    if not amount.is_finite():
        raise ValueError("amount is not finite")
    return amount


def quantize_half_up(value: Decimal, exponent: int) -> Decimal:
    """Round to ``exponent`` decimal places, half away from zero.

    ROUND_HALF_UP is the banking convention the spec fixes in §4; the default
    ROUND_HALF_EVEN would quietly shave fractions of a cent in one direction.
    """
    quantum = Decimal(1).scaleb(-exponent)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def decimal_places(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("amount is not finite")
    return max(0, -exponent)


def decimal_to_str(value: Decimal) -> str:
    return format(value, "f")


def json_default(obj: Any) -> str:
    if isinstance(obj, Decimal):
        return decimal_to_str(obj)
    if isinstance(obj, datetime):
        return iso8601(obj)
    raise TypeError(f"not JSON serializable: {type(obj).__name__}")


# --- Envelope ---------------------------------------------------------------


def build_envelope(
    data: dict[str, Any],
    *,
    source_stage: str,
    target_stage: str,
    now: datetime | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Create a fresh envelope in the format fixed by spec §6.2."""
    payload = dict(data)
    payload.setdefault("correlation_id", correlation_id or str(uuid.uuid4()))
    return {
        "message_id": str(uuid.uuid4()),
        "timestamp": iso8601(now or utc_now()),
        "source_stage": source_stage,
        "target_stage": target_stage,
        "message_type": MESSAGE_TYPE,
        "data": payload,
    }


def next_envelope(
    record: dict[str, Any],
    *,
    source_stage: str,
    target_stage: str,
    data_updates: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Hand a record to the next stage.

    ``message_id`` is fresh per hop; ``correlation_id`` inside ``data`` is what
    ties the audit trail together and is never regenerated.
    """
    data = dict(record.get("data") or {})
    data.update(data_updates or {})
    return build_envelope(
        data,
        source_stage=source_stage,
        target_stage=target_stage,
        now=now,
        correlation_id=data.get("correlation_id"),
    )


def terminal_envelope(
    record: dict[str, Any],
    *,
    source_stage: str,
    final_status: str,
    reason_code: str,
    detail: str | None = None,
    data_updates: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a terminal record (``rejected`` / ``held`` / ``settled``).

    Zero is a decision, not an absence: a terminal record always carries the
    reason code and the stage that decided it.
    """
    updates = dict(data_updates or {})
    updates.update(
        {
            "status": final_status,
            "final_status": final_status,
            "reason_code": reason_code,
            "decided_by": source_stage,
            "decided_at": iso8601(now or utc_now()),
        }
    )
    if detail:
        updates["detail"] = detail
    return next_envelope(
        record,
        source_stage=source_stage,
        target_stage=config.TERMINAL_TARGET,
        data_updates=updates,
        now=now,
    )


def is_terminal(record: dict[str, Any]) -> bool:
    return record.get("target_stage") == config.TERMINAL_TARGET


def transaction_id(record: dict[str, Any]) -> str:
    return str((record.get("data") or {}).get("transaction_id") or "UNKNOWN")


def correlation_id(record: dict[str, Any]) -> str:
    return str((record.get("data") or {}).get("correlation_id") or "")


# --- File I/O ---------------------------------------------------------------


def load_record(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        record = json.load(handle)
    if not isinstance(record, dict):
        raise ValueError("record is not a JSON object")
    return record


def write_record_atomic(path: Path, record: dict[str, Any]) -> None:
    """Write via ``.tmp`` + ``os.replace``.

    A half-written JSON file must never be visible to the next stage, and a
    plain ``open(path, "w")`` makes exactly that visible for a few
    milliseconds.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False, default=json_default)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
