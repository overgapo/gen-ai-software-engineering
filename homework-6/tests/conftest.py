"""Shared fixtures.

Every test that touches the file protocol gets its own ``tmp_path``-backed
``shared/``. Nothing here writes into the project's real ``shared/`` -- a test
that pollutes the demo state would be found during the screenshot run, at the
worst possible moment (agents.md §6.6).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from pipeline import config
from pipeline.models import build_envelope

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_INPUT = PROJECT_ROOT / "sample-transactions.json"

# A fixed clock keeps decided_at/scored_at deterministic. The transaction
# timestamps in fixtures are what the fraud rules read, never this.
FIXED_NOW = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def now() -> datetime:
    return FIXED_NOW


@pytest.fixture
def shared_root(tmp_path: Path) -> Path:
    root = tmp_path / "shared"
    for sub in config.SHARED_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def sample_input() -> Path:
    return SAMPLE_INPUT


def raw_transaction(**overrides: Any) -> dict[str, Any]:
    """A valid raw record; override any field to break exactly one thing."""
    record = {
        "transaction_id": "TXN100",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "description": "Test payment",
        "metadata": {"channel": "online", "country": "US"},
    }
    record.update(overrides)
    return {key: value for key, value in record.items() if value is not ...}


def envelope(target_stage: str = "validator", **overrides: Any) -> dict[str, Any]:
    return build_envelope(
        raw_transaction(**overrides),
        source_stage="orchestrator",
        target_stage=target_stage,
        now=FIXED_NOW,
    )


def write_input(shared_root: Path, record: dict[str, Any]) -> Path:
    path = shared_root / "input" / f"{record['data']['transaction_id']}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path
