# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`homework-2` is one assignment in a university course ("GenAI and Agentic AI for Software Engineering"). The parent repo (`../`) is a homework template with one directory per assignment (`homework-1` … `homework-6`). The application — an Express ticket API + React (Vite) front-end — is **implemented**: backend in `src/` (routes → services → repository layering), client in `client/`, tests in `tests/`, sample data and run scripts in `demo/`.

## Commands

```bash
npm test                  # full suite (Jest + supertest, ~1s)
npx jest test_import_csv  # single suite; -t "name" for single test
npm run test:coverage     # enforces ≥85% lines/statements gate
npm run test:ui           # browser UI e2e (puppeteer-core + local Chrome; auto-skips without Chrome)
npm start                 # serve API + built client on :3000
npm run dev               # same, auto-restart on changes
cd client && npm run build   # rebuild the front-end (Express serves client/dist)
cd client && npm run dev     # Vite dev server on :5173, proxies to :3000
./demo/run.sh             # install + build + start + seed 100 sample tickets
node demo/generate-samples.js  # regenerate sample data deliverables
```

Tests must never touch `data/` — snapshotting is disabled under `NODE_ENV=test` (Jest sets it automatically); always construct `createApp({ repository: new TicketRepository() })` in tests.

## The specification (read `docs/SPEC.md` before implementing)

**`docs/SPEC.md` is the binding, canonical spec** — it merges the original assignment (`TASKS.md`) with explicitly agreed decisions that close the assignment's gaps and contradictions (the original `TASKS.md` is ambiguous in ~16 places; all were resolved with the author). Where they disagree, `SPEC.md` wins; its "Deviations from TASKS.md" section lists the deliberate departures. Do not re-decide anything settled there — if a new gap appears, ask, then record the decision in `SPEC.md`.

**`docs/PLAN.md` is the execution roadmap** — 11 dependency-ordered phases, each with a "Done when" gate. Work through it in order and don't mark a phase done until its gate passes.

Build an **Intelligent Customer Support System**: a ticket-management REST API plus a web front-end. Chosen stack: **Node.js ≥18 + Express backend (CommonJS, Jest + supertest, as in `../homework-1`) and a React front-end built with Vite**.

Six tasks:

1. **Ticket CRUD API** — `POST/GET/PUT/DELETE /tickets`, `GET /tickets/:id`, plus `POST /tickets/import` for bulk import from **CSV, JSON, and XML**. Import returns a summary (total / successful / failed with per-record error details). Validate email format, string lengths (`subject` 1–200, `description` 10–2000), and enums; validation failures → `400`, creation → `201`, missing → `404`.
2. **Auto-classification** — `POST /tickets/:id/auto-classify` assigns one of six categories (`account_access`, `technical_issue`, `billing_question`, `feature_request`, `bug_report`, `other`) and a priority via keyword rules (urgent: "can't access"/"critical"/"production down"/"security"; high: "important"/"blocking"/"asap"; low: "minor"/"cosmetic"/"suggestion"; medium: default). Response includes category, priority, confidence (0–1), reasoning, and keywords found. Must support an optional auto-run-on-create flag, manual override, and decision logging.
3. **Test suite** — >85% coverage, organized per the file layout in `TASKS.md` (api, model, csv/json/xml import, categorization, integration, performance + `fixtures/`).
4. **Multi-level documentation** — `README.md`, `API_REFERENCE.md`, `ARCHITECTURE.md`, `TESTING_GUIDE.md`, with ≥3 Mermaid diagrams across them.
5. **Front-end** — ticket list with category/priority/status filtering, create/edit forms with client-side validation, detail view, bulk-import upload, auto-classify trigger with result display. Must consume the real API (no hardcoded data) and be responsive.
6. **Integration & performance tests** — full ticket lifecycle, bulk import + classification verification, 20+ concurrent requests, combined filters.

The full contract — ticket model (extended with a `classification` object), endpoint semantics, import rules, classification algorithm, and test thresholds — lives in `docs/SPEC.md`. The decisions most likely to be violated by habit:

- **Import is all-or-nothing** (deliberate deviation from `TASKS.md`): any invalid record → `400`, nothing persisted; summary `{total, successful, failed, errors[]}` returned either way.
- **Storage:** in-memory Map behind `ticketRepository` + debounced async JSON snapshot (restored on startup, **disabled in tests**, gitignored data dir). Never write the snapshot synchronously on the request path.
- **Manual wins over auto-classification** on create; explicit `POST /tickets/:id/auto-classify` always overwrites.
- **`PUT` is a partial update**; `resolved_at` is server-managed (set on `resolved`/`closed`, cleared on reopen).
- **Coverage gate:** ≥85% lines+statements via Jest `coverageThreshold`.

## Required deliverables (grading depends on these)

Per the parent `../README.md`, a submission is incomplete without all of:
- `README.md` — solution overview, author, and AI-tools-used sections (skeleton exists; author placeholders and implementation sections must be filled in before submission)
- `HOWTORUN.md` — step-by-step run instructions (does not exist yet — create it)
- Coverage report screenshot at `docs/screenshots/test_coverage.png` and UI screenshot at `docs/screenshots/ui.png`, plus screenshots of AI interactions
- Sample data files: `sample_tickets.csv` (50), `sample_tickets.json` (20), `sample_tickets.xml` (30), and invalid files for negative tests
- `demo/` — runnable demo scripts (homework-1 shipped `run.sh`/`run.bat` and sample requests; follow that pattern)

## Submission workflow

Work happens on a fork. Each assignment is submitted as its own branch + **detailed** pull request:
- Branch name: `homework-2-submission`
- The PR body is the primary submission narrative — must include a thorough summary, how AI was used, how to verify, and embedded screenshots. Bare/one-line PRs are rejected.
- PRs target the **student's own fork** (`main`), never the upstream course repo. Reviewer: `Alexey-Popov`.

Keep the project self-contained inside `homework-2/` (its own `package.json`, `node_modules` ignored via the repo root `.gitignore`).
