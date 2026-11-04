#!/usr/bin/env bash
# Local run: ngrok tunnel -> set PUBLIC_URL -> point Twilio at it -> start server.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8790}"
uv run python scripts/load_keys.py
ngrok http "$PORT" --log=stdout > /tmp/phone-agent-ngrok.log 2>&1 &
NGROK_PID=$!
trap 'kill $NGROK_PID 2>/dev/null' EXIT
for _ in $(seq 1 20); do
  URL=$(curl -s localhost:4040/api/tunnels | python3 -c "import json,sys;t=json.load(sys.stdin)['tunnels'];print(next(x['public_url'] for x in t if x['public_url'].startswith('https')))" 2>/dev/null || true)
  [ -n "$URL" ] && break; sleep 0.5
done
[ -z "${URL:-}" ] && { echo "ngrok did not start; see /tmp/phone-agent-ngrok.log"; exit 1; }
sed -i '' "s#^PUBLIC_URL=.*#PUBLIC_URL=$URL#" .env
uv run python scripts/set_webhook.py
echo "Call your Twilio number now. Ctrl+C to stop."
PORT=$PORT uv run python -m app.server
