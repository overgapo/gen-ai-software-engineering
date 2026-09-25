#!/bin/sh
# Make the coverage gate fail on purpose, so it can be photographed failing.
#
#   ./docs/screenshots/gate_demo.sh break     # add a temporary failing test
#   ./docs/screenshots/gate_demo.sh restore   # remove it
#
# A separate throwaway file is used rather than editing a real test: a new file
# never collides with a cached .pyc, which is what bites when you edit an
# existing test back and forth (see HOWTORUN step 5).
set -e

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO="$DIR/tests/test_zz_gate_demo.py"

case "$1" in
  break)
    cat > "$DEMO" <<'PY'
"""TEMPORARY — proves the coverage gate blocks a push. Delete after capturing."""


def test_settlement_totals_are_wrong_on_purpose():
    from pipeline.settlement import settlement_fee
    from pipeline.models import to_decimal

    # 25 bps of 542.50 is 1.36, not 9.99. This assertion is meant to fail.
    assert settlement_fee(to_decimal("542.50")) == to_decimal("9.99")
PY
    echo "added tests/test_zz_gate_demo.py — the suite is now red on purpose."
    echo "Now ask Claude Code to run:  git push"
    echo "The PreToolUse hook should block it. Screenshot that, then run: $0 restore"
    ;;
  restore)
    rm -f "$DEMO"
    find "$DIR" -name __pycache__ -type d -not -path "$DIR/.venv/*" -exec rm -rf {} + 2>/dev/null || true
    echo "removed the temporary test and cleared bytecode caches."
    echo "Verify with:  .venv/bin/python -m pytest -q"
    ;;
  *)
    echo "usage: $0 break|restore" >&2
    exit 2
    ;;
esac
