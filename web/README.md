# Opinion Trading — Next.js dashboard

**Primary** dashboard UI (light theme, DnD overview, Framer Motion). Streamlit is legacy. See [docs/ui_nextjs.md](../docs/ui_nextjs.md).

## Setup

```bash
npm install
cp .env.example .env.local   # optional — see below
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API must be reachable at `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

### Environment

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI base URL (public, browser-side) |
| `DASHBOARD_PASSWORD` | Optional; enables middleware login |

No secrets use the `NEXT_PUBLIC_` prefix except the API base URL.

## Scripts

- `npm run dev` — development server
- `npm run build` — production build
- `npm run start` — run production server after build
- `npm run lint` — ESLint

## Docker

From repo root: `docker compose --profile web up --build api web`.
