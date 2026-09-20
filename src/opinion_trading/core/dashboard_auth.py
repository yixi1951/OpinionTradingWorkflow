"""Streamlit dashboard auth backends: password (existing) | oauth stub (IdP-ready)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class OAuthSettings:
    client_id: str = ""
    client_secret: str = ""
    discovery_url: str = ""
    redirect_uri: str = ""
    scopes: str = "openid profile email"

    @classmethod
    def from_env(cls) -> "OAuthSettings":
        return cls(
            client_id=os.environ.get("OAUTH_CLIENT_ID", "").strip(),
            client_secret=os.environ.get("OAUTH_CLIENT_SECRET", "").strip(),
            discovery_url=os.environ.get("OAUTH_DISCOVERY_URL", "").strip(),
            redirect_uri=os.environ.get("OAUTH_REDIRECT_URI", "").strip(),
            scopes=os.environ.get("OAUTH_SCOPES", "openid profile email").strip(),
        )

    def configured(self) -> bool:
        return bool(self.client_id and self.discovery_url)


def resolve_auth_backend() -> str:
    """``password`` | ``oauth`` | ``none`` (none = open dashboard unless password set)."""
    raw = os.environ.get("STREAMLIT_AUTH_BACKEND", "").strip().lower()
    if raw in ("oauth", "oidc", "sso"):
        return "oauth"
    if raw in ("none", "off", "disabled"):
        return "none"
    if raw in ("password", "basic", ""):
        return "password"
    return "password"


def oauth_proxy_user() -> Optional[str]:
    """Trust reverse-proxy injected user (nginx oauth2-proxy / OIDC)."""
    for key in (
        "OAUTH_PROXY_AUTHENTICATED_USER",
        "REMOTE_USER",
        "HTTP_X_FORWARDED_USER",
    ):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return None


def require_dashboard_auth(
    st_module,
    t: Callable[[str], str],
) -> None:
    """Gate Streamlit UI. CI runs with no password and backend ``none`` → no-op."""
    backend = resolve_auth_backend()
    expected_pwd = os.environ.get("STREAMLIT_DASHBOARD_PASSWORD", "").strip()

    if backend == "none" and not expected_pwd:
        return

    if st_module.session_state.get("dashboard_authenticated"):
        return

    if backend == "oauth":
        _require_oauth(st_module, t)
        return

    if not expected_pwd:
        return

    st_module.markdown(f"### {t('auth_title')}")
    st_module.caption(t("auth_env_hint"))
    pwd = st_module.text_input(t("auth_prompt"), type="password", key="dashboard_pwd")
    if st_module.button("OK", key="dashboard_auth_btn"):
        if pwd == expected_pwd:
            st_module.session_state["dashboard_authenticated"] = True
            st_module.rerun()
        else:
            st_module.error(t("auth_wrong"))
    st_module.stop()


def _require_oauth(st_module, t: Callable[[str], str]) -> None:
    settings = OAuthSettings.from_env()
    proxy_user = oauth_proxy_user()
    if proxy_user:
        st_module.session_state["dashboard_authenticated"] = True
        st_module.session_state["oauth_user"] = proxy_user
        return

    st_module.markdown(f"### {t('auth_title')}")
    st_module.caption(
        "OAuth / SSO backend selected (`STREAMLIT_AUTH_BACKEND=oauth`). "
        "Full in-app OIDC requires IdP registration — use reverse-proxy SSO in production."
    )
    if not settings.configured():
        st_module.warning(
            "Set OAUTH_CLIENT_ID and OAUTH_DISCOVERY_URL (and secrets via env, not git). "
            "See deploy/oauth.md."
        )
    else:
        st_module.info(
            "OIDC client metadata is configured. Wire Authlib or oauth2-proxy in front of "
            "Streamlit; this stub does not perform live token exchange in CI."
        )

    if os.environ.get("OAUTH_STUB_ALLOW", "").strip().lower() in ("1", "true", "yes"):
        if st_module.button("Dev stub: mark authenticated", key="oauth_stub_btn"):
            st_module.session_state["dashboard_authenticated"] = True
            st_module.session_state["oauth_user"] = "stub-dev"
            st_module.rerun()
    st_module.stop()
