# Changelog

## Unreleased (2026-09)

### P0 replay / walk-forward
- Multi-day fixture raw CSVs (`tests/fixtures/raw_posts_2026-06-1*.csv`) and `price_history_replay.csv`.
- `--mode replay-batch` seeds fixtures when `data/raw` is empty; omits 2025 backtest date defaults so 2026 fixtures are not filtered out.
- Walk-forward auto-shrinks train/test windows on short `signal_history`.

### P1 price alignment
- Paper equity MTM and `evaluate_signals` share `lookup_close` / local price table (`PRICE_FILE` or cache CSV).
- `validate_paper_eval_price_alignment` catches mismatches.

### P3 ML baseline
- `scripts/compare_ml_baseline.py` writes TF-IDF vs keyword report; CI fixture `tests/fixtures/annotation_sample_labeled.csv`.
- `sample_annotation.py` accepts raw CSV as well as JSONL.

### P5 Zhihu adapter
- Best-effort Zhihu HTML collector + stub fallback; not enabled in default daily platform list.

### Tests / docs
- Replay-batch, walk-forward, price alignment, zhihu, and core-module coverage tests.
- Roadmap / DEV_SETUP / CI / annotation docs updated.

## Unreleased (2026-06)

### CI & smoke

- **fast-daily-smoke** job: copies `tests/fixtures/raw_posts_smoke_min.csv` when needed; disables `analysis.enabled` before replay for speed.
- Local/CI env: `OPENCLAW_SKIP_ROW_SCORE=1`, `SCORING_MODE=keyword`.

### Dashboard

- **Quality gate history** chart on Eval tab (`quality_gate_history.jsonl` from daily runs).
- Hero KPI: **fallback rate** (red when above `quality.max_fallback_rate`, default 35%).
- Sentiment engine strip: fallback / noise % from latest raw CSV.
- Eval: auto walk-forward, fold table, **WF CSV download**.
- Sidebar: ZIP export, collect progress log, universe editor, strategy preview, optional `STREAMLIT_DASHBOARD_PASSWORD`.
- UI language syncs `project.explanation_lang`; English re-renders stored explanations.

### Pipeline

- Parallel collection (`COLLECT_PARALLEL`, `COLLECT_MAX_WORKERS`, `collect_progress_*.jsonl`, optional tqdm).
- Post **time decay** (`sentiment_recency` in settings).
- `.env` auto-load via `env_bootstrap` (main + Streamlit).
- Multi-agent consensus explanations (zh/en); sentiment-only Kelly + explanations.

### Config / tools

- `settings_patch`: universe symbols, explanation_lang, `set_analysis_enabled`.
- Export bundle includes WF JSON, collect progress logs.
- `scripts/restore_analysis_enabled.py` — turn multi-agent back on after CI smoke.
- Docs: `DEV_SETUP`, `FAQ`, `CI.md`, `LIMITATIONS_AND_ROADMAP`, `.env.example`, `docs/assets/` screenshot placeholder.