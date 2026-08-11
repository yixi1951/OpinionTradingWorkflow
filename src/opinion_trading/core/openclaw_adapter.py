from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional

import requests

_MISSING = object()


class OpenClawClient:
    """Simple adapter to call an OpenClaw sentiment endpoint.

    Expects environment variable `OPENCLAW_URL` set to base URL (e.g. https://openclaw.example.com)
    and optional `OPENCLAW_TOKEN` for Bearer auth.
    """

    def __init__(
        self,
        base_url: str | None = _MISSING,
        token: str | None = _MISSING,
        timeout: int | None = None,
    ) -> None:
        if base_url is _MISSING:
            # Prefer dedicated inference service, then legacy OpenClaw proxy
            self.base_url = os.environ.get("INFERENCE_URL") or os.environ.get(
                "OPENCLAW_URL"
            )
        else:
            self.base_url = base_url
        if token is _MISSING:
            self.token = os.environ.get("OPENCLAW_TOKEN")
        else:
            self.token = token
        if timeout is None:
            timeout = int(os.environ.get("OPENCLAW_TIMEOUT", "180"))
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def score_texts(self, texts: Iterable[str]) -> Optional[List[float]]:
        if not self.is_configured():
            return None

        url = self.base_url.rstrip("/") + "/api/v1/sentiment"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload = {"texts": list(texts)}
        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            # expected response: {"scores": [0.1, -0.2, ...]}
            scores = data.get("scores")
            if isinstance(scores, list) and all(
                isinstance(s, (int, float)) for s in scores
            ):
                return [float(s) for s in scores]
        except Exception:
            return None

        return None

    def health_check(self, timeout: float = 2.0) -> Dict[str, object]:
        """Fast liveness/readiness probe — no LLM call (safe for UI first paint)."""
        if not self.is_configured():
            return {
                "connected": False,
                "url": None,
                "message": "OPENCLAW_URL not configured",
                "mode": "health",
            }
        base = self.base_url.rstrip("/")
        ready_info: Dict[str, object] = {}
        try:
            ready_resp = requests.get(f"{base}/ready", timeout=timeout)
            if ready_resp.ok:
                ready_info = ready_resp.json() if ready_resp.content else {"status": "ready"}
            else:
                ready_info = {"status": "not_ready", "http": ready_resp.status_code}
        except Exception as exc:
            ready_info = {"status": "unreachable", "detail": str(exc)[:80]}
        try:
            health_resp = requests.get(f"{base}/health", timeout=timeout)
            health_ok = health_resp.ok
            health_body = health_resp.json() if health_resp.content else {}
        except Exception as exc:
            return {
                "connected": False,
                "url": self.base_url,
                "message": str(exc)[:160],
                "ready": ready_info,
                "mode": "health",
            }
        connected = bool(health_ok) and str(ready_info.get("status", "")).lower() in {
            "ready",
            "ok",
            "",
        }
        # If /ready is missing (404) but /health is ok, still treat as up.
        if health_ok and ready_info.get("status") in {"unreachable", "not_ready"}:
            # try health alone when ready endpoint absent
            if isinstance(ready_info.get("http"), int) and int(ready_info["http"]) == 404:
                connected = True
            elif ready_info.get("status") == "unreachable":
                connected = health_ok
        return {
            "connected": connected,
            "url": self.base_url,
            "message": "OpenClaw proxy healthy" if connected else "OpenClaw proxy not ready",
            "ready": ready_info,
            "health": health_body if health_ok else {},
            "mode": "health",
        }

    def probe(self) -> Dict[str, object]:
        """Connectivity check including a live sentiment score (slow — LLM path)."""
        if not self.is_configured():
            return {
                "connected": False,
                "url": None,
                "message": "OPENCLAW_URL not configured",
            }
        ready_info: Dict[str, object] = {}
        try:
            ready_url = self.base_url.rstrip("/") + "/ready"
            ready_resp = requests.get(ready_url, timeout=5)
            if ready_resp.ok:
                ready_info = ready_resp.json() if ready_resp.content else {}
        except Exception as exc:
            ready_info = {"status": "unreachable", "detail": str(exc)[:80]}

        url = self.base_url.rstrip("/") + "/api/v1/sentiment"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            probe_timeout = int(os.environ.get("OPENCLAW_PROBE_TIMEOUT", "120"))
            resp = requests.post(
                url,
                json={"texts": ["连接测试：今天市场偏多。"]},
                headers=headers,
                timeout=min(probe_timeout, self.timeout),
            )
            resp.raise_for_status()
            data = resp.json()
            scores = data.get("scores")
            ok = isinstance(scores, list) and len(scores) == 1
            return {
                "connected": ok,
                "url": self.base_url,
                "message": "OpenClaw gateway reachable",
                "sample_score": float(scores[0]) if ok else None,
                "ready": ready_info,
                "score_source": data.get("source"),
                "mode": "llm",
            }
        except Exception as exc:
            return {
                "connected": False,
                "url": self.base_url,
                "message": str(exc)[:160],
                "ready": ready_info,
                "mode": "llm",
            }
