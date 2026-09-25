"""File-based stage mechanics shared by all four stages.

Stages never import each other; they share only this runner, which claims a
record from an inbox, hands it to a stage's pure ``process_transaction`` and
routes the result (spec §6.1). Keeping the mechanics in one place is why each
stage module is only its decision logic.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pipeline import config
from pipeline.audit import hash_account, log_event
from pipeline.models import (
    build_envelope,
    correlation_id,
    is_terminal,
    load_record,
    terminal_envelope,
    transaction_id,
    write_record_atomic,
)

ProcessFn = Callable[..., dict[str, Any]]


class ResultCollision(RuntimeError):
    """A terminal record would overwrite an existing result. Never silenced."""


def inbox_dir(shared_root: Path, stage_name: str) -> Path:
    """First stage reads ``input/``; later stages read ``output/``."""
    sub = "input" if stage_name == config.STAGE_ORDER[0] else "output"
    return Path(shared_root) / sub


def _audit_fields(record: dict[str, Any]) -> dict[str, Any]:
    data = record.get("data") or {}
    normalized = data.get("normalized") or {}
    risk = data.get("risk") or {}
    fields: dict[str, Any] = {
        "reason_code": data.get("reason_code"),
        "amount": normalized.get("amount") or data.get("amount"),
        "currency": normalized.get("currency") or data.get("currency"),
        "risk_score": risk.get("score"),
    }
    for key in ("source_account", "destination_account"):
        account = data.get(key)
        if account:
            fields[key] = hash_account(str(account))
    return fields


def _route(shared_root: Path, record: dict[str, Any]) -> Path:
    txn = transaction_id(record)
    if is_terminal(record):
        path = Path(shared_root) / "results" / f"{txn}.json"
        if path.exists():
            raise ResultCollision(f"result for {txn} already exists")
        return path
    return Path(shared_root) / "output" / f"{txn}.json"


def run_stage(
    shared_root: Path,
    stage_name: str,
    process: ProcessFn,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Process every record addressed to ``stage_name``. Returns the outputs."""
    shared_root = Path(shared_root)
    inbox = inbox_dir(shared_root, stage_name)
    processing = shared_root / "processing"
    processing.mkdir(parents=True, exist_ok=True)

    outputs: list[dict[str, Any]] = []
    for path in sorted(inbox.glob("*.json")):
        try:
            record = load_record(path)
        except (ValueError, UnicodeDecodeError) as exc:
            # An unreadable file still has to reach a terminal state -- a
            # silently skipped record is money nobody is looking for.
            record = build_envelope(
                {"transaction_id": path.stem},
                source_stage="ingest",
                target_stage=stage_name,
                now=now,
            )
            outputs.append(
                _finish(
                    shared_root,
                    stage_name,
                    terminal_envelope(
                        record,
                        source_stage=stage_name,
                        final_status="rejected",
                        reason_code="MALFORMED_RECORD",
                        detail=type(exc).__name__,
                        now=now,
                    ),
                    now,
                )
            )
            path.unlink()
            continue

        if record.get("target_stage") != stage_name:
            continue  # addressed to another stage; leave it where it is

        claimed = processing / f"{stage_name}-{path.name}"
        shutil.move(str(path), str(claimed))

        try:
            result = process(record, now=now)
        except Exception as exc:  # noqa: BLE001 - deliberate stage boundary
            # Log the exception *type* and the id, never the payload.
            result = terminal_envelope(
                record,
                source_stage=stage_name,
                final_status="rejected",
                reason_code="STAGE_ERROR",
                detail=type(exc).__name__,
                now=now,
            )

        outputs.append(_finish(shared_root, stage_name, result, now))
        claimed.unlink()

    return outputs


def _finish(
    shared_root: Path, stage_name: str, result: dict[str, Any], now: datetime | None
) -> dict[str, Any]:
    write_record_atomic(_route(shared_root, result), result)
    data = result.get("data") or {}
    log_event(
        shared_root,
        stage=stage_name,
        transaction_id=transaction_id(result),
        correlation_id=correlation_id(result),
        outcome=data.get("final_status") or f"forwarded:{result.get('target_stage')}",
        now=now,
        **_audit_fields(result),
    )
    return result
