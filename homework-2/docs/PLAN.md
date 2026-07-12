# Implementation Plan

Execution order for building the system defined in [`SPEC.md`](SPEC.md). Phases are ordered by dependency; each ends with a **Done when** gate. Tests are written within the phase that builds the feature (per-phase counts come from `TASKS.md` Task 3), so coverage grows with the code instead of being backfilled.

Standing rule: any design decision made during implementation is recorded in `SPEC.md` **at the moment it is made** — the Task 4 documents (Phase 9) are then generated from SPEC and the actual code, never from memory.

## Layout & dependency decisions

- **Backend at the directory root** (`src/`, `tests/`, root `package.json`) — mirrors homework-1. **Front-end in `client/`** as a separate Vite app with its own `package.json`.
- In production/demo mode Express serves `client/dist` as static files — one process, one port, no CORS.
- Backend dependencies (deliberately minimal): `express`, `multer` (multipart), `csv-parse` (robust quoting — required because CSV cells contain JSON strings), `fast-xml-parser`. UUIDs via built-in `crypto.randomUUID()` — no extra dep. Dev: `jest`, `supertest`.

## Phase 0 — Scaffolding

Root `package.json` + scripts (`start`, `dev`, `test`, `test:coverage`), Jest config with the `coverageThreshold` gate (≥85% lines+statements), directory skeleton (`src/{routes,services,repository,validation,config}`, `tests/fixtures`), `.gitignore` additions (`node_modules`, `coverage`, `data/`, `client/dist`).

**Done when:** `npm test` runs (empty suite) and `npm start` serves a health endpoint.

## Phase 1 — Domain core: validation + repository

- `validation/ticket.js`: create/update rules from SPEC §2 (required fields, email format, lengths, enums, server-managed field protection). Single source of truth for enums.
- `repository/ticketRepository.js`: Map-backed CRUD + filtering; debounced async JSON snapshot (load on startup, write after mutations, disabled when `NODE_ENV=test`).
- Tests: `test_ticket_model` (9).

**Done when:** model tests green; snapshot survives a manual restart; tests leave no files behind.

## Phase 2 — CRUD API

- Express app factory (`app.js` separate from `server.js` listen — needed for supertest).
- Routes: `POST/GET /tickets`, `GET/PUT/DELETE /tickets/:id`; AND-combined filters (`category`, `priority`, `status`, `assigned_to`, `customer_id`, `search`); partial PUT; `resolved_at` transitions; central error middleware producing the structured `400` body; correct 201/200/204/404 codes.
- Tests: `test_ticket_api` (11).

**Done when:** API tests green; manual curl pass over every endpoint matches SPEC §3.

## Phase 3 — Classification engine

- `services/classifier.js`: keyword tables in `config/`, category scoring with the `bug_report` repro-marker rule, priority most-matches/tie-goes-higher resolution, confidence formula (`matches/(matches+competing)` clamped to [0.3, 0.95], `other` ≤ 0.3), human-readable `reasoning`.
- Wire-up: `POST /tickets/:id/auto-classify` (always applies, resets `overridden`); `auto_classify` flag on create (manual values win, result stored with `overridden=true`); PUT on `category`/`priority` sets `overridden`; structured JSON decision log.
- Tests: `test_categorization` (10) — must cover disambiguation, priority conflicts, confidence bounds, and override semantics.

**Done when:** categorization tests green; classifying sample texts by hand gives sensible category/priority/confidence.

## Phase 4 — Bulk import

- `services/importer.js`: per-format parsers (CSV with JSON-in-cell columns, JSON array, XML per SPEC §4) normalizing to one record shape; format detection by extension with Content-Type fallback; **two-pass all-or-nothing** — validate every record first, insert only if zero errors; `{total, successful, failed, errors[]}` summary; `auto_classify` flag applied post-insert.
- Route: `POST /tickets/import` via multer (memory storage); unparseable/empty/unknown-format file → `400`.
- Tests: `test_import_csv` (6), `test_import_json` (5), `test_import_xml` (5) + valid/invalid fixtures in `tests/fixtures/`.

**Done when:** import tests green, including the atomicity case (1 bad record in 50 → 400, repository unchanged).

## Phase 5 — Integration & performance tests (Task 3 closure)

- `test_integration` (5): cross-feature workflows through the HTTP layer.
- `test_performance` (5): the SPEC §6 thresholds (create <50ms, list 1000 <200ms, import 100 <2s, classify <20ms, 20 concurrent <3s).
- Run full coverage; plug any gaps below the 85% gate now, not later.

**Done when:** `npm run test:coverage` passes the threshold; screenshot-able coverage report exists.

## Phase 6 — Front-end (React + Vite, in `client/`)

Build order: API client module → ticket list with filters → detail view (incl. `classification` panel) → create/edit forms with client-side validation mirroring SPEC §2 → import upload with summary/error display → auto-classify button with result display → success/error toasts → responsive pass (mobile breakpoint).

**Done when:** every Task 5 requirement works against the live backend; `vite build` output is served by Express; UI screenshot taken with real imported data.

## Phase 7 — End-to-end tests (Task 6)

- `test_e2e` (separate files per SPEC §6): full lifecycle (create → classify → assign → resolve → close, `resolved_at` checked), import-with-classification verification, 20+ concurrent mixed requests, combined category+priority filtering.

**Done when:** full suite green and still above the coverage gate.

## Phase 8 — Sample data & demo

- Generate `sample_tickets.csv` (50), `sample_tickets.json` (20), `sample_tickets.xml` (30) with realistic, classifier-exercising text; invalid counterparts for negative demos.
- `demo/`: `run.sh` + `run.bat` (install, build client, start, seed via import), `sample-requests.http`.

**Done when:** on a clean clone, `demo/run.sh` brings up the app with data and every sample request succeeds.

## Phase 9 — Documentation

- `API_REFERENCE.md` (endpoints, schemas, error formats, cURL per endpoint), `ARCHITECTURE.md` (component + sequence Mermaid diagrams, design decisions incl. the repository/snapshot and all-or-nothing trade-offs), `TESTING_GUIDE.md` (test pyramid Mermaid, how to run, fixtures, manual checklist, **measured** benchmark table), full `README.md` (author, overview, architecture diagram, setup, structure), `HOWTORUN.md`. ≥3 Mermaid diagrams total.
- Screenshots into `docs/screenshots/`: `test_coverage.png`, `ui.png`, AI-interaction shots.

**Done when:** all six documents exist, cross-link correctly, and match the implemented behavior (verify against SPEC, not memory).

## Phase 10 — Submission

Branch `homework-2-submission`; PR to the fork's `main` with the full narrative (summary, AI workflow, verification steps, embedded screenshots); reviewer `Alexey-Popov`.

**Done when:** PR open, CI-clean (if any), all parent-README deliverables checked off.
