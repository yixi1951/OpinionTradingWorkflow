"""Compute service — signal aggregation, factor calc, pick lists."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from opinion_trading.services.common import create_service_app

app, metrics = create_service_app("compute")


class DailyComputeRequest(BaseModel):
    trade_date: Optional[str] = None
    fast_daily: bool = True
    top_n: int = 5


class FactorComputeRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    price_file: str = "data/reports/price_history_template.csv"


@app.post("/v1/compute/daily")
def compute_daily(req: DailyComputeRequest) -> Dict[str, Any]:
    """Run daily analysis / signal generation without crawling (uses cached raw)."""
    metrics.inc("compute_daily_requests_total")
    try:
        from opinion_trading.agents.workflow import OpinionTradingWorkflow

        wf = OpinionTradingWorkflow()
        run_date = (
            date.fromisoformat(req.trade_date) if req.trade_date else date.today()
        )
        result = wf.run_daily(run_date=run_date, skip_crawl=req.fast_daily)
        metrics.inc("compute_daily_success_total")
        picks = result.get("picks") or result.get("signals") or []
        return {
            "ok": True,
            "trade_date": run_date.isoformat(),
            "signals": len(result.get("signals", []) or []),
            "picks": picks[: req.top_n] if isinstance(picks, list) else picks,
            "report": result.get("report_path") or result.get("daily_report"),
        }
    except Exception as exc:
        metrics.inc("compute_daily_failure_total")
        return {"ok": False, "error": str(exc)[:300]}


@app.post("/v1/compute/factors")
def compute_factors(req: FactorComputeRequest) -> Dict[str, Any]:
    metrics.inc("compute_factor_requests_total")
    try:
        import json
        from pathlib import Path

        import pandas as pd

        from opinion_trading.core.config_loader import load_runtime_config
        from opinion_trading.core.evaluation import load_prices
        from opinion_trading.core.factor_backtest import (
            fetch_hs300_benchmark,
            run_factor_backtest,
            save_factor_backtest_report,
        )

        runtime = load_runtime_config()
        prices = load_prices(req.price_file)
        sent_path = Path(runtime.memory_dir) / "sentiment_history.jsonl"
        rows = []
        if sent_path.exists():
            for line in sent_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                rows.append(
                    {
                        "trade_date": obj.get("trade_date"),
                        "symbol": obj.get("symbol"),
                        "factor": float(obj.get("sentiment_score", 0.0) or 0.0),
                    }
                )
        if not rows:
            return {"ok": False, "error": "no sentiment history"}
        factor_df = pd.DataFrame(rows)
        start = req.start_date or str(factor_df["trade_date"].min())[:10]
        end = req.end_date or str(factor_df["trade_date"].max())[:10]
        bench = fetch_hs300_benchmark(start, end)
        report = run_factor_backtest(
            factor_df, prices, benchmark_df=bench, horizons=(1, 3, 5)
        )
        path = save_factor_backtest_report(report, runtime.report_dir, tag="api")
        metrics.inc("compute_factor_success_total")
        return {
            "ok": True,
            "report": path,
            "horizons": report.horizons,
            "vs_benchmark": report.vs_benchmark,
            "n_obs": report.n_obs,
        }
    except Exception as exc:
        metrics.inc("compute_factor_failure_total")
        return {"ok": False, "error": str(exc)[:300]}


@app.get("/v1/picks/latest")
def latest_picks(top_n: int = 5) -> Dict[str, Any]:
    """Read latest realtime/daily picks for presentation layer."""
    from pathlib import Path
    import json
    import re

    report_dir = Path("data/reports")
    # Prefer JSONL realtime alerts / picks sidecars if present
    jsonl_candidates = sorted(report_dir.glob("realtime_alerts_*.jsonl"), reverse=True)
    if jsonl_candidates:
        rows = []
        for line in jsonl_candidates[0].read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return {"ok": True, "file": str(jsonl_candidates[0]), "picks": rows[:top_n]}

    candidates = sorted(report_dir.glob("realtime_picks_*.md"), reverse=True)
    if candidates:
        text = candidates[0].read_text(encoding="utf-8")
        # Extract symbol-like tokens from markdown
        syms = re.findall(r"\b\d{6}\.(?:SH|SZ)\b", text)
        picks = [{"symbol": s, "source": "realtime_md"} for s in list(dict.fromkeys(syms))[:top_n]]
        return {"ok": True, "file": str(candidates[0]), "picks": picks}

    sig = Path("data/memory/signal_history.jsonl")
    if not sig.exists():
        return {"ok": True, "picks": []}
    lines = [ln for ln in sig.read_text(encoding="utf-8").splitlines() if ln.strip()]
    picks = [json.loads(ln) for ln in lines[-top_n:]]
    return {"ok": True, "picks": list(reversed(picks))}

def main() -> None:
    import uvicorn

    uvicorn.run(
        "opinion_trading.services.compute_app:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", "8003")),
        reload=False,
    )


if __name__ == "__main__":
    main()
