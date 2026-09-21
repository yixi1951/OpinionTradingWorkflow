# Changelog

## Unreleased (2026-09)

### Historical memory (JSONL recall)

- **`historical_memory`**: filtered `query_memory`, `recall_symbol_context`, optional JSONL prune; CLI `--mode memory-query` / `memory-recall`; Streamlit **历史记忆** panel; `docs/historical_memory.md`.
- Settings `memory.recall_enabled` / `recall_auto` / `lookback_days`; env `MEMORY_RECALL=1`. Daily run can append recall snippets to signal `explanation` (default off).

### External-track scaffolds (ops-ready, credentials pending)

- **Broker HTTP sandbox**: FastAPI mock (`mock_broker_server`), `HttpSandboxBrokerAdapter`, `--mode broker-sandbox-probe`, expanded `docs/broker_integration.md`.
- **Crawl persistence**: `crawl_persistence` helpers, `--mode collect-persist` / `crawl-span`, `docs/crawl_persistence.md`.
- **Human labels**: export/import scripts + `human-labels-*` CLI modes; expanded `docs/human_labels_howto.md`.
- **Auth**: `dashboard_auth` OAuth stub + `deploy/oauth.md`; `STREAMLIT_AUTH_BACKEND` switch.
- **DeepSeek daily**: scheduled `.github/workflows/deepseek-daily.yml` + `scripts/run_deepseek_daily.sh` (skips when secret missing).

### Engineering-complete (research prototype)

- **Status**: In-repo implementable work declared complete; remaining roadmap items are external-deps only (see `docs/LIMITATIONS_AND_ROADMAP.md` § OUT OF SCOPE).
- **`scripts/run_demo.sh`**: Linux one-shot OpenClaw stub + keyword offline demo; documented in `docs/DEV_SETUP.md`.
- **Quality**: optional `collection.semantic_near_dedup` (Jaccard/SimHash); winsorize `per_symbol` / `adaptive`; `timezone_utils.normalize_trade_date`; transaction cost `min_commission_cny` / `transfer_fee_bps`.
- **Scoring scaffolds**: `multi_label_sentiment`, `macro_industry_factors` stubs, `batch_scoring` chunked offline helper.
- **Labels**: synthetic fixture expanded to **72** balanced rows; `docs/human_labels_howto.md` + `scripts/add_human_labels.py`.
- CI coverage gate **54% → 55%** (measured ~57%).

