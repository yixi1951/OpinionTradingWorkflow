"""Read-only HTTP routes for the Next.js dashboard (file-backed + memory)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Query
from pydantic import BaseModel

from opinion_trading.core.historical_memory import (
    KNOWN_KINDS,
    query_memory,
    recall_symbol_context,
)
from opinion_trading.core.monthly_training import load_latest_monthly_training
from opinion_trading.core.walk_forward_cache import load_walk_forward_json
from opinion_trading.core.symbol_explain import explain_symbol_sentiment
from opinion_trading.services.api_ui_enrich import enrich_picks_payload, quotes_for_symbols
from opinion_trading.services.api_ui_data import (
    analyst_payload,
    comments_for_symbol,
    load_dashboard_raw_posts,
    load_latest_alerts,
    load_latest_raw_posts,
    load_latest_realtime_picks,
    load_sentiment_history_df,
    memory_dir as ui_memory_dir,
    openclaw_dashboard_payload,
    raw_pipeline_summary,
    report_dir as ui_report_dir,
    review_series,
    sentiment_evidence_posts,
    symbol_daily_sentiment,
    workspace_add_watch,
    workspace_inbox,
    workspace_profile,
    workspace_remove_watch,
    workspace_run_alerts,
    workspace_upsert_alert,
)


def _memory_dir() -> str:
    return os.environ.get("MEMORY_DIR", "data/memory")


def _report_dir() -> str:
    return os.environ.get("REPORT_DIR", "data/reports")


class AuthVerifyRequest(BaseModel):
    password: str = ""


class WatchMutation(BaseModel):
    username: str = "demo"
    symbol: str = ""


class AlertRuleRequest(BaseModel):
    username: str = "demo"
    symbol: str = ""
    score_high: float = 0.35
    score_low: float = -0.35
    heat_spike_ratio: float = 2.0
    email: str = ""


class AlertRunRequest(BaseModel):
    username: str = "demo"


def register_ui_routes(app) -> None:
    @app.get("/v1/memory/kinds")
    def memory_kinds() -> Dict[str, Any]:
        return {"kinds": list(KNOWN_KINDS)}

    @app.get("/v1/memory/query")
    def memory_query(
        kind: str = Query(..., description="signals|sentiment|trades|events|quality_gate"),
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = Query(50, ge=1, le=500),
    ) -> Dict[str, Any]:
        try:
            rows = query_memory(
                _memory_dir(),
                kind=kind,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "kind": kind, "rows": rows, "count": len(rows)}

    @app.get("/v1/memory/recall")
    def memory_recall(
        symbol: str = Query(..., min_length=1),
        lookback_days: int = Query(14, ge=1, le=365),
    ) -> Dict[str, Any]:
        sym = symbol.strip().upper()
        if not sym:
            raise HTTPException(status_code=400, detail="symbol required")
        ctx = recall_symbol_context(
            _memory_dir(),
            sym,
            lookback_days=lookback_days,
        )
        return {"ok": True, "recall": ctx}

    @app.get("/v1/sentiment/history")
    def sentiment_history(
        symbol: Optional[str] = None,
        limit: int = Query(100, ge=1, le=500),
        include_noise: int = Query(0, ge=0, le=1),
        evidence_limit: int = Query(40, ge=0, le=120),
        lookback_days: int = Query(14, ge=1, le=90),
    ) -> Dict[str, Any]:
        rows = query_memory(
            _memory_dir(),
            kind="sentiment",
            symbol=symbol,
            limit=limit,
        )
        scores = [
            float(r["sentiment_score"])
            for r in rows
            if r.get("sentiment_score") is not None
        ]
        avg = sum(scores) / len(scores) if scores else None
        evidence: List[Dict[str, Any]] = []
        if symbol and evidence_limit > 0:
            evidence = sentiment_evidence_posts(
                symbol.strip(),
                limit=evidence_limit,
                include_noise=bool(include_noise),
                lookback_days=lookback_days,
            )
        return {
            "ok": True,
            "rows": rows,
            "count": len(rows),
            "avg_score": round(avg, 4) if avg is not None else None,
            "evidence_posts": evidence,
            "evidence_count": len(evidence),
            "lookback_days": lookback_days,
        }

    @app.get("/v1/eval/walk-forward")
    def eval_walk_forward() -> Dict[str, Any]:
        data = load_walk_forward_json(_report_dir())
        if data is None:
            return {
                "ok": False,
                "message": "No walk_forward_report.json in report dir",
                "report_dir": _report_dir(),
            }
        return {"ok": True, "report": data, "report_dir": _report_dir()}

    @app.get("/v1/eval/monthly")
    def eval_monthly() -> Dict[str, Any]:
        monthly_df, summary = load_latest_monthly_training(_report_dir())
        rows: List[Dict[str, Any]] = []
        if not monthly_df.empty:
            rows = monthly_df.fillna("").to_dict(orient="records")
        return {
            "ok": bool(summary or rows),
            "summary": summary,
            "rows": rows,
            "report_dir": _report_dir(),
        }

    @app.post("/v1/auth/verify")
    def auth_verify(req: AuthVerifyRequest) -> Dict[str, Any]:
        expected = (
            os.environ.get("STREAMLIT_DASHBOARD_PASSWORD", "").strip()
            or os.environ.get("DASHBOARD_PASSWORD", "").strip()
        )
        if not expected:
            return {"ok": True, "required": False}
        return {"ok": req.password == expected, "required": True}

    @app.get("/v1/dashboard/snapshot")
    def dashboard_snapshot() -> Dict[str, Any]:
        picks, picks_path = load_latest_realtime_picks()
        alerts, alerts_path = load_latest_alerts()
        sentiment_df = load_sentiment_history_df()
        raw_df, raw_path = load_dashboard_raw_posts(include_noise=False)
        platform_count = (
            int(sentiment_df["platform"].nunique()) if not sentiment_df.empty else 0
        )
        pipeline = raw_pipeline_summary(raw_df)
        return enrich_picks_payload(
            {
                "ok": True,
                "report_dir": ui_report_dir(),
                "memory_dir": ui_memory_dir(),
                "picks": picks,
                "picks_path": picks_path,
                "alerts": alerts,
                "alerts_path": alerts_path,
                "raw_path": raw_path,
                "platform_count": platform_count,
                "pipeline": pipeline,
            }
        )

    @app.get("/v1/picks/file")
    def picks_file() -> Dict[str, Any]:
        rows, path = load_latest_realtime_picks()
        return enrich_picks_payload(
            {"ok": bool(rows), "picks": rows, "source_path": path}
        )

    @app.get("/v1/quotes")
    def market_quotes(
        symbols: str = Query(..., min_length=1, description="Comma-separated A-share codes"),
    ) -> Dict[str, Any]:
        parts = [s.strip() for s in symbols.split(",") if s.strip()]
        if not parts:
            raise HTTPException(status_code=400, detail="symbols required")
        if len(parts) > 50:
            raise HTTPException(status_code=400, detail="max 50 symbols per request")
        return quotes_for_symbols(parts)

    @app.get("/v1/alerts/latest")
    def alerts_latest() -> Dict[str, Any]:
        rows, path = load_latest_alerts()
        return {"ok": bool(rows), "alerts": rows, "source_path": path}

    @app.get("/v1/raw/summary")
    def raw_summary() -> Dict[str, Any]:
        raw_df, path = load_latest_raw_posts()
        payload = raw_pipeline_summary(raw_df)
        payload["source_path"] = path
        return payload

    @app.get("/v1/comments")
    def comments(
        symbol: str = Query(..., min_length=1),
        top_n: int = Query(20, ge=1, le=80),
        include_noise: int = Query(0, ge=0, le=1),
        lookback_days: int = Query(14, ge=1, le=90),
    ) -> Dict[str, Any]:
        return comments_for_symbol(
            symbol.strip(),
            top_n=top_n,
            include_noise=bool(include_noise),
            lookback_days=lookback_days,
        )

    @app.get("/v1/openclaw/dashboard")
    def openclaw_dashboard() -> Dict[str, Any]:
        raw_df, _ = load_latest_raw_posts()
        picks, _ = load_latest_realtime_picks()
        return openclaw_dashboard_payload(raw_df, picks)

    @app.get("/v1/watchlist/explain")
    def watchlist_explain(
        symbol: str = Query(..., min_length=1),
    ) -> Dict[str, Any]:
        sym = symbol.strip()
        sentiment_df = load_sentiment_history_df()
        raw_df, _ = load_latest_raw_posts()
        expl = explain_symbol_sentiment(sym, sentiment_df=sentiment_df, raw_df=raw_df)
        daily = symbol_daily_sentiment(sentiment_df, sym)
        return {"ok": True, "symbol": sym, "explanation": expl, "sentiment_daily": daily}

    @app.get("/v1/review/series")
    def review(
        symbol: str = Query(..., min_length=1),
        lookback_days: int = Query(90, ge=30, le=365),
    ) -> Dict[str, Any]:
        return review_series(symbol.strip(), lookback_days=lookback_days)

    @app.get("/v1/analyst")
    def analyst() -> Dict[str, Any]:
        return analyst_payload()

    @app.get("/v1/workspace/profile")
    def ws_profile(username: str = Query("demo")) -> Dict[str, Any]:
        return workspace_profile(username.strip() or "demo")

    @app.get("/v1/workspace/inbox")
    def ws_inbox(
        username: str = Query("demo"),
        limit: int = Query(30, ge=1, le=100),
    ) -> Dict[str, Any]:
        return workspace_inbox(username.strip() or "demo", limit=limit)

    @app.post("/v1/workspace/watch/add")
    def ws_watch_add(req: WatchMutation) -> Dict[str, Any]:
        if not req.symbol.strip():
            raise HTTPException(status_code=400, detail="symbol required")
        return workspace_add_watch(req.username.strip() or "demo", req.symbol)

    @app.post("/v1/workspace/watch/remove")
    def ws_watch_remove(req: WatchMutation) -> Dict[str, Any]:
        if not req.symbol.strip():
            raise HTTPException(status_code=400, detail="symbol required")
        return workspace_remove_watch(req.username.strip() or "demo", req.symbol)

    @app.post("/v1/workspace/alerts")
    def ws_alerts_upsert(req: AlertRuleRequest) -> Dict[str, Any]:
        if not req.symbol.strip():
            raise HTTPException(status_code=400, detail="symbol required")
        return workspace_upsert_alert(
            req.username.strip() or "demo",
            req.symbol.strip(),
            req.score_high,
            req.score_low,
            req.heat_spike_ratio,
            req.email,
        )

    @app.post("/v1/workspace/alerts/run")
    def ws_alerts_run(req: AlertRunRequest) -> Dict[str, Any]:
        return workspace_run_alerts(req.username.strip() or "demo")
