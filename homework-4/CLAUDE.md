# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`homework-4` is one assignment in a university course ("GenAI and Agentic AI for Software Engineering"). The parent repo (`../`) is a homework template with one directory per assignment (`homework-1` … `homework-6`); each is self-contained with its own `CLAUDE.md`, so do not carry another assignment's stack or commands into here.

This directory is currently **unimplemented** — the only file is `TASKS.md`, the binding assignment brief. Read it first; everything below summarizes and disambiguates it.

## The assignment in one sentence

Build an **agentic bug-fix pipeline** — a chain of Claude Code sub-agents (`*.agent.md`) plus their skills (`*.md`) — *and* a small **sample app** for the pipeline to operate on, then run the pipeline end-to-end and commit the evidence (artifacts + screenshots).

Two things are being built at once, and they must not be confused:
- **The tooling**: the agents/skills that *do* the work (the actual deliverable being graded).
- **The subject**: a deliberately-buggy mini app in `src/` that the tooling *acts on* to produce demonstrable before/after results.

## Architecture: agents communicate through artifact files, not calls

This is the big picture that isn't obvious from any single file. Each agent is a markdown prompt that **reads one or more artifact files and writes the next one**. The pipeline is a file-based data flow, not an API:

```
Bug Researcher      →  research/codebase-research.md
Research Verifier   →  research/verified-research.md      (verifies the above; uses research-quality skill)
Bug Planner         →  implementation-plan.md
Bug Fixer           →  fix-summary.md                     (applies plan, runs tests)
Security Verifier   →  security-report.md                 (reads fix-summary + changed files; report only, no edits)
Unit Test Generator →  test-report.md + test files        (reads fix-summary + changed files; uses FIRST skill)
```

