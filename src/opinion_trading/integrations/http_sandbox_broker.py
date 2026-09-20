"""HTTP client adapter for broker sandbox REST APIs (dry-run by default)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests

from opinion_trading.integrations.broker_adapter import (
    BaseBrokerAdapter,
    ExecutionIntent,
)


def _sandbox_url() -> str:
    return os.environ.get("BROKER_SANDBOX_URL", "http://127.0.0.1:8765").rstrip("/")


def live_order_allowed() -> bool:
    """Dangerous override — requires explicit env (never default on)."""
    return os.environ.get("BROKER_SANDBOX_ALLOW_LIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def http_sandbox_enabled() -> bool:
    return os.environ.get("ENABLE_HTTP_BROKER_SANDBOX", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


class HttpSandboxBrokerAdapter(BaseBrokerAdapter):
    """POST dry-run intents to ``BROKER_SANDBOX_URL`` (mock or future REST API).

    Always records a local audit JSONL mirror under ``report_dir``.
    """

    def __init__(
        self,
        report_dir: str = "data/reports",
        base_url: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = (base_url or _sandbox_url()).rstrip("/")
        self.timeout = timeout

    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        if not intents:
            return {
                "path": "",
                "count": 0,
                "dry_run": True,
                "sandbox": True,
                "live_order": False,
                "http": True,
            }
        dry_run = all(i.dry_run for i in intents)
        live_order = False
        if not dry_run and live_order_allowed():
            live_order = True
        elif not dry_run:
            raise ValueError(
                "HttpSandboxBrokerAdapter refuses live_order without "
                "BROKER_SANDBOX_ALLOW_LIVE=1 (documented dangerous)"
            )

        day = intents[0].trade_date
        audit_path = self.report_dir / f"http_sandbox_intents_{day}.jsonl"
        payloads = []
        with audit_path.open("a", encoding="utf-8") as f:
            for intent in intents:
                row = intent.to_dict()
                row["sandbox"] = True
                row["live_order"] = live_order
                row["http_target"] = self.base_url
                payloads.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        body = {
            "intents": [
                {
                    "trade_date": i.trade_date,
                    "symbol": i.symbol,
                    "side": i.side,
                    "confidence": i.confidence,
                    "suggested_notional_ratio": i.suggested_notional_ratio,
                    "reason": i.reason,
                    "source": i.source,
                    "dry_run": True if not live_order else i.dry_run,
                    "client_order_id": f"{i.trade_date}:{i.symbol}:{i.side}",
                }
                for i in intents
            ],
            "dry_run": not live_order,
            "live_order": live_order,
        }
        resp = requests.post(
            f"{self.base_url}/v1/intents",
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        remote = resp.json()
        return {
            "path": str(audit_path),
            "count": len(intents),
            "dry_run": not live_order,
            "sandbox": True,
            "live_order": live_order,
            "http": True,
            "remote": remote,
        }


def probe_sandbox(base_url: Optional[str] = None, timeout: float = 5.0) -> Dict[str, object]:
    url = (base_url or _sandbox_url()).rstrip("/")
    try:
        r = requests.get(f"{url}/health", timeout=timeout)
        ok = r.status_code == 200
        detail = r.json() if ok else {"status_code": r.status_code}
        return {"ok": ok, "url": url, "health": detail}
    except requests.RequestException as exc:
        return {"ok": False, "url": url, "error": str(exc)}
