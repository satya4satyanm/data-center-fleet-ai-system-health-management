#!/usr/bin/env bash
# Push this machine's metrics to an already-running hub (no extra ports).
set -e
cd "$(dirname "$0")/.."

HUB="${HUB:-http://127.0.0.1:8888}"

if ! python3 -c "import psutil" 2>/dev/null; then
  pip install -r requirements.txt
fi

echo "  Pushing metrics from this machine to ${HUB}"
echo "  (hub must already be running: python server.py --mode hub)"
echo ""

exec python3 server.py --mode agent --hub "$HUB" --push-only --tag site=local --interval 10
