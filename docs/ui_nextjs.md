# Next.js dashboard (primary UI)

The **Next.js** app under `web/` is the **preferred** trading dashboard. Streamlit (`src/opinion_trading/ui_dashboard.py`) remains for legacy workflows but is **deprecated** for day-to-day use.

## Routes (parity with Streamlit tabs)

| Section | Route | API |
|---------|-------|-----|
| Overview (draggable widgets) | `/` | `GET /v1/status`, `GET /v1/dashboard/snapshot`, sentiment + memory snippets |
| 自选股监控 | `/watchlist` | `GET /v1/workspace/profile`, `GET /v1/watchlist/explain`, watch add/remove |
| 信号预警 | `/alerts` | workspace alerts + `POST /v1/workspace/alerts/run`, inbox |
| 舆情复盘 | `/review` | `GET /v1/review/series` |
| AI 采集筛选 | `/ai` | `GET /v1/raw/summary` |
| 选股 | `/picks` | `GET /v1/picks` (compute) · `GET /v1/picks/file` (CSV fallback) |
| OpenClaw | `/openclaw` | `GET /v1/openclaw/dashboard` |
| 舆情 | `/sentiment` | `GET /v1/sentiment/history` |
| 评论依据 | `/comments` | `GET /v1/comments?symbol=` |
| 评估 | `/eval` | `GET /v1/eval/walk-forward`, `GET /v1/eval/monthly` |
| 分析师 | `/analyst` | `GET /v1/analyst` |
| 记忆 | `/memory` | `GET /v1/memory/*` |
| 运行日线 | `/run` | `POST /v1/run/daily` |

## UX notes

- **Light theme** by default (soft gray borders, white surfaces).
- **Hover** on cards, nav, and table rows; **rounded-2xl** panels.
- **Drag-and-drop** widget order on Overview (`localStorage` key `otw-dashboard-widget-order-v1`).
- **Framer Motion** page transitions and `AnimatePresence` route switches.
- **`prefers-reduced-motion`** toning in `globals.css`.

Still **thin / stub** vs Streamlit where noted:

- **Eval**: no price CSV upload or Yahoo fetch from the browser (use CLI / Streamlit for full backtest upload).
- **Analyst**: needs `analyst_scores` in `signal_history.jsonl` or `backtest_comparison.csv` on disk.
- **OpenClaw**: live probe only when `OPENCLAW_URL` is set on the API host.
- **Review**: price series uses the same Python fetch as Streamlit (may be empty offline).

## Local dev (API + Next)

```bash
docker compose up -d --build api collector compute inference

cd web
npm install
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
# → http://localhost:3000
```

CORS: `API_CORS_ENABLED=1`, `API_CORS_ORIGINS` includes `http://localhost:3000`.

## Docker (profile `web`)

```bash
docker compose --profile web up --build api web
```

Use `WEB_PORT=3001` if port 3000 is taken (e.g. Grafana).

## Optional password gate

- **Next.js**: `DASHBOARD_PASSWORD` (compose maps from `STREAMLIT_DASHBOARD_PASSWORD` for `web`).
- **API**: `POST /v1/auth/verify` — password never in the client bundle.

## Streamlit (legacy)

```bash
docker compose --profile ui up --build streamlit-ui
```

See `web/README.md` for frontend-only commands.
