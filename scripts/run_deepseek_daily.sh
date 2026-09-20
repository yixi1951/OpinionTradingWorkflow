#!/usr/bin/env bash
# Mirror .github/workflows/deepseek-daily.yml locally (requires DEEPSEEK_API_KEY).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src
export SCORING_MODE=ai
export DEEPSEEK_ALLOW_LIVE=1
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="data/reports/deepseek_daily_${STAMP}"
mkdir -p "$REPORT_DIR"

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "DEEPSEEK_API_KEY not set — skip (fork-friendly)."
  exit 0
fi

python -m opinion_trading.main --mode deepseek-probe | tee "$REPORT_DIR/probe.log"
python -m opinion_trading.main --mode score-sample | tee "$REPORT_DIR/score_sample.log"
echo "ok" > "$REPORT_DIR/status.txt"
echo "Wrote $REPORT_DIR"
