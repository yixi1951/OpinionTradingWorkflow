"""Lightweight HTTP(S) probe for configured crawl proxies.

Reads ``collection.proxy_urls`` / ``PROXY_POOL`` (same source as
``ProxyRotator``). Empty pool → skip/PASS so CI stays green. No captcha
solver, no login cookies, no live network in unit tests (inject transport).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit

from opinion_trading.core.gateway_health import load_proxy_pool
from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

DEFAULT_PROBE_URL = "http://example.com/"


@dataclass
class ProxyProbeResult:
    url: str
    display_url: str
    ok: bool
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProxyHealthReport:
    ok: bool
    skipped: bool
    probe_url: str
    timeout: float
    configured: int
    passed: int
    failed: int
    message: str
    results: List[ProxyProbeResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        return payload

    def log_line(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"PROXY HEALTH {status} {self.message}"

    def table_lines(self) -> List[str]:
        if self.skipped:
            return [self.log_line()]
        header = f"{'proxy':<42} {'status':<6} {'code':<6} {'ms':<8} error"
        lines = [header, "-" * len(header)]
        for row in self.results:
            st = "PASS" if row.ok else "FAIL"
            code = "-" if row.status_code is None else str(row.status_code)
            ms = "-" if row.latency_ms is None else str(row.latency_ms)
            err = (row.error or "")[:48]
            lines.append(f"{row.display_url:<42} {st:<6} {code:<6} {ms:<8} {err}")
        lines.append(f"SUMMARY {self.passed}/{self.configured} PASS")
        lines.append(self.log_line())
        return lines


def redact_proxy_url(url: str) -> str:
    """Hide userinfo in proxy URLs (never print credentials)."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not (parts.username or parts.password):
        return raw
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"***@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _status_ok(resp: Any) -> bool:
    if bool(getattr(resp, "ok", False)):
        return True
    code = getattr(resp, "status_code", None)
    try:
        return code is not None and 200 <= int(code) < 400
    except (TypeError, ValueError):
        return False


def probe_one_proxy(
    proxy_url: str,
    *,
    probe_url: str = DEFAULT_PROBE_URL,
    timeout: float = 5.0,
    transport: Any = None,
) -> ProxyProbeResult:
    """GET ``probe_url`` through ``proxy_url``. ``transport`` is test-injectable."""
    import requests

    display = redact_proxy_url(proxy_url)
    get = transport.get if transport is not None else requests.get
    proxies = {"http": proxy_url, "https": proxy_url}
    started = time.perf_counter()
    try:
        resp = get(probe_url, proxies=proxies, timeout=timeout)
        latency_ms = int((time.perf_counter() - started) * 1000)
        code = getattr(resp, "status_code", None)
        ok = _status_ok(resp)
        error = "" if ok else f"HTTP {code}"
        return ProxyProbeResult(
            url=proxy_url,
            display_url=display,
            ok=ok,
            status_code=code if isinstance(code, int) else None,
            latency_ms=latency_ms,
            error=error,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ProxyProbeResult(
            url=proxy_url,
            display_url=display,
            ok=False,
            status_code=None,
            latency_ms=latency_ms,
            error=str(exc)[:160],
        )


def check_proxy_health(
    *,
    config_path: Optional[str] = None,
    extra: Optional[Sequence[str]] = None,
    probe_url: Optional[str] = None,
    timeout: float = 5.0,
    transport: Any = None,
) -> ProxyHealthReport:
    urls = load_proxy_pool(config_path, extra=list(extra) if extra else None)
    target = (probe_url or os.environ.get("PROXY_HEALTH_URL") or DEFAULT_PROBE_URL).strip()
    timeout = max(0.2, float(timeout))

    if not urls:
        report = ProxyHealthReport(
            ok=True,
            skipped=True,
            probe_url=target,
            timeout=timeout,
            configured=0,
            passed=0,
            failed=0,
            message="No proxies configured; skip/PASS (CI-safe)",
            results=[],
        )
        logger.info(report.log_line())
        return report

    results = [
        probe_one_proxy(u, probe_url=target, timeout=timeout, transport=transport)
        for u in urls
    ]
    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed
    ok = passed > 0
    if ok:
        msg = f"{passed}/{len(results)} proxies reachable via {target}"
    else:
        msg = f"all {len(results)} configured proxies failed via {target}"
    report = ProxyHealthReport(
        ok=ok,
        skipped=False,
        probe_url=target,
        timeout=timeout,
        configured=len(results),
        passed=passed,
        failed=failed,
        message=msg,
        results=results,
    )
    if report.ok:
        logger.info(report.log_line())
    else:
        logger.error(report.log_line())
    return report


def run_cli(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Probe collection.proxy_urls / PROXY_POOL (no captcha/login)"
    )
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument(
        "--probe-url",
        default=None,
        help="HTTP(S) URL fetched through each proxy (default PROXY_HEALTH_URL or example.com)",
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--proxy",
        action="append",
        default=[],
        help="Extra proxy URL (repeatable); merged with config/env pool",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args(argv)

    report = check_proxy_health(
        config_path=args.config,
        extra=args.proxy,
        probe_url=args.probe_url,
        timeout=args.timeout,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.json:
        print(payload)
    else:
        print("\n".join(report.table_lines()))
    return 0 if report.ok else 1
