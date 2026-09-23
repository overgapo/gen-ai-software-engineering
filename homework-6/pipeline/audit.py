"""Append-only audit trail with PII stripped at the boundary.

The rules here are from spec §6.4 and agents.md §5. They are enforced rather
than documented: ``log_event`` raises instead of writing a line that carries a
plaintext account number or a customer description.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline import config
from pipeline.models import iso8601, json_default, utc_now

# Matches the account format this pipeline accepts. Its only job is to catch a
# plaintext account that slipped into a log field.
_ACCOUNT_RE = re.compile(r"ACC-\d{4}")

# Descriptions are free text a customer typed -- treat them as containing
# anything. Account numbers are allowed as *field names* because the spec's
# audit line carries "source_account": "acct_<hash>"; the regex below is what
# stops a plaintext one from getting through.
_FORBIDDEN_FIELDS = frozenset({"description"})


class AuditViolation(RuntimeError):
    """Raised when a log line would leak PII. Never caught to 'keep going'."""


def hash_account(account: str) -> str:
    """Pseudonymize an account number for logs: ``acct_<sha256[:12]>``.

    Stable across a run, so an analyst can still correlate lines, and
    irreversible, so the log is not a second copy of the account ledger.
    """
    digest = hashlib.sha256(account.encode("utf-8")).hexdigest()
    return f"acct_{digest[:12]}"


def audit_path(shared_root: Path) -> Path:
    return Path(shared_root) / "logs" / config.AUDIT_FILENAME


def log_event(
    shared_root: Path,
    *,
    stage: str,
    transaction_id: str,
    correlation_id: str,
    outcome: str,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Append one JSON line to ``shared/logs/audit.log``.

    Opened in append mode only: a correction is a new line, never an edit to an
    old one.
    """
    forbidden = _FORBIDDEN_FIELDS.intersection(fields)
    if forbidden:
        raise AuditViolation(
            f"refusing to audit-log sensitive field(s): {sorted(forbidden)}"
        )

    entry: dict[str, Any] = {
        "ts": iso8601(now or utc_now()),
        "stage": stage,
        "transaction_id": transaction_id,
        "correlation_id": correlation_id,
        "outcome": outcome,
    }
    entry.update({key: value for key, value in fields.items() if value is not None})

    line = json.dumps(entry, ensure_ascii=False, default=json_default)
    if _ACCOUNT_RE.search(line):
        raise AuditViolation("refusing to audit-log a plaintext account number")

    path = audit_path(shared_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return entry
