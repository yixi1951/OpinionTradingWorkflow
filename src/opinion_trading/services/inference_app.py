"""Inference service — multi-model LLM gateway."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from opinion_trading.services.common import create_service_app
from opinion_trading.services.llm_gateway import MultiModelGateway

app, metrics = create_service_app("inference")
_gateway = MultiModelGateway()


class ScoreRequest(BaseModel):
    texts: List[str]
    scenario: str = "sentiment"
    prompt_version: Optional[str] = None
    use_cache: bool = True


class PromptActivateRequest(BaseModel):
    scenario: str
    version: str


@app.post("/api/v1/sentiment")
def sentiment_compat(req: ScoreRequest) -> Dict[str, Any]:
    """Backward-compatible endpoint used by OpenClawClient."""
    return score(req)


@app.post("/v1/score")
def score(req: ScoreRequest) -> Dict[str, Any]:
    metrics.inc("inference_requests_total")
    result = _gateway.score(
        req.texts,
        scenario=req.scenario,
        prompt_version=req.prompt_version,
        use_cache=req.use_cache,
    )
    if result.get("cache_hit"):
        metrics.inc("inference_cache_hits_total")
    else:
        metrics.inc("inference_cache_misses_total")
    if result.get("provider") == "keyword_fallback":
        metrics.inc("inference_fallback_total")
    else:
        metrics.inc("inference_success_total")
    metrics.set_gauge("inference_cache_hit_rate", _gateway.stats()["cache_hit_rate"])
    return result


@app.get("/v1/prompts")
def list_prompts(scenario: Optional[str] = None) -> Dict[str, Any]:
    return {"prompts": _gateway.prompts.list_versions(scenario)}


@app.post("/v1/prompts/activate")
def activate_prompt(req: PromptActivateRequest) -> Dict[str, Any]:
    _gateway.prompts.set_active(req.scenario, req.version)
    return {"ok": True, "active": _gateway.prompts.list_versions(req.scenario)}


@app.get("/v1/gateway/stats")
def gateway_stats() -> Dict[str, Any]:
    return _gateway.stats()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "opinion_trading.services.inference_app:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", "8002")),
        reload=False,
    )


if __name__ == "__main__":
    main()
