from __future__ import annotations

import os
from typing import Iterable, List, Optional

import requests


class OpenClawClient:
    """Simple adapter to call an OpenClaw sentiment endpoint.

    Expects environment variable `OPENCLAW_URL` set to base URL (e.g. https://openclaw.example.com)
    and optional `OPENCLAW_TOKEN` for Bearer auth.
    """

    def __init__(
        self, base_url: str | None = None, token: str | None = None, timeout: int | None = None
    ) -> None:
        self.base_url = base_url or os.environ.get("OPENCLAW_URL")
        self.token = token or os.environ.get("OPENCLAW_TOKEN")
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
