# OAuth / SSO scaffolding (not production-complete)

This repository ships **configuration and Streamlit hooks** for enterprise SSO. It does **not** register your app with an IdP or store client secrets in git.

## Streamlit auth backend

| `STREAMLIT_AUTH_BACKEND` | Behavior |
|--------------------------|----------|
| `password` (default) | `STREAMLIT_DASHBOARD_PASSWORD` gate (demo-grade) |
| `oauth` | Expect reverse-proxy OIDC **or** dev stub (`OAUTH_STUB_ALLOW=1`) |
| `none` | Open UI unless password env is still set |

## OIDC environment variables

Set in `.env` or your process manager (never commit values):

- `OAUTH_CLIENT_ID`
- `OAUTH_CLIENT_SECRET`
- `OAUTH_DISCOVERY_URL` (e.g. `https://login.example.com/.well-known/openid-configuration`)
- `OAUTH_REDIRECT_URI` (public callback URL)
- `OAUTH_SCOPES` (default `openid profile email`)

Optional trust headers from a proxy:

- `OAUTH_PROXY_AUTHENTICATED_USER` / `REMOTE_USER` / `HTTP_X_FORWARDED_USER`

## Recommended production pattern

1. Register the app with your IdP (Azure AD, Okta, Keycloak, etc.).
2. Place **oauth2-proxy** or nginx `auth_request` in front of Streamlit.
3. Set `STREAMLIT_AUTH_BACKEND=oauth` and pass the authenticated user via proxy headers.
4. Keep Streamlit bound to `127.0.0.1`; expose only HTTPS on nginx.

See also `deploy/nginx-streamlit.conf.example` and `docs/deploy-aliyun-nginx-auth.md`.

## CI

GitHub Actions does not set OAuth variables; pytest and Streamlit smoke tests run without SSO.

## Dev-only stub

`OAUTH_STUB_ALLOW=1` shows a button to mark the session authenticated — **never enable on public hosts**.
