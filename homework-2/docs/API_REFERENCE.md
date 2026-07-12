# API Reference

REST API for the Intelligent Customer Support System. Base URL in local development: `http://localhost:3000`. All request/response bodies are JSON unless noted otherwise.

## Endpoints

| Method | Endpoint | Success | Description |
|--------|----------|---------|-------------|
| GET | `/health` | 200 | Liveness check |
| POST | `/tickets` | 201 | Create a ticket (`?auto_classify=true` optional) |
| POST | `/tickets/import` | 201 | Bulk import CSV/JSON/XML (all-or-nothing) |
| GET | `/tickets` | 200 | List tickets with filtering |
| GET | `/tickets/:id` | 200 | Get one ticket |
| PUT | `/tickets/:id` | 200 | Partial update |
| DELETE | `/tickets/:id` | 204 | Delete a ticket |
| POST | `/tickets/:id/auto-classify` | 200 | Classify and apply category/priority |

## Ticket model

```json
{
  "id": "3f9e0f6a-…",
  "customer_id": "CUST-1001",
  "customer_email": "jane@example.com",
  "customer_name": "Jane Doe",
  "subject": "Cannot log in",
  "description": "My password is rejected…",
  "category": "account_access",
  "priority": "urgent",
  "status": "new",
  "created_at": "2026-07-08T12:00:00.000Z",
  "updated_at": "2026-07-08T12:00:00.000Z",
  "resolved_at": null,
  "assigned_to": null,
  "tags": ["auth"],
  "metadata": { "source": "web_form", "browser": "Chrome", "device_type": "desktop" },
  "classification": {
    "category": "account_access",
    "priority": "urgent",
    "confidence": 0.95,
    "reasoning": "category \"account_access\": matched \"login\"…",
    "keywords": ["login", "password"],
    "classified_at": "2026-07-08T12:00:01.000Z",
    "overridden": false
  }
}
```

**Enums**

| Field | Values |
|-------|--------|
| `category` | `account_access`, `technical_issue`, `billing_question`, `feature_request`, `bug_report`, `other` |
| `priority` | `urgent`, `high`, `medium`, `low` |
| `status` | `new`, `in_progress`, `waiting_customer`, `resolved`, `closed` |
| `metadata.source` | `web_form`, `email`, `api`, `chat`, `phone` |
| `metadata.device_type` | `desktop`, `mobile`, `tablet` |

**Field rules**

- Required on create: `customer_email` (valid email), `subject` (1–200 chars), `description` (10–2000 chars).
- Defaults: `category=other`, `priority=medium`, `status=new`, `tags=[]`, `metadata.source=api`.
- Server-managed and silently ignored if sent by a client: `id`, `created_at`, `updated_at`, `resolved_at`, `classification`.
- `resolved_at` is set automatically on transition to `resolved`/`closed` and cleared when the ticket returns to an active status.

## Error format

Validation failures return `400`:

```json
{
  "error": "Validation failed",
  "details": [
    { "field": "customer_email", "message": "must be a valid email address" },
    { "field": "subject", "message": "is required" }
  ]
}
```

Unknown ids return `404` with `{ "error": "Ticket not found" }`. Malformed JSON bodies return `400` with `{ "error": "Invalid JSON body" }`.

## Create a ticket

```bash
curl -X POST http://localhost:3000/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_email": "jane@example.com",
    "subject": "Cannot log in",
    "description": "My password is rejected and I cannot access my account."
  }'
```

With auto-classification (client-supplied `category`/`priority` win; the classifier fills the rest and records its result in `classification`):

```bash
curl -X POST 'http://localhost:3000/tickets?auto_classify=true' \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_email": "ops@example.com",
    "subject": "Production down",
    "description": "Every request fails with an error since the update. Critical!"
  }'
```

## List tickets

All filters combine with AND. Results are sorted newest-first.

| Query param | Meaning |
|-------------|---------|
| `category`, `priority`, `status` | Exact enum match (unknown values → `400`) |
| `assigned_to`, `customer_id` | Exact match |
| `search` | Case-insensitive substring over `subject` + `description` |

```bash
curl 'http://localhost:3000/tickets?category=account_access&priority=urgent&search=login'
```

## Get / update / delete

```bash
curl http://localhost:3000/tickets/<id>

# PUT is a partial update — send only the fields you change
curl -X PUT http://localhost:3000/tickets/<id> \
  -H 'Content-Type: application/json' \
  -d '{ "status": "resolved", "assigned_to": "agent-7" }'

curl -X DELETE http://localhost:3000/tickets/<id>   # 204 on success
```

## Auto-classify

Always applies the result (overwrites `category` and `priority`, sets `classification.overridden=false`). Returns the updated ticket.

```bash
curl -X POST http://localhost:3000/tickets/<id>/auto-classify
```

Response fields inside `classification`: `category`, `priority`, `confidence` (0–1), `reasoning` (human-readable), `keywords` (matched terms), `classified_at`, `overridden`.

## Bulk import

`multipart/form-data` with the file in the `file` field. Format is detected by extension (`.csv`, `.json`, `.xml`) with a Content-Type fallback. **Import is all-or-nothing**: if any record fails validation, nothing is persisted.

```bash
# success -> 201
curl -X POST 'http://localhost:3000/tickets/import?auto_classify=true' \
  -F 'file=@demo/sample_tickets.csv'
```

```json
{ "total": 50, "successful": 50, "failed": 0, "errors": [] }
```

```bash
# any invalid record -> 400, nothing imported
curl -X POST http://localhost:3000/tickets/import -F 'file=@demo/invalid_tickets.csv'
```

```json
{
  "error": "Import failed",
  "total": 3,
  "successful": 0,
  "failed": 2,
  "errors": [
    {
      "record": 2,
      "details": [{ "field": "customer_email", "message": "must be a valid email address" }]
    }
  ]
}
```

Unparseable, empty, or unknown-format files return `400` with `{ "error": "Import failed", "reason": "…" }`.

**File formats**

- **CSV** — header row + one ticket per row; `tags` and `metadata` columns contain JSON strings:

  ```csv
  customer_email,subject,description,tags,metadata
  a@b.com,Login issue,"Cannot access my account.","[""auth""]","{""source"":""web_form""}"
  ```

- **JSON** — an array of ticket objects.
- **XML** — `<tickets>` root with `<ticket>` elements; `tags` nest as `<tags><tag>…</tag></tags>`, `metadata` as child elements.

See ready-made examples in [`../demo/`](../demo/) and [`../demo/sample-requests.http`](../demo/sample-requests.http).
