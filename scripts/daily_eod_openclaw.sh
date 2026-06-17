#!/usr/bin/env bash
# End-of-day: crawl raw posts (daily mode) + OpenClaw batch rescore for UI AI coverage.
set -euo pipefail

ROOT="${OPENCLAW_PICKS_ROOT:-/opt/openclaw-picks}"
VENV="${ROOT}/.venv/bin"
LOG_DIR="${OPENCLAW_LOG_DIR:-/var/log/openclaw-picks}"
CONFIG="${OPENCLAW_CONFIG:-config/settings.yaml}"

mkdir -p "$LOG_DIR"
cd "$ROOT"

if [[ -f /etc/openclaw-picks.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/openclaw-picks.env
  set +a
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export HOME="${HOME:-/home/openclaw}"

DATE="${1:-$(TZ=Asia/Shanghai date +%F)}"
STAMP="$(TZ=Asia/Shanghai date +%Y%m%d_%H%M%S)"
LOG="${LOG_DIR}/daily_eod_${STAMP}.log"
ERR="${LOG_DIR}/daily_eod_${STAMP}.err.log"

exec >>"$LOG" 2>>"$ERR"

echo "=== daily_eod start $(date -Iseconds) date=${DATE} ==="

echo "--- daily crawl ---"
"${VENV}/python" -m opinion_trading.main --mode daily --date "$DATE" --config "$CONFIG"

RAW="${ROOT}/data/raw/raw_posts_${DATE}.csv"
if [[ ! -f "$RAW" ]]; then
  LATEST="$(ls -1 "${ROOT}/data/raw"/raw_posts_*.csv 2>/dev/null | tail -1 || true)"
  if [[ -n "$LATEST" ]]; then
    RAW="$LATEST"
    echo "Using latest raw: $RAW"
  else
    echo "No raw_posts CSV found; skip rescore"
    exit 0
  fi
fi

if [[ -z "${OPENCLAW_URL:-}" ]]; then
  echo "OPENCLAW_URL unset; skip rescore (keyword scores only)"
  exit 0
fi

echo "--- OpenClaw rescore: $RAW ---"
MAX_ROWS="${OPENCLAW_RESCORE_MAX_ROWS:-120}"
BATCH="${OPENCLAW_BATCH_SIZE:-4}"
"${VENV}/python" "${ROOT}/scripts/rescore_raw_openclaw.py" \
  --csv "$RAW" \
  --batch-size "$BATCH" \
  --max-rows "$MAX_ROWS" \
  --retries 2

echo "=== daily_eod done $(date -Iseconds) ==="