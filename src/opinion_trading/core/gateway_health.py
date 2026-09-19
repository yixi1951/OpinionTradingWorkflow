"""OpenClaw / collection gateway health probe (HTTP + optional WS).

Offline-safe: when no gateway URL is configured, reports a Stub pass so CI and
local keyword mode still have a clear HEALTH PASS/FAIL line. Proxy URLs from
``collection.proxy_urls`` / ``PROXY_POOL`` are enumerated here; crawl rotation
lives in ``opinion_trading.core.proxy_pool.ProxyRotator`` (round-robin + failover).
Captcha solvers and login-session farms are not implemented.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    ok: bool
    mode: str  # stub | live
    http_ready: Optional[bool] = None
    http_sentiment: Optional[bool] = None
    ws_ok: Optional[bool] = None
    proxy_pool_configured: int = 0
    url: Optional[str] = None
    ws_url: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def log_line(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"HEALTH {status} [{self.mode}] {self.message}"


def resolve_http_url(
    base_url: Optional[str] = None,
    *,
    stub: Optional[bool] = None,
) -> Optional[str]:
    if stub is True:
        return None
    if stub is None:
        env_stub = os.environ.get("GATEWAY_HEALTH_STUB", "").strip().lower()
        if env_stub in {"1", "true", "yes"}:
            return None
    if base_url is not None:
        raw = str(base_url).strip()
    else:
        raw = (
            os.environ.get("INFERENCE_URL")
            or os.environ.get("OPENCLAW_URL")
            or os.environ.get("OPENCLAW_GATEWAY_URL")
            or ""
        ).strip()
    return raw or None


def resolve_ws_url(ws_url: Optional[str] = None) -> Optional[str]:
    raw = (ws_url if ws_url is not None else os.environ.get("OPENCLAW_WS_URL", "")).strip()
    return raw or None


def load_proxy_pool(
    config_path: Optional[str] = None,
    *,
    extra: Optional[List[str]] = None,
) -> List[str]:
    """Return configured proxy URLs (no connectivity checks)."""
    urls: List[str] = []
    env_pool = os.environ.get("PROXY_POOL", "").strip()
    if env_pool:
        urls.extend(p.strip() for p in env_pool.split(",") if p.strip())
    path = config_path or os.environ.get("GATEWAY_HEALTH_CONFIG", "config/settings.yaml")
    cfg_path = Path(path)
    if cfg_path.is_file():
        try:
            import yaml  # type: ignore[import-not-found]

            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            coll = raw.get("collection") or {}
            listed = coll.get("proxy_urls") or []
            if isinstance(listed, str):
                listed = [listed]
            for item in listed:
                s = str(item).strip()
                if s:
                    urls.append(s)
        except Exception as exc:
            logger.debug("proxy pool config skipped: %s", exc)
    if extra:
        urls.extend(str(x).strip() for x in extra if str(x).strip())
    # de-dupe, keep order
    seen: set[str] = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def probe_http(
    base_url: str,
    *,
    token: Optional[str] = None,
    timeout: float = 5.0,
    transport: Any = None,
) -> Dict[str, Any]:
    """GET /ready and POST /api/v1/sentiment. ``transport`` is test-injectable."""
    import requests

    post = transport.post if transport is not None else requests.post
    get = transport.get if transport is not None else requests.get
    headers = {"Content-Type": "application/json"}
    tok = token if token is not None else os.environ.get("OPENCLAW_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    root = base_url.rstrip("/")
    ready: Dict[str, Any] = {"ok": False}
    try:
        resp = get(root + "/ready", timeout=timeout)
        ready = {
            "ok": bool(getattr(resp, "ok", False)),
            "status_code": getattr(resp, "status_code", None),
        }
        try:
            if getattr(resp, "content", None):
                ready["body"] = resp.json()
        except Exception:
            ready["body"] = None
    except Exception as exc:
        ready = {"ok": False, "error": str(exc)[:160]}

    sentiment: Dict[str, Any] = {"ok": False}
    try:
        resp = post(
            root + "/api/v1/sentiment",
            json={"texts": ["health-check: 连接测试"]},
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        scores = data.get("scores")
        ok = isinstance(scores, list) and len(scores) >= 1
        sentiment = {
            "ok": ok,
            "scores": scores if ok else None,
            "source": data.get("source"),
        }
    except Exception as exc:
        sentiment = {"ok": False, "error": str(exc)[:160]}
    return {"ready": ready, "sentiment": sentiment}


def probe_ws(
    ws_url: str,
    *,
    timeout: float = 2.0,
    opener: Any = None,
) -> Dict[str, Any]:
    """Lightweight WebSocket handshake. ``opener`` is test-injectable."""
    if opener is not None:
        try:
            opener(ws_url, timeout=timeout)
            return {"ok": True, "url": ws_url}
        except Exception as exc:
            return {"ok": False, "url": ws_url, "error": str(exc)[:160]}
    try:
        import asyncio

        import websockets
    except Exception as exc:
        return {"ok": None, "url": ws_url, "error": f"ws probe skipped: {exc}"[:160]}

    async def _once() -> str:
        async with websockets.connect(ws_url, open_timeout=timeout) as ws:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                msg = "<no-reply>"
            return str(msg)[:80]

    try:
        reply = asyncio.run(_once())
        return {"ok": True, "url": ws_url, "reply": reply}
    except Exception as exc:
        return {"ok": False, "url": ws_url, "error": str(exc)[:160]}


def check_gateway_health(
    *,
    base_url: Optional[str] = None,
    ws_url: Optional[str] = None,
    token: Optional[str] = None,
    timeout: float = 5.0,
    stub: Optional[bool] = None,
    config_path: Optional[str] = None,
    http_transport: Any = None,
    ws_opener: Any = None,
) -> HealthCheckResult:
    proxies = load_proxy_pool(config_path)
    http_url = resolve_http_url(base_url, stub=stub)
    ws = resolve_ws_url(ws_url)

    if not http_url:
        result = HealthCheckResult(
            ok=True,
            mode="stub",
            http_ready=None,
            http_sentiment=None,
            ws_ok=None,
            proxy_pool_configured=len(proxies),
            url=None,
            ws_url=ws,
            message="No gateway URL; Stub/keyword fallback (offline OK)",
            details={"proxy_urls": proxies, "hint": "Set OPENCLAW_URL to probe a live gateway"},
        )
        logger.info(result.log_line())
        return result

    http = probe_http(
        http_url, token=token, timeout=timeout, transport=http_transport
    )
    ready_ok = bool(http["ready"].get("ok"))
    sent_ok = bool(http["sentiment"].get("ok"))
    ws_info: Dict[str, Any] = {"ok": None}
    if ws:
        ws_info = probe_ws(ws, timeout=min(timeout, 2.0), opener=ws_opener)

    ws_flag = ws_info.get("ok")
    # HTTP sentiment is the pass/fail gate; WS and /ready are diagnostics.
    ok = sent_ok
    if ok:
        msg = f"gateway reachable sentiment=ok ready={ready_ok} ws={ws_flag}"
    else:
        err = http["sentiment"].get("error") or "sentiment probe failed"
        msg = f"gateway sentiment failed: {err}"

    result = HealthCheckResult(
        ok=ok,
        mode="live",
        http_ready=ready_ok,
        http_sentiment=sent_ok,
        ws_ok=ws_flag if isinstance(ws_flag, bool) else None,
        proxy_pool_configured=len(proxies),
        url=http_url,
        ws_url=ws,
        message=msg,
        details={"http": http, "ws": ws_info, "proxy_urls": proxies},
    )
    if result.ok:
        logger.info(result.log_line())
    else:
        logger.error(result.log_line())
    return result


def run_cli(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="OpenClaw gateway health check")
    parser.add_argument("--url", default=None, help="HTTP base URL (default OPENCLAW_URL)")
    parser.add_argument("--ws-url", default=None, help="Optional WS URL")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--stub", action="store_true", help="Force Stub/offline pass")
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args(argv)

    result = check_gateway_health(
        base_url=args.url,
        ws_url=args.ws_url,
        timeout=args.timeout,
        stub=True if args.stub else None,
        config_path=args.config,
    )
    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    if args.json:
        print(payload)
    else:
        print(result.log_line())
        print(payload)
    return 0 if result.ok else 1
