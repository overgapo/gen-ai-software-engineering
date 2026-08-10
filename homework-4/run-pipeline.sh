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

# run_agent <label> <agent-file> <model> <expected-output> [skill-file]
#
# Builds the prompt as: an activation directive + the agent definition + (optionally) the
# agent's skill inlined — that inlining is how skills are "loaded automatically".
#
# The activation directive matters: an *.agent.md file on its own reads as a *description*
# of an agent, and a model handed one will politely ask "what would you like me to do?"
# instead of acting. The directive turns the definition into an order to execute now.
#
# After the agent returns, its expected artifact must exist — `claude` exits 0 even when it
# merely replied with text, so exit status alone cannot tell us the step did its job.
run_agent() {
  local label="$1" agent_file="$2" model="$3" expected="$4" skill_file="${5:-}"

  echo ""
  echo "=============================================================================="
  echo "▶  ${label}   [${model}]"
  echo "=============================================================================="

  local prompt
  prompt="You are running as an autonomous agent inside a non-interactive pipeline.
There is no human available to answer questions: if you reply with a question or with a
description of what you *would* do, this pipeline step FAILS.

Adopt the role defined below and EXECUTE IT NOW against this repository (${ROOT}).
Read the inputs it names, do the work, and WRITE YOUR OUTPUT ARTIFACT TO DISK.

Required artifact for this step: ${expected}

Do not ask for clarification. Do not ask for permission. Do not stop at a summary.
Use your file tools to create the artifact before you finish.

--- BEGIN AGENT DEFINITION ---

"
  prompt+="$(cat "$agent_file")"
  if [ -n "$skill_file" ]; then
    prompt+=$'\n\n--- LOADED SKILL — you MUST follow this ---\n\n'
    prompt+="$(cat "$skill_file")"
    echo "   (skill loaded: ${skill_file})"
  fi

  # Capture the CLI's status instead of letting `set -e` abort mid-function: a bare failure
  # would kill the script before the diagnostics below ever print, leaving the operator with
  # no idea which step died or why. (Seen for real: a mid-stream API stall on step 6.)
  local status=0
  printf '%s' "$prompt" | claude -p \
    --model "$model" \
    --permission-mode acceptEdits \
    --allowedTools $ALLOWED_TOOLS \
    --add-dir "$ROOT" || status=$?

  if [ "$status" -ne 0 ]; then
    echo "" >&2
    echo "------------------------------------------------------------------------------" >&2
    echo "✖  ${label} FAILED — the claude CLI exited with status ${status}." >&2
    echo "   Common causes: a mid-stream API error, or an invalid --model id." >&2
    if [ -e "$expected" ]; then
      echo "   NOTE: ${expected} exists anyway — the agent may have written it before" >&2
      echo "   failing. Inspect it; if it is complete, re-run just this step." >&2
    fi
    echo "------------------------------------------------------------------------------" >&2
    exit 1
  fi

  # Gate: refuse to continue on a step that produced nothing, so a vacuous run can never
  # masquerade as a successful one.
  if [ ! -e "$expected" ]; then
    echo ""
    echo "------------------------------------------------------------------------------" >&2
    echo "✖  ${label} FAILED — expected artifact was not created: ${expected}" >&2
    echo "   The agent returned without writing its output, so downstream agents have no" >&2
    echo "   input. Stopping here rather than running the rest of the chain on nothing." >&2
    echo "------------------------------------------------------------------------------" >&2
    exit 1
  fi

  echo ""
  echo "✔  ${label} complete  →  ${expected}"
}

echo "Starting agentic bug-fix pipeline on the expense-tracker app..."

run_agent "1/6 Bug Researcher"      "$AGENTS/researcher.agent.md"           "$MODEL_RESEARCHER" "research/codebase-research.md"
run_agent "2/6 Research Verifier"   "$AGENTS/research-verifier.agent.md"    "$MODEL_VERIFIER"   "research/verified-research.md" "$SKILLS/research-quality-measurement.md"
run_agent "3/6 Bug Planner"         "$AGENTS/planner.agent.md"              "$MODEL_PLANNER"    "implementation-plan.md"
run_agent "4/6 Bug Fixer"           "$AGENTS/bug-fixer.agent.md"            "$MODEL_FIXER"      "fix-summary.md"
run_agent "5/6 Security Verifier"   "$AGENTS/security-verifier.agent.md"    "$MODEL_SECURITY"   "security-report.md"
run_agent "6/6 Unit Test Generator" "$AGENTS/unit-test-generator.agent.md"  "$MODEL_TESTS"      "test-report.md" "$SKILLS/unit-tests-FIRST.md"

echo ""
echo "=============================================================================="
echo "Pipeline finished. Artifacts:"
echo "  research/codebase-research.md   research/verified-research.md"
echo "  implementation-plan.md          fix-summary.md"
echo "  security-report.md              test-report.md   tests/"
echo "=============================================================================="
echo "Run 'npm test' to confirm the suite is green."
