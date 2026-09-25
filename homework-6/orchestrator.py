#!/usr/bin/env python3
"""Pipeline orchestrator.

Prepares ``shared/``, fans raw transactions into ``shared/input/``, runs the
four stages in order and reconciles: every input record must reach a terminal
state. A record that is still in flight at the end is a failure, not a warning
-- a stuck transaction is money nobody is looking for.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - `python orchestrator.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import compliance, config, fraud_detector, settlement, validator
from pipeline.models import (
    build_envelope,
    iso8601,
    terminal_envelope,
    utc_now,
    write_record_atomic,
)
from pipeline.reporting import build_summary
from pipeline.stage_runner import run_stage

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_ROOT / "sample-transactions.json"
DEFAULT_SHARED = PROJECT_ROOT / "shared"

STAGES = {
    "validator": validator.process_transaction,
    "fraud_detector": fraud_detector.process_transaction,
    "compliance": compliance.process_transaction,
    "settlement": settlement.process_transaction,
}


class PipelineStateError(RuntimeError):
    """Refuses to mix a new run into the leftovers of an old one."""


def prepare_shared(shared_root: Path, clean: bool = False) -> Path:
    shared_root = Path(shared_root)
    for sub in config.SHARED_SUBDIRS:
        (shared_root / sub).mkdir(parents=True, exist_ok=True)

    if clean:
        # Wipe the contents, not the skeleton: the directory layout is
        # committed (each holds a .gitkeep) and a run should not delete it.
        for sub in config.SHARED_SUBDIRS:
            for path in (shared_root / sub).iterdir():
                if path.name == ".gitkeep":
                    continue
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()

    if not clean:
        leftovers = [
            path
            for sub in ("input", "processing", "output")
            for path in (shared_root / sub).glob("*.json")
        ]
        if leftovers:
            raise PipelineStateError(
                f"{len(leftovers)} record(s) left from a previous run; "
                "re-run with --clean to start fresh"
            )
    return shared_root


def fan_in(
    input_path: Path, shared_root: Path, now: datetime | None = None
) -> list[str]:
    """Write one envelope per raw record into ``shared/input/``."""
    with Path(input_path).open("r", encoding="utf-8") as handle:
        raw_records = json.load(handle)
    if not isinstance(raw_records, list):
        raise ValueError("input file must contain a JSON array of transactions")

    accepted: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            txn_id = f"MALFORMED-{index:03d}"
            record = build_envelope(
                {"transaction_id": txn_id},
                source_stage="orchestrator",
                target_stage="validator",
                now=now,
            )
            write_record_atomic(
                shared_root / "results" / f"{txn_id}.json",
                terminal_envelope(
                    record,
                    source_stage="orchestrator",
                    final_status="rejected",
                    reason_code="MALFORMED_RECORD",
                    detail="record is not a JSON object",
                    now=now,
                ),
            )
            accepted.append(txn_id)
            continue

        txn_id = str(raw.get("transaction_id") or f"UNKNOWN-{index:03d}")
        record = build_envelope(
            dict(raw), source_stage="orchestrator", target_stage="validator", now=now
        )
        if txn_id in seen:
            # A result file is never overwritten, so the duplicate gets its own
            # terminal record rather than replacing the first one.
            dup_id = f"{txn_id}-DUP{index:03d}"
            record["data"]["transaction_id"] = dup_id
            write_record_atomic(
                shared_root / "results" / f"{dup_id}.json",
                terminal_envelope(
                    record,
                    source_stage="orchestrator",
                    final_status="rejected",
                    reason_code="DUPLICATE_TRANSACTION_ID",
                    detail=f"'{txn_id}' already seen in this input file",
                    now=now,
                ),
            )
            accepted.append(dup_id)
            continue

        seen.add(txn_id)
        write_record_atomic(shared_root / "input" / f"{txn_id}.json", record)
        accepted.append(txn_id)
    return accepted


def run_pipeline(
    input_path: Path = DEFAULT_INPUT,
    shared_root: Path = DEFAULT_SHARED,
    clean: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    started_at = iso8601(now or utc_now())
    run_id = str(uuid.uuid4())

    shared_root = prepare_shared(shared_root, clean=clean)
    accepted = fan_in(Path(input_path), shared_root, now=now)

    for stage_name in config.STAGE_ORDER:
        run_stage(shared_root, stage_name, STAGES[stage_name], now=now)

    summary = build_summary(
        shared_root / "results",
        run_id=run_id,
        started_at=started_at,
        expected_total=len(accepted),
    )
    write_record_atomic(shared_root / "results" / config.SUMMARY_FILENAME, summary)
    return summary


# --- CLI --------------------------------------------------------------------

_STATUS_MARK = {"settled": "OK ", "held": "HOLD", "rejected": "REJ "}


def print_summary(summary: dict[str, Any]) -> None:
    print()
    print(f"{'TXN':<12} {'AMOUNT':>12} {'CUR':<4} {'':<5} {'RISK':>5}  REASON")
    print("-" * 88)
    for row in summary["transactions"]:
        risk = "" if row["risk_score"] is None else str(row["risk_score"])
        reason = row["reason_code"] or ""
        if row["signals"]:
            reason = f"{reason} [{', '.join(row['signals'])}]"
        elif row["detail"] and row["final_status"] == "rejected":
            reason = f"{reason} ({row['detail']})"
        print(
            f"{str(row['transaction_id']):<12} {str(row['amount'] or ''):>12} "
            f"{str(row['currency'] or ''):<4} {_STATUS_MARK.get(row['final_status'], '?'):<5} "
            f"{risk:>5}  {reason}"
        )
    print("-" * 88)
    counts = summary["by_status"]
    totals = summary["totals"]
    print(
        f"total={summary['total']}  settled={counts.get('settled', 0)}  "
        f"held={counts.get('held', 0)}  rejected={counts.get('rejected', 0)}"
    )
    print(
        f"settled gross={totals['settled_gross']} {totals['settlement_currency']}  "
        f"fees={totals['fees']}  net={totals['settled_net']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the transaction processing pipeline")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--shared", type=Path, default=DEFAULT_SHARED)
    parser.add_argument("--clean", action="store_true", help="wipe shared/ before running")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)

    try:
        summary = run_pipeline(args.input, args.shared, clean=args.clean)
    except PipelineStateError as exc:
        print(f"refusing to start: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print_summary(summary)

    if not summary["complete"]:
        print(
            f"INCOMPLETE: {summary['expected_total']} record(s) accepted, "
            f"{summary['total']} reached a terminal state",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
