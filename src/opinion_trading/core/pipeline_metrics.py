"""Lightweight pipeline metrics: counters/gauges → Prometheus text + JSON snapshot.

Used by the main daily workflow (not only microservices). Scrape or tail
``data/memory/pipeline_metrics.prom`` / ``pipeline_metrics.json``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class PipelineMetrics:
    """In-process metrics for one daily (or realtime) run."""

    def __init__(self, service: str = "pipeline") -> None:
        self.service = service
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.labels: Dict[str, str] = {}

    def inc(self, name: str, value: float = 1.0) -> None:
        self.counters[name] = self.counters.get(name, 0.0) + float(value)

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = float(value)

    def set_label(self, key: str, value: str) -> None:
        self.labels[str(key)] = str(value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "service": self.service,
            "labels": dict(self.labels),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
        }

    def render_prometheus(self) -> str:
        svc = self.service
        lines = [
            "# HELP opinion_trading_pipeline OpinionTrading pipeline snapshot",
            f'service_info{{service="{svc}"}} 1',
        ]
        for k, v in sorted(self.counters.items()):
            lines.append(f'{k}{{service="{svc}"}} {v}')
        for k, v in sorted(self.gauges.items()):
            lines.append(f'{k}{{service="{svc}"}} {v}')
        return "\n".join(lines) + "\n"

    def flush(self, memory_dir: str) -> Dict[str, str]:
        root = Path(memory_dir)
        root.mkdir(parents=True, exist_ok=True)
        prom_path = root / "pipeline_metrics.prom"
        json_path = root / "pipeline_metrics.json"
        prom_path.write_text(self.render_prometheus(), encoding="utf-8")
        json_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"prom": str(prom_path), "json": str(json_path)}


def record_daily_snapshot(
    metrics: PipelineMetrics,
    *,
    trade_date: str,
    signals: int,
    signals_allowed: int,
    risk_rejects: int,
    trades: int,
    open_positions: int,
    pending_orders: int,
    trading_halted: bool,
    broker_errors: int = 0,
    portfolio_value: Optional[float] = None,
) -> PipelineMetrics:
    """Fill standard daily gauges/counters onto ``metrics``."""
    metrics.set_label("trade_date", trade_date)
    metrics.inc("pipeline_signals_total", signals)
    metrics.inc("pipeline_signals_allowed_total", signals_allowed)
    metrics.inc("pipeline_risk_rejects_total", risk_rejects)
    metrics.inc("pipeline_trades_total", trades)
    metrics.inc("pipeline_broker_errors_total", broker_errors)
    metrics.set_gauge("pipeline_open_positions", open_positions)
    metrics.set_gauge("pipeline_pending_orders", pending_orders)
    metrics.set_gauge("pipeline_trading_halted", 1.0 if trading_halted else 0.0)
    if portfolio_value is not None:
        metrics.set_gauge("pipeline_portfolio_value", float(portfolio_value))
    return metrics
