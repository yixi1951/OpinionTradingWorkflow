#!/usr/bin/env bash
# One-shot offline demo: OpenClaw stub gateway + keyword replay (no live API keys).
#
# Usage:
#   bash scripts/run_demo.sh
#   bash scripts/run_demo.sh --skip-ui
#   bash scripts/run_demo.sh --with-wf
#
# Env (optional): DEMO_DATE=2026-06-17, OPENCLAW_STUB_PORT=18790

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_UI=0
WITH_WF=0
STUB_PORT="${OPENCLAW_STUB_PORT:-18790}"
DEMO_DATE="${DEMO_DATE:-2026-06-17}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-ui) SKIP_UI=1; shift ;;
    --with-wf) WITH_WF=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
else
  PYTHON="${PYTHON:-python3}"
  echo "Tip: create .venv for reproducible deps (see docs/DEV_SETUP.md)" >&2
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export SCORING_MODE="${SCORING_MODE:-keyword}"
export OPENCLAW_SKIP_ROW_SCORE="${OPENCLAW_SKIP_ROW_SCORE:-1}"
export USE_LLM_GATEWAY="${USE_LLM_GATEWAY:-0}"

mkdir -p data/raw data/memory data/reports

if [[ ! -f "data/raw/raw_posts_${DEMO_DATE}.csv" ]]; then
  if [[ -f "tests/fixtures/raw_posts_smoke_min.csv" ]]; then
    cp "tests/fixtures/raw_posts_smoke_min.csv" "data/raw/raw_posts_${DEMO_DATE}.csv"
  elif [[ -f "tests/fixtures/raw_posts_${DEMO_DATE}.csv" ]]; then
    cp "tests/fixtures/raw_posts_${DEMO_DATE}.csv" "data/raw/raw_posts_${DEMO_DATE}.csv"
  else
    echo "Missing raw fixture for ${DEMO_DATE}" >&2
    exit 1
  fi
fi

STUB_PID=""
cleanup() {
  if [[ -n "${STUB_PID}" ]] && kill -0 "${STUB_PID}" 2>/dev/null; then
    kill "${STUB_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "=== [1/4] OpenClaw sentiment stub on :${STUB_PORT} ==="
OPENCLAW_URL="http://127.0.0.1:${STUB_PORT}" \
  "${PYTHON}" -m uvicorn openclaw_stub:app --host 127.0.0.1 --port "${STUB_PORT}" &
STUB_PID=$!
sleep 1

echo "=== [2/4] Gateway health (stub URL) ==="
OPENCLAW_URL="http://127.0.0.1:${STUB_PORT}" \
  "${PYTHON}" scripts/check_gateway_health.py || true

echo "=== [3/4] Keyword fast-daily replay (${DEMO_DATE}) ==="
"${PYTHON}" -m opinion_trading.main --mode daily --date "${DEMO_DATE}" --fast-daily

if [[ "${WITH_WF}" -eq 1 ]]; then
  echo "=== [3b] Walk-forward on replay fixture price table ==="
  "${PYTHON}" -m opinion_trading.main --mode walk_forward \
    --price-file tests/fixtures/price_history_replay.csv
fi

echo "=== [4/4] Artifacts ==="
test -f data/memory/state.json
echo "  state.json OK"
if compgen -G "data/reports/realtime_picks_*.md" > /dev/null; then
  echo "  realtime picks OK"
fi

if [[ "${SKIP_UI}" -eq 0 ]]; then
  echo "Launching Streamlit (Ctrl+C stops UI; stub stops on exit) ..."
  exec bash scripts/run_ui.sh --skip-demo --no-browser
else
  echo "Demo pipeline complete (--skip-ui). Open UI with: bash scripts/run_ui.sh"
fi
