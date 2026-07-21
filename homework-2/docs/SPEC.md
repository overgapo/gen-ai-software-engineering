# Resolved Specification — Intelligent Customer Support System

This document is the **binding specification** for Homework 2. It merges the original assignment (`../TASKS.md`) with explicit decisions that close its gaps and contradictions. Where this document and `TASKS.md` disagree, this document wins — every deviation is listed in [Deviations from TASKS.md](#deviations-from-tasksmd).

## 1. Stack & storage

- **Backend:** Node.js ≥ 18, Express, CommonJS. Tests: Jest + supertest.
- **Front-end:** React + Vite.
- **Storage:** in-memory `Map` behind a repository module (`ticketRepository`); no code outside the repository may know the storage mechanism.
- **Persistence:** async JSON snapshot — written to disk after mutations (debounced 100 ms, never synchronously on the request path; atomic write via tmp-file + rename), restored on startup from `data/tickets.json` (gitignored). Snapshotting is **disabled in tests** (`NODE_ENV=test`).

## 2. Ticket model

As specified in `TASKS.md`, extended with the `classification` object:

```json
{
  "id": "UUID (server-generated)",
  "customer_id": "string (optional)",
  "customer_email": "email (required)",
  "customer_name": "string (optional)",
  "subject": "string, 1–200 chars (required)",
  "description": "string, 10–2000 chars (required)",
  "category": "account_access | technical_issue | billing_question | feature_request | bug_report | other",
  "priority": "urgent | high | medium | low",
  "status": "new | in_progress | waiting_customer | resolved | closed",
  "created_at": "datetime (server-generated)",
  "updated_at": "datetime (server-managed)",
  "resolved_at": "datetime | null (server-managed)",
  "assigned_to": "string | null",
  "tags": ["array of strings"],
  "metadata": {
    "source": "web_form | email | api | chat | phone",
    "browser": "string",
    "device_type": "desktop | mobile | tablet"
  },
  "classification": {
    "category": "enum (as above)",
    "priority": "enum (as above)",
    "confidence": "number 0–1",
    "reasoning": "string",
    "keywords": ["matched keywords"],
    "classified_at": "datetime",
    "overridden": "boolean"
  }
}
```

**Field rules:**
- Required on create: `customer_email` (valid email), `subject`, `description`.
- Defaults: `category=other`, `priority=medium`, `status=new`, `tags=[]`, `metadata.source=api`, `assigned_to=null`, `resolved_at=null`, `classification=null`.
- `id`, `created_at`, `updated_at` are server-generated/managed and immutable from the client.
- Client-supplied server-managed fields (`id`, `created_at`, `updated_at`, `resolved_at`, `classification`) are **silently ignored** on create and update — not validation errors. This keeps GET → modify → PUT round-trips working.
- `resolved_at` is server-managed: set on transition to `resolved` or `closed`; cleared to `null` on return to an active status (`new` / `in_progress` / `waiting_customer`). Clients cannot set it.

## 3. API

| Method | Endpoint | Success | Notes |
|--------|----------|---------|-------|
| POST | `/tickets` | 201 | Optional `auto_classify` flag (see §5) |
| POST | `/tickets/import` | 201 | Bulk import, all-or-nothing (see §4) |
| GET | `/tickets` | 200 | Filters below |
| GET | `/tickets/:id` | 200 | 404 if missing |
| PUT | `/tickets/:id` | 200 | **Partial update** (merge semantics) |
| DELETE | `/tickets/:id` | 204 | 404 if missing |
| POST | `/tickets/:id/auto-classify` | 200 | Returns classification result (see §5) |

- **`GET /tickets` filters** (all combinable, AND semantics): `category`, `priority`, `status`, `assigned_to`, `customer_id`, and free-text `search` over `subject` + `description`. Results are sorted newest-first (`created_at` descending).
- **Validation failures** → `400` with a structured body listing per-field errors. Unknown enum values, malformed email, and length violations are validation failures.
- **PUT** accepts any subset of editable fields; absent fields are left unchanged. `updated_at` is refreshed by the server.

## 4. Bulk import

- **Transport:** `multipart/form-data`, file in the `file` field.
- **Format detection:** by file extension (`.csv`, `.json`, `.xml`), falling back to the part's Content-Type. Unknown format, unparseable file, or empty file → `400`.
- **Semantics: all-or-nothing.** Every record is validated first; if all are valid, all are imported (`201`); if **any** record is invalid, **nothing** is imported (`400`). Both responses carry the summary:

```json
{ "total": 50, "successful": 50, "failed": 0, "errors": [] }
```

  `errors[]` items reference the record (index/line) and list its field errors. By design, `successful` is either `total` or `0`.
- **`auto_classify` flag** (query param or form field): when true, every imported ticket is auto-classified after creation.
- **CSV encoding:** one ticket per row; the `tags` and `metadata` columns contain JSON strings (e.g. `"[""vpn"",""urgent""]"`).
- **XML structure:**

```xml
<tickets>
  <ticket>
    <customer_email>a@b.com</customer_email>
    <subject>…</subject>
    <description>…</description>
    <tags><tag>vpn</tag><tag>urgent</tag></tags>
    <metadata><source>email</source><browser>…</browser><device_type>desktop</device_type></metadata>
  </ticket>
</tickets>
```

## 5. Auto-classification

**Categories** (keyword-based): `account_access` (login, password, 2FA), `technical_issue` (bugs, errors, crashes), `billing_question` (payments, invoices, refunds), `feature_request` (enhancements, suggestions), `bug_report` (defects **with reproduction markers**), `other` (no match).

- **`technical_issue` vs `bug_report` disambiguation:** `bug_report` only when the text contains reproduction markers — "steps to reproduce", "expected"/"actual" behavior, numbered step lists. Otherwise error/crash/bug language → `technical_issue`.

**Priority keywords:** urgent — "can't access", "critical", "production down", "security"; high — "important", "blocking", "asap"; low — "minor", "cosmetic", "suggestion"; medium — default when nothing matches.

- **Conflict resolution:** the priority level with the **most keyword matches** wins; ties go to the higher level (urgent > high > low). Category ties resolve by definition order (`account_access` → `technical_issue` → `billing_question` → `feature_request`); the confidence formula reflects the ambiguity in such cases.

**Confidence** (deterministic): based on winning-category matches penalized by competing-category matches — `matches / (matches + competing)` — clamped to `[0.3, 0.95]`; `other` → ≤ 0.3.

**Behavior:**
- `POST /tickets/:id/auto-classify` always applies the result: overwrites `category` and `priority`, stores the full result in `classification`, resets `overridden` to `false`.
- On create with `auto_classify=true`: if the client supplied `category`/`priority`, the supplied values are kept (manual wins) — the classification is still computed and stored in `classification`, with `overridden=true`.
- A later manual change of `category`/`priority` via PUT sets `classification.overridden = true`.
- **Decision logging:** every classification decision is written as a structured JSON log entry (`ticket_id`, resulting category/priority, confidence, keywords, timestamp). The latest result lives in `ticket.classification`; there is no separate history store or endpoint.

## 6. Testing

- **Structure per `TASKS.md` Task 3** (api 11, model 9, csv 6, json 5, xml 5, categorization 10, integration 5, performance 5, + `fixtures/`).
- **Task 6 scenarios are separate additional files** (e.g. `test_e2e`): full ticket lifecycle, bulk import + classification verification, 20+ concurrent requests, combined category+priority filtering.
- **Coverage gate:** ≥ 85% **lines and statements**, enforced via Jest `coverageThreshold`; branches/functions reported but not gated.
- **Browser-level UI tests** (added after a live-testing gap was found): a separate suite (`tests/ui/`, `npm run test:ui`) drives headless Chrome via puppeteer-core against a spawned server. Kept out of `npm test` and the coverage gate; skips itself when no local Chrome is found (`CHROME_PATH` to override).
- **Performance thresholds** (generous by design to avoid flakes; measured actuals go into TESTING_GUIDE's benchmarks table):

| Benchmark | Threshold |
|-----------|-----------|
| Single ticket create | < 50 ms |
| List 1000 tickets | < 200 ms |
| Import 100 records | < 2 s |
| Single classification | < 20 ms |
| 20 concurrent requests | < 3 s total |

## 7. Front-end (Task 5)

React + Vite app consuming the real API (no hardcoded data): ticket list with category/priority/status filters, create/edit forms with client-side validation, ticket detail view (including `classification`), bulk-import upload, auto-classify trigger with result display, clear success/error feedback, responsive layout.

## 8. Documentation deliverables

Exactly **four** Task 4 documents: `README.md`, `API_REFERENCE.md`, `ARCHITECTURE.md`, `TESTING_GUIDE.md` (≥ 3 Mermaid diagrams across them). `HOWTORUN.md` is additionally required by the course rules. Sample data: `sample_tickets.csv` (50), `sample_tickets.json` (20), `sample_tickets.xml` (30), plus invalid files for negative tests.

## Deviations from TASKS.md

Deliberate, agreed-with-the-author deviations — not oversights:

1. **Task 4 says "5 documentation files" but lists 4** — treated as a typo; exactly the four listed documents are produced.
2. **Import is all-or-nothing**, whereas `TASKS.md`'s summary format ("successful, failed") implies partial success. The summary structure is preserved (`successful` is `total` or `0`), and per-record error details are still returned on failure.
3. **The ticket model is extended** with a `classification` object — required to satisfy Task 2 ("store classification confidence") and Task 5 ("view classification results"), which the original model has no fields for.
