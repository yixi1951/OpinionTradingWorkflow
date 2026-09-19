# Changelog

## Unreleased (2026-09)

### P2 gateway health
- `scripts/check_gateway_health.py` and `--mode gateway-health`: HTTP `/ready` + `/api/v1/sentiment`, optional WS.
- No `OPENCLAW_URL` → Stub **HEALTH PASS** (offline/CI). Proxy pool is config-only (`collection.proxy_urls` / `PROXY_POOL`).

### Longer walk-forward fixtures
- Price table spans 2026-03-20..2026-06-18. Raw seed clones weekday CSVs 2026-03-23..2026-06-17 (~87 days).
- Default 60/20 windows are not shrunk on that span; three non-overlapping 60/20 folds would still need ~240 days (documented).

### P3 labeled set / hybrid
- `tests/fixtures/annotation_sample_labeled.csv`: 36 synthetic rows, 12 per class.
- `compare_ml_baseline` also reports offline hybrid fusion (LLM skipped without keys).
- `scripts/train_eval.py` lazy-imports sklearn; CI smoke skips if missing.

### P5 Bilibili adapter
- Best-effort Bilibili search HTML + stub fallback; not on default daily platform list.

### Transaction costs
- `evaluate_signals` / paper fills honor `slippage_bps` + `fee_bps` on the shared price table. MTM stays mid. Broker sandbox still future.

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