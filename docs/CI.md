# CI / GitHub Actions

Workflow: `.github/workflows/ci.yml`

## Jobs

| Job | What it does |
|-----|----------------|
| `test` | `pytest tests/` on Python 3.10–3.12（coverage gate `--cov-fail-under=55`） |
| `fast-daily-smoke` | Fixture raw CSV → `analysis.enabled=false` → `--fast-daily` → checks `data/memory/state.json` |

## fast-daily-smoke

1. Ensures `data/raw/raw_posts_2026-06-17.csv` exists (copies `tests/fixtures/raw_posts_smoke_min.csv` if missing).
2. Runs `set_analysis_enabled('config/settings.yaml', False)` so CI does not fetch market data for technical/fundamental agents.
3. Runs daily with `OPENCLAW_SKIP_ROW_SCORE=1` and `SCORING_MODE=keyword`.

P0 多日路径由 pytest 覆盖（不依赖仓库内已有 `data/raw`）：

- `tests/test_replay_walk_forward.py`：fixture seed → `replay-batch` → 短历史 `walk_forward`
- 多日 raw：committed `raw_posts_2026-06-1*.csv` + seed 时按 weekday 扩展到 `2026-03-23..2026-06-17`
- 价表：`tests/fixtures/price_history_replay.csv`（同 span，约 90 日历日）
- 网关健康：`tests/test_gateway_health.py`（mock HTTP/WS，无外网）
- 代理探测：`tests/test_proxy_health.py`（空池 PASS；mock transport，无外网）

Local check (matches CI):

```bash
export PYTHONPATH=src OPENCLAW_SKIP_ROW_SCORE=1 SCORING_MODE=keyword
cp tests/fixtures/raw_posts_smoke_min.csv data/raw/raw_posts_2026-06-17.csv
python -c "from opinion_trading.core.settings_patch import set_analysis_enabled; set_analysis_enabled('config/settings.yaml', False)"
python -m opinion_trading.main --mode daily --date 2026-06-17 --fast-daily
```

Offline P0 replay + walk-forward (fixtures only):

```bash
export PYTHONPATH=src OPENCLAW_SKIP_ROW_SCORE=1 SCORING_MODE=keyword
python -m opinion_trading.main --mode replay-batch --reset-paper
python -m opinion_trading.main --mode walk_forward --price-file tests/fixtures/price_history_replay.csv
```

Restore multi-agent after CI simulation:

```bash
python scripts/restore_analysis_enabled.py
# or: python scripts/restore_analysis_enabled.py --off
```