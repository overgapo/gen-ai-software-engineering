#!/usr/bin/env bash
# One-command demo: install, build the front-end, start the server and seed it
# with the sample data. Run from anywhere: ./demo/run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-3000}"

echo "==> Installing backend dependencies"
(cd "$ROOT" && npm install --silent)

echo "==> Installing front-end dependencies and building"
(cd "$ROOT/client" && npm install --silent && npm run build --silent)

echo "==> Starting server on port $PORT"
(cd "$ROOT" && PORT="$PORT" node src/server.js) &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

echo "==> Waiting for the server"
for _ in $(seq 1 30); do
  if curl -s "http://localhost:$PORT/health" > /dev/null; then break; fi
  sleep 0.5
done

echo "==> Seeding sample data (with auto-classification)"
for f in sample_tickets.csv sample_tickets.json sample_tickets.xml; do
  echo -n "  $f -> "
  curl -s -X POST "http://localhost:$PORT/tickets/import?auto_classify=true" \
    -F "file=@$ROOT/demo/$f"
  echo
done

echo
echo "==> Demo of the all-or-nothing import (this one is expected to fail):"
echo -n "  invalid_tickets.csv -> "
curl -s -X POST "http://localhost:$PORT/tickets/import" \
  -F "file=@$ROOT/demo/invalid_tickets.csv"
echo

echo
echo "==> Ready: open http://localhost:$PORT in your browser (Ctrl+C to stop)"
wait $SERVER_PID
