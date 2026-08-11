"""HTTP clients for inter-service calls (loose coupling)."""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


class ServiceClient:
    def __init__(self, base_url: str, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str) -> Dict[str, Any]:
        r = requests.get(self.base_url + path, timeout=min(30, self.timeout))
        r.raise_for_status()
        return r.json()

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(
            self.base_url + path, json=payload, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()


def collector_client() -> ServiceClient:
    return ServiceClient(os.environ.get("COLLECTOR_URL", "http://127.0.0.1:8001"))


def inference_client() -> ServiceClient:
    return ServiceClient(os.environ.get("INFERENCE_URL", "http://127.0.0.1:8002"))


def compute_client() -> ServiceClient:
    return ServiceClient(os.environ.get("COMPUTE_URL", "http://127.0.0.1:8003"))


def api_client() -> ServiceClient:
    return ServiceClient(os.environ.get("API_URL", "http://127.0.0.1:8000"))
