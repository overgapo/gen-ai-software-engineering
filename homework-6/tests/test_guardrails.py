"""Tests that assert the *absence* of things (spec §11.3).

A guarantee that depends on nobody ever writing a particular line is stronger
when a test refuses to let them. If one of these fails, the fix is the code --
never a relaxed assertion (agents.md §7).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from pipeline import config
from pipeline.audit import AuditViolation, audit_path, log_event
from orchestrator import run_pipeline
from tests.conftest import FIXED_NOW

PIPELINE_DIR = Path(__file__).resolve().parent.parent / "pipeline"
MONEY_MODULES = sorted(PIPELINE_DIR.glob("*.py"))
ACCOUNT_RE = re.compile(r"ACC-\d{4}")


@pytest.mark.parametrize("module", MONEY_MODULES, ids=lambda p: p.name)
def test_no_float_in_the_money_path(module):
    """No float() call and no float literal anywhere in pipeline/.

    ``isinstance(value, float)`` is fine -- that is how models.to_decimal
    *detects* a float in order to route it through Decimal(repr(...)).
    """
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    offences = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "float":
                offences.append(f"float() call at line {node.lineno}")
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            offences.append(f"float literal {node.value!r} at line {node.lineno}")
    assert not offences, f"{module.name}: " + "; ".join(offences)


@pytest.mark.parametrize("module", MONEY_MODULES, ids=lambda p: p.name)
def test_no_stage_imports_another_stage(module):
    """Stages talk through files, never through imports (agents.md §6.1)."""
    stages = set(config.STAGE_ORDER)
    if module.stem not in stages:
        pytest.skip("not a stage module")
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pipeline"):
            imported.update(alias.name for alias in node.names)
            imported.add((node.module or "").removeprefix("pipeline."))
        elif isinstance(node, ast.Import):
            imported.update(alias.name.removeprefix("pipeline.") for alias in node.names)
    assert not (imported & (stages - {module.stem})), f"{module.stem} imports a sibling stage"


def test_audit_log_has_no_plaintext_accounts(shared_root, sample_input):
    run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW)
    text = audit_path(shared_root).read_text(encoding="utf-8")
    assert text.strip(), "a run with no audit trail is not an auditable run"
    assert not ACCOUNT_RE.search(text)
    assert "acct_" in text  # the hashes are actually there


def test_audit_log_never_carries_a_description(shared_root, sample_input):
    run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW)
    for line in audit_path(shared_root).read_text().splitlines():
        entry = json.loads(line)
        assert "description" not in entry
        assert "Monthly rent payment" not in line


def test_log_event_refuses_a_description(shared_root):
    with pytest.raises(AuditViolation, match="description"):
        log_event(
            shared_root, stage="validator", transaction_id="TXN001",
            correlation_id="c", outcome="rejected", description="Invoice #4471",
        )


def test_log_event_refuses_a_plaintext_account(shared_root):
    with pytest.raises(AuditViolation, match="plaintext account"):
        log_event(
            shared_root, stage="validator", transaction_id="TXN001",
            correlation_id="c", outcome="rejected", counterparty="ACC-1001",
        )


def test_refused_audit_line_is_not_written(shared_root):
    with pytest.raises(AuditViolation):
        log_event(
            shared_root, stage="validator", transaction_id="TXN001",
            correlation_id="c", outcome="rejected", counterparty="ACC-1001",
        )
    assert not audit_path(shared_root).exists()


def test_amounts_survive_a_run_as_strings_not_json_numbers(shared_root, sample_input):
    run_pipeline(sample_input, shared_root, clean=True, now=FIXED_NOW)
    for path in (shared_root / "results").glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for value in _walk(raw):
            assert not isinstance(value, float), f"{path.name} carries a JSON float"


def _walk(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)
    else:
        yield node
