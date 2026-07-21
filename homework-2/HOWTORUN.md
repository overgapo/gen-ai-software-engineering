# How to Run

## Prerequisites

- Node.js ≥ 18 (developed on Node 20)
- npm

No database, Docker, or environment variables required. The server listens on port **3000** (`PORT` env var to override).

## Quickest path (recommended)

```bash
./demo/run.sh        # macOS / Linux
demo\run.bat         # Windows
```

The script installs all dependencies, builds the React front-end, starts the server, seeds it with 100 sample tickets (auto-classified), and demonstrates a rejected all-or-nothing import. Then open **http://localhost:3000**.

## Manual steps

```bash
# 1. Backend
npm install

# 2. Front-end (build once; Express serves client/dist)
cd client && npm install && npm run build && cd ..

# 3. Start
npm start            # or: npm run dev (auto-restart on changes)

# 4. Open the app
open http://localhost:3000

# 5. (optional) Seed sample data
curl -X POST 'http://localhost:3000/tickets/import?auto_classify=true' -F 'file=@demo/sample_tickets.csv'
curl -X POST 'http://localhost:3000/tickets/import?auto_classify=true' -F 'file=@demo/sample_tickets.json'
curl -X POST 'http://localhost:3000/tickets/import?auto_classify=true' -F 'file=@demo/sample_tickets.xml'
```

## Front-end development mode

For hot-reloading UI work, run the API and the Vite dev server side by side:

```bash
npm run dev                # terminal 1 — API on :3000
cd client && npm run dev   # terminal 2 — UI on :5173, proxies /tickets to :3000
```

## Tests

```bash
npm test                # 66 tests, ~1 s
npm run test:coverage   # + coverage report (gate: ≥85% lines/statements)
```

See [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for the full testing guide.

## Data persistence

Tickets live in memory and are snapshotted to `data/tickets.json` (gitignored) — they survive a server restart. Delete that file for a clean slate.

## Trying the API directly

Ready-made requests: [demo/sample-requests.http](demo/sample-requests.http) (VS Code REST Client / IntelliJ HTTP client) or the cURL examples in [docs/API_REFERENCE.md](docs/API_REFERENCE.md).
