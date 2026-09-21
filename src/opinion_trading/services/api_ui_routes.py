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


def _memory_dir() -> str:
    return os.environ.get("MEMORY_DIR", "data/memory")


def _report_dir() -> str:
    return os.environ.get("REPORT_DIR", "data/reports")


class AuthVerifyRequest(BaseModel):
    password: str = ""


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
        return {
            "ok": True,
            "rows": rows,
            "count": len(rows),
            "avg_score": round(avg, 4) if avg is not None else None,
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