### Transaction costs + UI settings preview
- **`execution.transaction_costs`**: optional commission tiers + A-share-style seller stamp-duty calendar on the shared eval/paper fill path (`docs/transaction_costs_research.md`). Default **off**; env `TRANSACTION_COSTS=1` to enable.
- Streamlit sidebar **read-only** settings preview via `opinion_trading.ui.settings_preview` (no config writes).
- Deploy: Nginx reverse-proxy checklist in `docs/DEV_SETUP.md`; example `deploy/nginx-streamlit.conf.example`.
- CI coverage gate **54%** (measured ~56% after #19 slice).

### Coverage + research scaffolds
- CI `--cov-fail-under` raised to **52**; added `tests/test_engineering_slice.py` for new modules.
- **Cross-day dedup**: optional SQLite fingerprint store (`collection.cross_day_dedup`, env `CROSS_DAY_DEDUP`); runs after in-day `text_dedup`.
- **Sentiment winsorize**: optional percentile clip on row scores (`quality.sentiment_winsorize`, env `SENTIMENT_WINSORIZE`); off by default.
- **Paper TP/SL scaffold**: `execution.paper_exit` uses shared price table, emits `paper_exit` events + paper `SELL` fills (research only).
- **Broker docs / stubs**: expanded `docs/broker_integration.md`; `BaseBrokerAdapter` live hooks + `LiveBrokerAdapter` raise `NotImplementedError`.

### Deploy UX
- `scripts/run_ui.sh`: Linux/macOS launcher (venv, `PYTHONPATH=src`, `--port`, `--no-browser`, optional keyword fast-daily).
- `docker-compose.yml`: `docker compose --profile ui up --build streamlit-ui` → Streamlit on **:8501** with `./data` + `./config` mounts. Full microservices stack unchanged (`docker compose up`).
- `docs/DEV_SETUP.md` / README document both paths.

### Proxy quality probe (P2)
- `--mode proxy-health` and `scripts/check_proxy_health.py` probe `collection.proxy_urls` / `PROXY_POOL` with a short HTTP(S) GET.
- Empty pool → skip/PASS (CI-safe). All configured proxies failing → exit 1.
- No captcha solver, no login cookies. Unit tests inject a fake transport (no live network).

### LLM failover skeleton
- If DeepSeek live scoring fails after retries, optionally try Qwen/DashScope (`QWEN_API_KEY` / `DASHSCOPE_API_KEY`, OpenAI-compatible) then keyword.
- Logs a single structured `LLM_FAILOVER {...}` warning. Keyword mode remains the CI default; pytest never needs live keys.

### Docs honesty
- Roadmap section 六 marks compose / `run_ui.sh` as landed; remaining gaps stay real broker API, captcha/login farm, large human labels, real crawl history.
- README “下一步” no longer claims “更多平台适配、ML 基线” as the next slice.

### DeepSeek live sentiment
- Env interface: `DEEPSEEK_API_KEY` (required for live), optional `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` / `DEEPSEEK_TIMEOUT`.
- OpenAI-compatible `/v1/chat/completions` client with one retry; keyword fallback when the key is missing (or `DEEPSEEK_REQUIRE=1` for a bilingual error).
- Wired first in `AISentimentAnalyzer` when `scoring.mode` is `ai`/`hybrid` (CI stays `SCORING_MODE=keyword`).
- CLI: `--mode deepseek-probe`, `--mode score-sample`, `scripts/probe_deepseek.py`. pytest mocks HTTP and strips the key.
- Manual GitHub Action **DeepSeek probe** (`.github/workflows/deepseek-probe.yml`, `workflow_dispatch` only) reads repo secret `DEEPSEEK_API_KEY`. Not on PR push.

### Opt-in Xiaohongshu / Weixin adapters
- Best-effort HTML collectors + stub fallback for `xiaohongshu` (`xhs`) and `weixin` (`gongzhonghao` / `wechat_oa`).
- Not on the default daily `strategy.platforms` list; enable by uncommenting in `config/settings.yaml`.
- Offline fixtures: `tests/fixtures/xiaohongshu_page.html`, `tests/fixtures/weixin_page.html`.

### Honest 3-fold walk-forward bundle (generated on demand)
- Committed replay span stays ~87 weekdays so `replay-batch` does not clone 170+ raw CSVs.
- `materialize_honest_walk_forward` / `scripts/materialize_wf_history.py` write ~240 calendar days of synthetic prices + `signal_history.jsonl` into a tmp dir.
- Tests assert 3 non-overlapping 60/20 folds without window shrink. This is **not** real crawl history.

### Proxy rotation skeleton
- `ProxyRotator` round-robin + failover; crawl GET uses `collection.proxy_urls` / `PROXY_POOL`.
- Captcha solvers and login-session farms remain deferred.

### P4 sandbox broker
- `SandboxBrokerAdapter` records dry-run intents to `sandbox_intents_*.jsonl` (`live_order=False`). No live broker API.

### Human labels / live hybrid flags
- Annotation schema adds optional `label_source` / `annotator`. CI fixture stays `synthetic`.
- Live hybrid LLM requires `HYBRID_USE_LLM=1` (or `USE_LLM_GATEWAY=1`) **and** a gateway/key; skipped in CI.

### P2 gateway health
- `scripts/check_gateway_health.py` and `--mode gateway-health`: HTTP `/ready` + `/api/v1/sentiment`, optional WS.
- No `OPENCLAW_URL` → Stub **HEALTH PASS** (offline/CI). Proxy URLs from `collection.proxy_urls` / `PROXY_POOL` are rotated by `ProxyRotator` on crawl GET (not a captcha/login farm).

### Longer walk-forward fixtures
- Price table spans 2026-03-20..2026-06-18. Raw seed clones weekday CSVs 2026-03-23..2026-06-17 (~87 days).
- Default 60/20 windows are not shrunk on that span. Three non-overlapping 60/20 folds use the **on-demand** ~240-day synthetic bundle (`scripts/materialize_wf_history.py`); still not real history.

### P3 labeled set / hybrid
- `tests/fixtures/annotation_sample_labeled.csv`: 36 synthetic rows, 12 per class.
- `compare_ml_baseline` also reports offline hybrid fusion (LLM skipped without keys).
- `scripts/train_eval.py` lazy-imports sklearn; CI smoke skips if missing.

### P5 Bilibili adapter
- Best-effort Bilibili search HTML + stub fallback; not on default daily platform list.

### Transaction costs
- `evaluate_signals` / paper fills honor `slippage_bps` + `fee_bps` on the shared price table. MTM stays mid. Broker **sandbox stub** records dry-run intents; live API still future.

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