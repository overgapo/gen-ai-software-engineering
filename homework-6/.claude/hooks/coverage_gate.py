#!/usr/bin/env python3
"""PreToolUse hook: block `git push` when test coverage is below the gate.

Claude Code calls this before every Bash tool call. It ignores everything that
is not a push, so the test suite runs once, at the moment it matters.

Protocol: the hook reads the tool call as JSON on stdin and communicates by
exit code -- 0 allows the command, 2 blocks it and shows stderr to Claude.

The threshold is passed to pytest explicitly rather than relying on
`pytest.ini`: a gate that can be lowered by editing the file it reads is not a
gate (agents.md §7).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

COVERAGE_GATE = 80
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

# `git push`, `git -C … push`, `git push --force`, and the same inside a
# compound command (`make test && git push`).
PUSH_RE = re.compile(r"(^|[;&|]\s*)git\b[^;&|]*\bpush\b")


def python_executable() -> str:
    venv = PROJECT_DIR / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on a malformed hook payload

    if payload.get("tool_name") != "Bash":
        return 0

    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not PUSH_RE.search(command):
        return 0

    print(f"coverage gate: running the test suite before push…", file=sys.stderr)
    result = subprocess.run(
        [
            python_executable(), "-m", "pytest",
            "--cov=pipeline", "--cov=orchestrator",
            f"--cov-fail-under={COVERAGE_GATE}",
            "--cov-report=term-missing", "-q",
        ],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        tail = [line for line in result.stdout.splitlines() if "Total coverage" in line]
        print(f"coverage gate: PASS — {tail[-1] if tail else 'suite green'}", file=sys.stderr)
        return 0

    print(
        f"PUSH BLOCKED by the coverage gate (minimum {COVERAGE_GATE}%).\n\n"
        f"{result.stdout[-2500:]}\n{result.stderr[-800:]}\n"
        "Fix the failing tests or raise coverage, then push again. "
        "Do not lower the threshold to get past this.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
