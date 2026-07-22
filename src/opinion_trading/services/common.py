"""Shared helpers for microservice FastAPI apps."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict

from fastapi import FastAPI, Response


class MetricsRegistry:
    """Minimal Prometheus-text metrics (no heavy deps)."""

    def __init__(self, service: str) -> None:
        self.service = service
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.latency_sum: Dict[str, float] = {}
        self.latency_count: Dict[str, float] = {}

    def inc(self, name: str, value: float = 1.0) -> None:
        self.counters[name] = self.counters.get(name, 0.0) + value

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = float(value)

    def observe_latency(self, name: str, seconds: float) -> None:
        self.latency_sum[name] = self.latency_sum.get(name, 0.0) + seconds
        self.latency_count[name] = self.latency_count.get(name, 0.0) + 1.0

    def render(self) -> str:
        lines = [f"# HELP service_info OpinionTrading service", f'service_info{{service="{self.service}"}} 1']
        for k, v in sorted(self.counters.items()):
            lines.append(f'{k}{{service="{self.service}"}} {v}')
        for k, v in sorted(self.gauges.items()):
            lines.append(f'{k}{{service="{self.service}"}} {v}')
        for k, total in sorted(self.latency_sum.items()):
            n = self.latency_count.get(k, 1.0)
            lines.append(f'{k}_seconds_sum{{service="{self.service}"}} {total}')
            lines.append(f'{k}_seconds_count{{service="{self.service}"}} {n}')
        return "\n".join(lines) + "\n"


def create_service_app(name: str, version: str = "1.0.0") -> tuple[FastAPI, MetricsRegistry]:
    app = FastAPI(title=f"OpinionTrading {name}", version=version)
    metrics = MetricsRegistry(name)

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "service": name, "version": version}

    @app.get("/ready")
    def ready() -> Dict[str, Any]:
        return {"status": "ready", "service": name}

    @app.get("/metrics")
    def prometheus_metrics() -> Response:
        return Response(content=metrics.render(), media_type="text/plain; version=0.0.4")

    return app, metrics


def timed(metrics: MetricsRegistry, name: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                metrics.observe_latency(name, time.perf_counter() - t0)

        return wrapper

    return decorator
