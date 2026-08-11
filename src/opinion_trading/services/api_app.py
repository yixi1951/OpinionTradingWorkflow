"""Presentation API — thin facade over compute/collector/inference."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from opinion_trading.services.clients import (
    collector_client,
    compute_client,
    inference_client,
)
from opinion_trading.services.common import create_service_app

app, metrics = create_service_app("api")


class RunDailyRequest(BaseModel):
    trade_date: Optional[str] = None
    collect: bool = False
    fast_daily: bool = True
    top_n: int = 5


@app.get("/v1/status")
def status() -> Dict[str, Any]:
    out: Dict[str, Any] = {"api": "ok"}
    for name, client_fn in (
        ("collector", collector_client),
        ("inference", inference_client),
        ("compute", compute_client),
    ):
        try:
            out[name] = client_fn().get("/health")
        except Exception as exc:
            out[name] = {"status": "down", "error": str(exc)[:120]}
    return out


@app.post("/v1/run/daily")
def run_daily(req: RunDailyRequest) -> Dict[str, Any]:
    """Orchestrate optional collect → compute; inference is used inside pipeline."""
    metrics.inc("api_run_daily_total")
    collect_result = None
    if req.collect:
        try:
            collect_result = collector_client().post(
                "/v1/collect",
                {"trade_date": req.trade_date},
            )
        except Exception as exc:
            collect_result = {"ok": False, "error": str(exc)[:200]}
    compute_result = compute_client().post(
        "/v1/compute/daily",
        {
            "trade_date": req.trade_date,
            "fast_daily": req.fast_daily or bool(collect_result and collect_result.get("ok")),
            "top_n": req.top_n,
        },
    )
    return {"collect": collect_result, "compute": compute_result}


@app.get("/v1/picks")
def picks(top_n: int = 5) -> Dict[str, Any]:
    try:
        return compute_client().get(f"/v1/picks/latest?top_n={top_n}")
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "picks": []}


class ScoreProxyRequest(BaseModel):
    texts: List[str] = Field(default_factory=list)
    scenario: str = "sentiment"


@app.post("/v1/score")
def score(req: ScoreProxyRequest) -> Dict[str, Any]:
    return inference_client().post(
        "/v1/score", {"texts": req.texts, "scenario": req.scenario}
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "opinion_trading.services.api_app:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
