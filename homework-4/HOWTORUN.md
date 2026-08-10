# How to Run

Step-by-step guide to run the expense-tracker app, its tests, and the six-agent pipeline.

## Prerequisites

- **Node.js ≥ 18** and npm.
- For the pipeline only: the **Claude Code CLI** (`claude`) on your `PATH`, authenticated.
  (The app and tests do **not** need it.)

All commands are run from the `homework-4/` directory.

---

## 1. Install dependencies

```bash
npm install
```

Installs `express` (runtime) plus `jest` and `supertest` (dev/test).

---

## 2. Run the app

```bash
npm start
```

Serves the API on `http://localhost:3000` (override with `PORT=... npm start`). It seeds
three demo expenses on startup so endpoints return something immediately.

Try it in another terminal:

```bash
curl http://localhost:3000/expenses
curl "http://localhost:3000/expenses?category=food"
curl "http://localhost:3000/summary?category=food"
curl -X DELETE -H "x-api-key: <key>" http://localhost:3000/expenses/1
```

### Seeing the seeded bugs (before the pipeline)

```bash
# Bug 001 — summary ignores the filter: the list totals 20.75, the summary reports 60.75
curl "http://localhost:3000/expenses?category=food"   # 2 items, sum 20.75
curl "http://localhost:3000/summary?category=food"    # count 3, total 60.75  ← wrong

# Bug 002 — date range drops the 2026-01-31 record (id 3)
curl "http://localhost:3000/expenses?from=2026-01-01&to=2026-01-31"   # returns ids [1,2] ← id 3 missing

# Bug 003 (security) — deletion is authorized by a secret hardcoded in src/expenses.js
```

Stop the server with `Ctrl+C`.

---

## 3. Run the tests

```bash
npm test
```

Runs Jest against the in-process app (via supertest — no port is bound). Before the pipeline
there are no generated tests yet; after a pipeline run this command proves the fixes.

---

## 4. Run the full pipeline (single command)

```bash
./run-pipeline.sh
```

This runs the six agents in order, each with its own model and its skill(s) loaded, passing
artifacts down the chain. It **edits `src/`** (applies the fixes) and **runs `npm test`**, so
run it on a clean git working tree if you want an easy before/after diff.

> **Tip:** run it in its own terminal. It invokes `claude` six times (2× Opus, 4× Sonnet),
> so it takes a few minutes and consumes tokens.

### Artifacts produced

| File | Written by |
|------|-----------|
| `research/codebase-research.md` | Bug Researcher |
| `research/verified-research.md` | Research Verifier |
| `implementation-plan.md` | Bug Planner |
| `fix-summary.md` | Bug Fixer |
| `security-report.md` | Security Verifier |
| `test-report.md` + `tests/*.test.js` | Unit Test Generator |

### After the run

```bash
npm test    # the suite should be green
git diff src/   # review the fixes the pipeline applied
```

Re-run the "seeing the seeded bugs" curls from step 2 — the summary now respects the filter,
the date range includes the boundary record, and deletion no longer trusts a hardcoded key.

---

## Resetting to the buggy state

The pipeline modifies `src/` and adds `tests/`. To get back to the original broken app:

```bash
git checkout -- src/
git clean -fd tests/ research/
rm -f implementation-plan.md fix-summary.md security-report.md test-report.md
```
