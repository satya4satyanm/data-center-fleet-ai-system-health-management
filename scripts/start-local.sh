#!/usr/bin/env bash
# Run hub + this machine's agent on one computer (for local dev / single-node DC).
set -e
cd "$(dirname "$0")/.."

if ! python3 -c "import psutil" 2>/dev/null; then
  echo "Installing dependencies..."
  pip install -r requirements.txt
fi

PORT="${PORT:-8889}"
HOST="${HOST:-127.0.0.1}"

echo ""
echo "  Starting hub + local agent on http://${HOST}:${PORT}"
echo "  Dashboard: cd frontend && npm run dev  →  http://localhost:5173"
echo ""

exec python3 server.py --mode standalone --host "$HOST" --port "$PORT" --tag site=local --interval 10
