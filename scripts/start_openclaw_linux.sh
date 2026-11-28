#!/usr/bin/env bash
# Start OpenClaw gateway + HTTP sentiment proxy on Linux (Cloud Agent / server).
#
# Prerequisites:
#   - Node >= 24.16 (nvm recommended)
#   - openclaw installed (e.g. npm i openclaw in ~/.local/openclaw-app)
#   - onboarded once: openclaw onboard --non-interactive --mode local \
#       --auth-choice deepseek-api-key --deepseek-api-key "$DEEPSEEK_API_KEY" \
#       --accept-risk --no-install-daemon
#
# Usage:
#   bash scripts/start_openclaw_linux.sh
#   export OPENCLAW_URL=http://127.0.0.1:18790
#   PYTHONPATH=src python3 scripts/validate_raw_openclaw.py --since 2026-11-01 --max-total-rows 40

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OC_APP="${OPENCLAW_APP_DIR:-$HOME/.local/openclaw-app}"
OC_BIN="${OC_APP}/node_modules/.bin/openclaw"
GW_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
PROXY_PORT="${OPENCLAW_PROXY_PORT:-18790}"

if [[ ! -x "$OC_BIN" ]]; then
  echo "openclaw CLI not found at $OC_BIN" >&2
  echo "Install Node 24.16+, then: mkdir -p $OC_APP && cd $OC_APP && npm i openclaw" >&2
  exit 1
fi

# Prefer nvm Node 24 if present (openclaw requires >=24.16).
if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  . "$HOME/.nvm/nvm.sh"
  nvm use 24.16.0 >/dev/null 2>&1 || nvm use 24 >/dev/null 2>&1 || true
  export PATH="$HOME/.nvm/versions/node/$(node -v | tr -d v)/bin:$PATH"
fi

CFG="$HOME/.openclaw/openclaw.json"
if [[ ! -f "$CFG" ]]; then
  echo "Missing $CFG — run openclaw onboard first." >&2
  exit 1
fi

TOKEN="$(python3 -c "import json; from pathlib import Path; print(json.loads(Path.home().joinpath('.openclaw/openclaw.json').read_text())['gateway']['auth']['token'])")"
MODEL="$(python3 -c "import json; from pathlib import Path; c=json.loads(Path.home().joinpath('.openclaw/openclaw.json').read_text()); m=c.get('agents',{}).get('defaults',{}).get('model'); print(m.get('primary') if isinstance(m,dict) else (m or 'deepseek/deepseek-v4-pro'))")"

# Enable OpenAI-compatible HTTP (shared token gets full operator scopes).
"$OC_BIN" config set gateway.http.endpoints.chatCompletions.enabled true --strict-json >/dev/null || true

echo "Starting gateway on :$GW_PORT ..."
"$OC_BIN" gateway run --port "$GW_PORT" --force --allow-unconfigured > /tmp/openclaw_gateway.log 2>&1 &
echo $! >/tmp/openclaw_gateway.pid

for _ in $(seq 1 60); do
  if curl -sf -m 1 "http://127.0.0.1:${GW_PORT}/ready" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf -m 2 "http://127.0.0.1:${GW_PORT}/ready" >/dev/null || {
  echo "Gateway failed to become ready; see /tmp/openclaw_gateway.log" >&2
  exit 1
}

echo "Starting proxy on :$PROXY_PORT (HTTP completions path) ..."
cd "$ROOT"
export WS_GATEWAY_URL="ws://127.0.0.1:${GW_PORT}"
export WS_GATEWAY_TOKEN="$TOKEN"
export WS_GATEWAY_MODEL="$MODEL"
export OPENCLAW_PROXY_VIA_HTTP=1
export OPENCLAW_GATEWAY_HTTP_URL="http://127.0.0.1:${GW_PORT}"
export WS_GATEWAY_RESPONSE_TIMEOUT=180
python3 -m uvicorn openclaw_ws_proxy:app --host 127.0.0.1 --port "$PROXY_PORT" > /tmp/openclaw_proxy.log 2>&1 &
echo $! >/tmp/openclaw_proxy.pid
sleep 2

export OPENCLAW_URL="http://127.0.0.1:${PROXY_PORT}"
echo "OPENCLAW_URL=$OPENCLAW_URL"
python3 - <<'PY'
import os, requests
url=os.environ["OPENCLAW_URL"]
r=requests.post(url+"/api/v1/sentiment", json={"texts":["茅台业绩超预期看好买入"]}, timeout=120)
print("smoke", r.status_code, r.text[:200])
r.raise_for_status()
PY
echo "OK — use: export OPENCLAW_URL=$OPENCLAW_URL"
