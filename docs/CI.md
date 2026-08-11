# CI / GitHub Actions

Workflow: `.github/workflows/ci.yml`

## Jobs

| Job | What it does |
|-----|----------------|
| `test` | `pytest tests/` on Python 3.12 |
| `fast-daily-smoke` | Fixture raw CSV → `analysis.enabled=false` → `--fast-daily` → checks `data/memory/state.json` |

## fast-daily-smoke

1. Ensures `data/raw/raw_posts_2026-06-17.csv` exists (copies `tests/fixtures/raw_posts_smoke_min.csv` if missing).
2. Runs `set_analysis_enabled('config/settings.yaml', False)` so CI does not fetch market data for technical/fundamental agents.
3. Runs daily with `OPENCLAW_SKIP_ROW_SCORE=1` and `SCORING_MODE=keyword`.

Local check (matches CI):

```bash
export PYTHONPATH=src OPENCLAW_SKIP_ROW_SCORE=1 SCORING_MODE=keyword
cp tests/fixtures/raw_posts_smoke_min.csv data/raw/raw_posts_2026-06-17.csv
python -c "from opinion_trading.core.settings_patch import set_analysis_enabled; set_analysis_enabled('config/settings.yaml', False)"
python -m opinion_trading.main --mode daily --date 2026-06-17 --fast-daily
```

Restore multi-agent after CI simulation:

```bash
python scripts/restore_analysis_enabled.py
# or: python scripts/restore_analysis_enabled.py --off
```