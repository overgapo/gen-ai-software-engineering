#!/usr/bin/env bash
#
# run-pipeline.sh — single-command agentic bug-fix pipeline.
#
# Runs the six agents in order, each with its task-appropriate model and its skill(s)
# loaded automatically, passing artifacts file-to-file down the chain:
#
#   Bug Researcher      -> research/codebase-research.md
#   Research Verifier   -> research/verified-research.md      (skill: research-quality-measurement)
#   Bug Planner         -> implementation-plan.md
#   Bug Fixer           -> fix-summary.md   (edits src/, runs npm test)
#   Security Verifier   -> security-report.md                 (report only)
#   Unit Test Generator -> test-report.md + tests/*.test.js   (skill: unit-tests-FIRST)
#
# Usage:  ./run-pipeline.sh
#
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"

AGENTS="agents"
SKILLS="skills"

# --- Model selection per agent (justified in README.md) --------------------------------
MODEL_RESEARCHER="claude-sonnet-5"
MODEL_VERIFIER="claude-opus-4-8"
MODEL_PLANNER="claude-sonnet-5"
MODEL_FIXER="claude-sonnet-5"
MODEL_SECURITY="claude-opus-4-8"
MODEL_TESTS="claude-sonnet-5"

# --- Preconditions ---------------------------------------------------------------------
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' CLI not found on PATH." >&2; exit 1; }
[ -d node_modules ] || { echo "Installing dependencies..."; npm install; }
mkdir -p research tests

# Tools each agent may use without prompting. Edits are auto-accepted via the permission
# mode; Bash is scoped to the commands the agents actually need (tests, run, curl checks).
ALLOWED_TOOLS='Read Write Edit Glob Grep Bash(npm:*) Bash(npx:*) Bash(node:*) Bash(curl:*)'

# run_agent <label> <agent-file> <model> [skill-file]
# Builds the prompt from the agent definition, inlines the skill if one is given (this is
# how skills are "loaded automatically"), and runs the agent headlessly.
run_agent() {
  local label="$1" agent_file="$2" model="$3" skill_file="${4:-}"

  echo ""
  echo "=============================================================================="
  echo "▶  ${label}   [${model}]"
  echo "=============================================================================="

  local prompt
  prompt="$(cat "$agent_file")"
  if [ -n "$skill_file" ]; then
    prompt+=$'\n\n---\n\n# LOADED SKILL — you MUST follow this\n\n'
    prompt+="$(cat "$skill_file")"
    echo "   (skill loaded: ${skill_file})"
  fi

  printf '%s' "$prompt" | claude -p \
    --model "$model" \
    --permission-mode acceptEdits \
    --allowedTools $ALLOWED_TOOLS \
    --add-dir "$ROOT"

  echo ""
  echo "✔  ${label} complete."
}

echo "Starting agentic bug-fix pipeline on the expense-tracker app..."

run_agent "1/6 Bug Researcher"      "$AGENTS/researcher.agent.md"           "$MODEL_RESEARCHER"
run_agent "2/6 Research Verifier"   "$AGENTS/research-verifier.agent.md"    "$MODEL_VERIFIER"   "$SKILLS/research-quality-measurement.md"
run_agent "3/6 Bug Planner"         "$AGENTS/planner.agent.md"              "$MODEL_PLANNER"
run_agent "4/6 Bug Fixer"           "$AGENTS/bug-fixer.agent.md"            "$MODEL_FIXER"
run_agent "5/6 Security Verifier"   "$AGENTS/security-verifier.agent.md"    "$MODEL_SECURITY"
run_agent "6/6 Unit Test Generator" "$AGENTS/unit-test-generator.agent.md"  "$MODEL_TESTS"      "$SKILLS/unit-tests-FIRST.md"

echo ""
echo "=============================================================================="
echo "Pipeline finished. Artifacts:"
echo "  research/codebase-research.md   research/verified-research.md"
echo "  implementation-plan.md          fix-summary.md"
echo "  security-report.md              test-report.md   tests/"
echo "=============================================================================="
echo "Run 'npm test' to confirm the suite is green."
