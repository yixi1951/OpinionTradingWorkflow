"""Collection service — independent crawl / API pull."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from opinion_trading.services.common import create_service_app

app, metrics = create_service_app("collector")


class CollectRequest(BaseModel):
    trade_date: Optional[str] = None
    symbols: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    max_posts: int = 20


@app.post("/v1/collect")
def collect(req: CollectRequest) -> Dict[str, Any]:
    """Run collection for symbols/platforms; failures are isolated to this service."""
    metrics.inc("collect_requests_total")
    t0 = datetime.now()
    try:
        from opinion_trading.core.config_loader import load_runtime_config
        from opinion_trading.core.noise_filter import filter_noisy_rows
        from opinion_trading.core.semantic_enrichment import enrich_raw_rows
        from opinion_trading.integrations.platform_sentiment_real import (
            RealPlatformSentimentProvider,
        )
        from opinion_trading.core.raw_store import RawPostCsvStore
        from opinion_trading.core.parallel_collect import collect_raw_posts_parallel

        cfg = load_runtime_config()
        symbols = req.symbols or list(cfg.symbols)
        platforms = req.platforms or list(cfg.strategy.platforms)
        run_date = (
            date.fromisoformat(req.trade_date)
            if req.trade_date
            else date.today()
        )
        provider = RealPlatformSentimentProvider(max_posts=req.max_posts)
        raw_rows = collect_raw_posts_parallel(
            provider, symbols=symbols, platforms=platforms, trade_date=run_date
        )
        raw_rows, noise_stats = filter_noisy_rows(raw_rows, mark_only=True)
        raw_rows = enrich_raw_rows(raw_rows)
        store = RawPostCsvStore(cfg.raw_dir)
        paths = store.save_partitioned_rows(run_date.isoformat(), raw_rows)
        metrics.inc("collect_success_total")
        metrics.set_gauge("collect_last_rows", float(len(raw_rows)))
        metrics.observe_latency(
            "collect_duration", (datetime.now() - t0).total_seconds()
        )
        return {
            "ok": True,
            "trade_date": run_date.isoformat(),
            "rows": len(raw_rows),
            "noise_rate": noise_stats.get("noise_rate", 0.0),
            "paths": {k: str(v) for k, v in paths.items()},
        }
    except Exception as exc:
        metrics.inc("collect_failure_total")
        return {"ok": False, "error": str(exc)[:300]}


def main() -> None:
    import uvicorn

    uvicorn.run(
        "opinion_trading.services.collector_app:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", "8001")),
        reload=False,
    )


if __name__ == "__main__":
    main()
