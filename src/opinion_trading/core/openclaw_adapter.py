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
            self.base_url = os.environ.get("OPENCLAW_URL")
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

    def probe(self) -> Dict[str, object]:
        """Lightweight connectivity check (single short text)."""
        if not self.is_configured():
            return {
                "connected": False,
                "url": None,
                "message": "OPENCLAW_URL not configured",
            }
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
            }
        except Exception as exc:
            return {
                "connected": False,
                "url": self.base_url,
                "message": str(exc)[:160],
            }
