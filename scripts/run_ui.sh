#!/usr/bin/env bash
# One-click Streamlit dashboard (Linux/macOS counterpart of scripts/run_ui.ps1).
#
# Usage:
#   bash scripts/run_ui.sh
#   bash scripts/run_ui.sh --port 8502
#   bash scripts/run_ui.sh --no-browser
#   bash scripts/run_ui.sh --with-demo
#   bash scripts/run_ui.sh --skip-demo
#
# Defaults: activate .venv if present, export PYTHONPATH=src, bind http://localhost:8501.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT=8501
NO_BROWSER=0
WITH_DEMO=0
SKIP_DEMO=0
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage: bash scripts/run_ui.sh [options] [-- extra streamlit args]

  --port N        Streamlit port (default 8501)
  --no-browser    Do not open a browser
  --with-demo     Force a keyword fast-daily replay before launch
  --skip-demo     Skip auto-replay even if no realtime picks exist
  -h, --help      Show this help

Env: PYTHONPATH is set to <repo>/src. Uses .venv/bin/python when present.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --port=*)
      PORT="${1#--port=}"
      shift
      ;;
    --no-browser)
      NO_BROWSER=1
      shift
      ;;
    --with-demo)
      WITH_DEMO=1
      shift
      ;;
    --skip-demo)
      SKIP_DEMO=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
elif [[ -x "${ROOT}/venv/bin/python" ]]; then
  PYTHON="${ROOT}/venv/bin/python"
  # shellcheck disable=SC1091
  source "${ROOT}/venv/bin/activate"
else
  PYTHON="${PYTHON:-python3}"
  echo "Note: .venv not found; using ${PYTHON}. Create one with:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

port_in_use() {
  local p="$1"
  if command -v python3 >/dev/null 2>&1 || [[ -x "${PYTHON}" ]]; then
    "${PYTHON}" - "$p" <<'PY' 2>/dev/null
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.3)
try:
    s.connect(("127.0.0.1", port))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
raise SystemExit(0)
PY
    return $?
  fi
  return 1
}

has_picks=0
if compgen -G "${ROOT}/data/reports/realtime_picks_*.md" > /dev/null; then
  has_picks=1
fi

run_fast_daily() {
  local date="2026-06-17"
  mkdir -p "${ROOT}/data/raw" "${ROOT}/data/memory" "${ROOT}/data/reports"
  if [[ ! -f "${ROOT}/data/raw/raw_posts_${date}.csv" ]]; then
    if [[ -f "${ROOT}/tests/fixtures/raw_posts_smoke_min.csv" ]]; then
      cp "${ROOT}/tests/fixtures/raw_posts_smoke_min.csv" "${ROOT}/data/raw/raw_posts_${date}.csv"
    elif [[ -f "${ROOT}/tests/fixtures/raw_posts_${date}.csv" ]]; then
      cp "${ROOT}/tests/fixtures/raw_posts_${date}.csv" "${ROOT}/data/raw/raw_posts_${date}.csv"
    else
      echo "No fixture raw CSV found; skip demo replay." >&2
      return 0
    fi
  fi
  echo "Running keyword fast-daily replay for ${date} (no crawl) ..."
  SCORING_MODE="${SCORING_MODE:-keyword}" OPENCLAW_SKIP_ROW_SCORE="${OPENCLAW_SKIP_ROW_SCORE:-1}" \
    "${PYTHON}" -m opinion_trading.main --mode daily --date "${date}" --fast-daily
}

if [[ "${SKIP_DEMO}" -eq 0 ]]; then
  if [[ "${WITH_DEMO}" -eq 1 || "${has_picks}" -eq 0 ]]; then
    if [[ "${has_picks}" -eq 0 ]]; then
      echo "No realtime picks found — running a lightweight stub replay first."
    else
      echo "--with-demo: refreshing data via fast-daily replay."
    fi
    run_fast_daily || echo "Demo replay failed; starting UI with whatever data is present." >&2
  fi
fi

if port_in_use "${PORT}"; then
  echo "Warning: port ${PORT} already in use. Stop the existing Streamlit process or pass --port 8502" >&2
fi

URL="http://localhost:${PORT}"
echo ""
echo "=== Opinion Trading Dashboard ==="
echo "  URL:  ${URL}"
echo "  Tabs: 实时选股 | 舆情分析 | 评论依据 | 回测评估"
echo "  PYTHONPATH=${PYTHONPATH}"
echo ""

if [[ "${NO_BROWSER}" -eq 0 ]]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${URL}" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "${URL}" >/dev/null 2>&1 || true
  fi
fi

exec "${PYTHON}" -m streamlit run src/opinion_trading/ui_dashboard.py \
  --server.port "${PORT}" \
  --server.headless true \
  "${EXTRA_ARGS[@]}"
