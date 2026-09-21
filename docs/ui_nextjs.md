# Next.js dashboard (preferred UI)

The Streamlit app (`src/opinion_trading/ui_dashboard.py`) remains available but is **deprecated** for day-to-day use. The **Next.js** app under `web/` is the preferred trading dashboard.

## What ships in the first slice

| Section | Route | API |
|---------|-------|-----|
| Overview / status | `/` | `GET /v1/status` |
| Picks | `/picks` | `GET /v1/picks` |
| Sentiment history | `/sentiment` | `GET /v1/sentiment/history` |
| Eval / walk-forward | `/eval` | `GET /v1/eval/walk-forward`, `GET /v1/eval/monthly` |
| Historical memory | `/memory` | `GET /v1/memory/*` |
| Run daily | `/run` | `POST /v1/run/daily` |

Still **Streamlit-only** (not ported yet): watch/alert tabs, live comments drill-down, OpenClaw animations, analyst debate UI, captcha/collect controls, full backtest upload flows.

## Local dev (API + Next)

```bash
# Terminal 1 — microservices (or at minimum API + compute + inference)
docker compose up -d --build api collector compute inference
# Or: python -m opinion_trading.services.api_app  (with backends configured)

# Terminal 2 — Next.js
cd web
npm install
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
# → http://localhost:3000
```

CORS is enabled on the API by default for `http://localhost:3000` (`API_CORS_ENABLED=1`, `API_CORS_ORIGINS`).

## Docker (profile `web`)

```bash
docker compose --profile web up --build api web
```

Do not bind Grafana and `web` both on host port 3000; use `WEB_PORT=3001` if the full stack is running.

## Optional password gate

Mirrors Streamlit’s `STREAMLIT_DASHBOARD_PASSWORD`:

- **Next.js**: set `DASHBOARD_PASSWORD` (compose maps from `STREAMLIT_DASHBOARD_PASSWORD` for the `web` service).
- **API**: `POST /v1/auth/verify` for programmatic checks (password never shipped in the client bundle).

## Streamlit (legacy)

```bash
docker compose --profile ui up --build streamlit-ui   # standalone :8501
# or full stack `dashboard` service on :8501
```

See `web/README.md` for frontend-only commands.