Run order (from `TASKS.md`): Researcher → Research Verifier → Planner → Fixer → Security Verifier and Unit Test Generator (the last two both branch off the Fixer's output and can run against the changed code independently).

**Upstream vs. the required 4 (resolved):** "Upstream" is a *position in the chain*, not an agent type — all six are the same `*.agent.md` form. Researcher and Planner are upstream = they **generate** the initial artifacts (`codebase-research.md`, `implementation-plan.md`) from `src/` + the `bug-context.md` files. The required 4 are downstream = they **verify / execute / review** what already exists. That's the real distinction: upstream produces input from scratch; the required 4 consume a prior agent's artifact. `TASKS.md` only mandates the 4 because it implicitly assumes research and plan are already given — but our single-command pipeline must run end-to-end, so we **author all six** (see Resolved contract §3) rather than hand-writing the upstream artifacts as fixtures.

## Hard requirements that are easy to miss

1. **Single-command execution.** The whole pipeline must run from *one* command (e.g. `npm run pipeline` or `./run-pipeline.sh`) that starts the agents in order and loads their skills automatically. No manual per-agent invocation between steps. Design the orchestration for this from the start — retrofitting it is painful.
2. **Explicit per-agent model selection.** Every `*.agent.md` frontmatter must name a model chosen to fit the task (stronger reasoning for research verification and security review; faster/cheaper for routine fixes or test scaffolding), and the homework README must justify each choice. See "Model IDs" in the environment notes for current identifiers; default to the latest Claude models.
3. **Two skills are mandatory, and the agents must actually use them:**
   - `skills/research-quality-measurement.md` — defines research-quality levels/labels; the Research Verifier writes `verified-research.md` using it. Required result sections: Verification Summary, Verified Claims, Discrepancies Found, Research Quality Assessment, References.
   - `skills/unit-tests-FIRST.md` — defines **FIRST** (Fast, Independent, Repeatable, Self-validating, Timely); the Unit Test Generator must follow it.
4. **The sample app must ship broken.** `src/` needs **≥2 intentional bugs** and **≥1 intentional security issue**, each documented in `context/bugs/XXX/bug-context.md`. Keep the stack minimal (single language, few deps), with a runnable entry point and a working test command. After a pipeline run, the *same* app demonstrates the fixes and passes tests, including the agent-generated ones.
5. **Security Verifier and Unit Test Generator have different write scopes.** The Security Verifier produces a *report only* — it must not edit code. The Unit Test Generator writes new test files. Keep those boundaries in the agent prompts.

## Resolved contract (binding — don't quietly re-decide)

These decisions are locked. If a later step wants to contradict one, say so out loud and get a new decision.

1. **App stack: Node.js + Express, in-memory, minimal deps.** No database — store data in an in-memory array/object (matches the sibling assignments' approach). Tests via **Jest**; `npm test` must work. Server listens on port **3000** (`PORT` env, default 3000). The subject app is a small **expense-tracker REST API**.
2. **Orchestration: a single `run-pipeline.sh` Bash script.** It invokes each agent in order, loads that agent's skill(s), and passes the artifact files along the chain. This is the one required single-command entry point — no `npm run pipeline` wrapper on top.
3. **Author all six agents.** The full chain is built as `*.agent.md`: Bug Researcher and Bug Planner (upstream, cheaper models for exploration/planning) plus the four required agents. The upstream artifacts are *generated by their agents*, not hand-written fixtures — so the pipeline is genuinely end-to-end.
4. **Seeded defects** (documented in `context/bugs/001|002|003/bug-context.md`), chosen so the pipeline can realistically find and fix them in one run:
   - **Bug #1 (logic):** `GET /summary` computes the total incorrectly — ignores the active filter or uses the wrong sign, so the returned total disagrees with the listed items.
   - **Bug #2 (validation / boundary):** the date-range filter uses `<` instead of `<=` (drops the boundary record), and/or amount validation wrongly accepts negatives or >2 decimal places.
   - **Security #1:** `DELETE /expenses/:id` authorizes by comparing the API key with `==` against a **hardcoded secret in source** — i.e. a hardcoded secret *and* an insecure (non-constant-time) comparison. Fix moves the secret to env and uses `crypto.timingSafeEqual`.

   These bug picks are the starting design; refine the exact wording once `src/` exists, but keep the counts (≥2 bugs, ≥1 security) and the documentation-in-`bug-context.md` requirement.
5. **Keep all six agents separate — no merging.** Merging an upstream agent into a required one was considered and rejected. In particular, **Researcher and Research Verifier must never be the same agent**: the verifier's job is to independently fact-check *someone else's* claims (this is what Task 1 and the research-quality skill grade), and a self-checking agent makes "Discrepancies Found" meaningless. Planner+Fixer is the only defensible merge, and even then it's not taken — if it ever were, the combined agent would still have to write `implementation-plan.md` to a file before applying it, so the artifact hand-off survives.
6. **Per-agent model selection** (declared in each `*.agent.md` frontmatter as a full model ID, passed to the `claude` CLI via `--model` from `run-pipeline.sh`; justified in `README.md`). Rationale: **Opus** where an error is expensive and independent judgment is graded; **Sonnet** everywhere else. Haiku is intentionally unused — reliability was preferred over a wider cost spread.

   | Agent | Model | Why |
   |-------|-------|-----|
   | Bug Researcher | `claude-sonnet-4-6` | Breadth-first code exploration; balanced quality/cost |
   | Research Verifier | `claude-opus-4-8` | Independent fact-check + quality grading (Task 1 is graded on this) |
   | Bug Planner | `claude-sonnet-4-6` | Designs the before/after fix; plan is later validated by the Fixer's tests |
   | Bug Fixer | `claude-sonnet-4-6` | Applies the plan and runs tests; Sonnet chosen over Haiku for edit reliability |
   | Security Verifier | `claude-opus-4-8` | Security judgment + severity rating; brief calls for stronger reasoning here |
   | Unit Test Generator | `claude-sonnet-4-6` | FIRST tests must cover the boundary case (Bug #2); needs real reasoning |

## Note on `TASKS.md`

The "Expected Project Structure" block in `TASKS.md` is mislabeled `homework-5/` at the top — a copy-paste slip. The work belongs in **`homework-4/`**.

## Repo-wide submission contract (grading gates, from `../README.md`)

- Work on a fork; **one branch per assignment** (`homework-4-submission`); PR targets **your own fork's `main`**, never the upstream course repo. Reviewer: `Alexey-Popov`. (Note: the current checked-out branch is `homework-3-submission` — branch off before starting homework-4 work.)
- The **PR body is the primary submission narrative** and must stand on its own: thorough summary, how AI was used, how to verify, plus 3–5 screenshots. Bare/one-line PRs are rejected even when the branch is complete.
- Required in-repo docs: a proper `README.md` (overview, how to run the pipeline and the app, **author/student info**, and the per-agent model justifications) and `HOWTORUN.md`.
- **Screenshots** go in `docs/screenshots/`: the pipeline run, the fixes applied, the security scan, and the generated unit tests.
- **Commit the agentic folder** — `agents/`, `skills/`, `context/`, and all produced artifacts (`verified-research.md`, `fix-summary.md`, `security-report.md`, `test-report.md`) are part of the deliverable, not scratch output.
