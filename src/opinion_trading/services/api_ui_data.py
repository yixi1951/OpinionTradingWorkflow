"""File-backed dashboard data loaders shared by API UI routes."""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from opinion_trading.core.noise_filter import refresh_row_noise_flags
from opinion_trading.core.symbol_explain import explain_symbol_sentiment
from opinion_trading.core.user_workspace import AlertRule, UserWorkspace
from opinion_trading.core.watchlist_alerts import run_watchlist_alert_cycle
from opinion_trading.ui_helpers import (
    build_openclaw_activity_feed,
    build_openclaw_summary,
    build_sentiment_engine_stats,
    compute_raw_capture_rates,
    evidence_stats,
    filter_comment_evidence,
    flatten_comment_rows,
    top_comment_rows,
)

_RAW_DATE_RE = re.compile(r"raw_posts_(\d{4}-\d{2}-\d{2})(?:_|\.csv)")


def memory_dir() -> str:
    return os.environ.get("MEMORY_DIR", "data/memory")


def report_dir() -> str:
    return os.environ.get("REPORT_DIR", "data/reports")


def raw_dir() -> str:
    return os.environ.get("RAW_DIR", "data/raw")


def users_dir() -> str:
    return os.environ.get("USERS_DIR", "data/users")


def _latest_file(pattern: str) -> str:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


def load_latest_realtime_picks(rd: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    root = rd or report_dir()
    path = _latest_file(str(Path(root) / "realtime_picks_*.csv"))
    if not path:
        return [], ""
    df = pd.read_csv(path)
    return df.fillna("").to_dict(orient="records"), path


def load_latest_alerts(rd: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    root = rd or report_dir()
    path = _latest_file(str(Path(root) / "realtime_alerts_*.jsonl"))
    if not path:
        return [], ""
    df = pd.read_json(path, lines=True)
    return df.fillna("").to_dict(orient="records"), path


def _ui_raw_lookback_days() -> int:
    return max(1, int(os.environ.get("UI_RAW_LOOKBACK_DAYS", "14")))


def _parse_raw_trade_date(path: Path) -> Optional[date]:
    m = _RAW_DATE_RE.search(path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def load_dashboard_raw_posts(
    raw: Optional[str] = None,
    *,
    lookback_days: Optional[int] = None,
    include_noise: bool = False,
) -> Tuple[pd.DataFrame, str]:
    """Merge recent combined + by_source raw CSVs for dashboard evidence."""
    root = Path(raw or raw_dir())
    lookback = lookback_days if lookback_days is not None else _ui_raw_lookback_days()
    cutoff = date.today() - timedelta(days=lookback)

    paths: List[Path] = []
    for pattern in ("raw_posts_*.csv", "by_source/raw_posts_*.csv"):
        for p in sorted(root.glob(pattern)):
            td = _parse_raw_trade_date(p)
            if td is not None and td < cutoff:
                continue
            paths.append(p)

    if not paths:
        latest = _latest_file(str(root / "raw_posts_*.csv"))
        if not latest:
            return pd.DataFrame(), ""
        paths = [Path(latest)]

    frames: List[pd.DataFrame] = []
    for p in paths:
        try:
            frames.append(pd.read_csv(p))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(), ""

    df = pd.concat(frames, ignore_index=True)
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"], keep="last")
    elif "title" in df.columns and "platform" in df.columns:
        df = df.drop_duplicates(subset=["platform", "title", "symbol"], keep="last")

    rows, _ = refresh_row_noise_flags(
        df.fillna("").to_dict(orient="records"),
        drop_noise=not include_noise,
    )
    out = pd.DataFrame(rows) if rows else pd.DataFrame()
    source_note = f"{root} (lookback={lookback}d, files={len(paths)})"
    return out, source_note


def load_latest_raw_posts(raw: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    return load_dashboard_raw_posts(raw, include_noise=True)


def load_sentiment_history_df(md: Optional[str] = None) -> pd.DataFrame:
    path = Path(md or memory_dir()) / "sentiment_history.jsonl"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def load_signal_history_rows(md: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    path = Path(md or memory_dir()) / "signal_history.jsonl"
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def raw_pipeline_summary(raw_df: pd.DataFrame) -> Dict[str, Any]:
    if raw_df is None or raw_df.empty:
        return {
            "ok": False,
            "total": 0,
            "engine_stats": {},
            "capture_rates": {},
            "score_source_counts": [],
            "platform_capture": [],
        }
    total = len(raw_df)
    df = raw_df.copy()
    llm_n = 0
    if "score_source" in df.columns:
        src = df["score_source"].astype(str).str.lower()
        llm_n = int(src.isin(["openclaw", "transformers", "gateway", "hybrid"]).sum())
    relevant_n = (
        int(df["ai_relevant"].fillna(True).astype(bool).sum())
        if "ai_relevant" in df.columns
        else total
    )
    success_n = (
        int((df["capture_status"].astype(str) == "success").sum())
        if "capture_status" in df.columns
        else 0
    )
    score_source_counts: List[Dict[str, Any]] = []
    if "score_source" in df.columns:
        vc = df["score_source"].fillna("(na)").astype(str).value_counts()
        score_source_counts = [
            {"score_source": str(k), "count": int(v)} for k, v in vc.items()
        ]
    platform_capture: List[Dict[str, Any]] = []
    if "platform" in df.columns and "capture_status" in df.columns:
        ct = pd.crosstab(df["platform"], df["capture_status"].fillna("na"))
        for plat in ct.index:
            row: Dict[str, Any] = {"platform": str(plat)}
            for col in ct.columns:
                row[str(col)] = int(ct.loc[plat, col])
            platform_capture.append(row)
    drop_reasons: List[Dict[str, Any]] = []
    if "ai_drop_reason" in df.columns and "ai_relevant" in df.columns:
        dropped = df[df["ai_relevant"].fillna(True).astype(bool) == False]  # noqa: E712
        if not dropped.empty:
            vc = dropped["ai_drop_reason"].fillna("(空)").astype(str).value_counts().head(10)
            drop_reasons = [{"reason": str(k), "count": int(v)} for k, v in vc.items()]

    show_cols = [
        c
        for c in [
            "symbol",
            "platform",
            "title",
            "ai_score",
            "score_source",
            "ai_relevant",
            "capture_status",
            "event_type",
        ]
        if c in df.columns
    ]
    sample = df
    if "ai_relevant" in sample.columns:
        sample = sample[sample["ai_relevant"].fillna(True).astype(bool)]
    if "ai_score" in sample.columns and not sample.empty:
        sample = sample.assign(
            _abs=pd.to_numeric(sample["ai_score"], errors="coerce").abs()
        ).sort_values("_abs", ascending=False)
    samples = sample[show_cols].head(30).fillna("").to_dict(orient="records") if show_cols else []

    return {
        "ok": True,
        "total": total,
        "llm_scored": llm_n,
        "ai_relevant": relevant_n,
        "capture_success": success_n,
        "engine_stats": build_sentiment_engine_stats(raw_df),
        "capture_rates": compute_raw_capture_rates(raw_df),
        "score_source_counts": score_source_counts,
        "platform_capture": platform_capture,
        "drop_reasons": drop_reasons,
        "samples": samples,
    }


def openclaw_dashboard_payload(
    raw_df: pd.DataFrame, picks: List[Dict[str, Any]], rd: Optional[str] = None
) -> Dict[str, Any]:
    picks_df = pd.DataFrame(picks) if picks else pd.DataFrame()
    summary = build_openclaw_summary(raw_df, picks_df)
    feed = build_openclaw_activity_feed(raw_df, limit=30, lang="zh")
    probe: Dict[str, Any] = {"connected": False, "message": "probe skipped on API"}
    try:
        from opinion_trading.core.openclaw_adapter import OpenClawClient

        client = OpenClawClient()
        if client.is_configured():
            probe = client.probe()
        else:
            probe = {"connected": False, "url": None, "message": "OPENCLAW_URL not set"}
    except Exception as exc:
        probe = {"connected": False, "message": str(exc)[:200]}
    picks_path = _latest_file(str(Path(rd or report_dir()) / "realtime_picks_*.csv"))
    return {
        "ok": True,
        "probe": probe,
        "summary": summary,
        "activity_feed": feed,
        "latest_picks_path": picks_path,
    }


def symbol_daily_sentiment(sentiment_df: pd.DataFrame, symbol: str) -> List[Dict[str, Any]]:
    if sentiment_df.empty:
        return []
    sub = sentiment_df[sentiment_df["symbol"].astype(str).str.upper() == symbol.upper()].copy()
    if sub.empty or "sentiment_score" not in sub.columns:
        return []
    sub["trade_date"] = pd.to_datetime(sub.get("trade_date"), errors="coerce")
    sub = sub.dropna(subset=["trade_date"])
    if "post_count" in sub.columns:
        daily = (
            sub.groupby(sub["trade_date"].dt.date)
            .agg(score=("sentiment_score", "mean"), heat=("post_count", "sum"))
            .reset_index()
        )
    else:
        daily = (
            sub.groupby(sub["trade_date"].dt.date)
            .agg(score=("sentiment_score", "mean"), heat=("sentiment_score", "count"))
            .reset_index()
        )
    daily.columns = ["trade_date", "score", "heat"]
    daily["trade_date"] = daily["trade_date"].astype(str)
    return daily.sort_values("trade_date").to_dict(orient="records")


def load_price_series(symbol: str, lookback_days: int = 90) -> List[Dict[str, Any]]:
    try:
        from opinion_trading.core.market_data import fetch_ohlcv

        end = date.today()
        start = end - timedelta(days=lookback_days)
        df = fetch_ohlcv(symbol, start_date=start.isoformat(), end_date=end.isoformat())
        if df is None or df.empty:
            return []
        out = df.reset_index() if "Close" in getattr(df, "columns", []) else df.copy()
        cols = {c.lower(): c for c in out.columns}
        date_col = cols.get("date") or cols.get("datetime") or out.columns[0]
        close_col = cols.get("close")
        if close_col is None:
            for c in out.columns:
                if str(c).lower() == "close":
                    close_col = c
                    break
        if close_col is None:
            return []
        res = pd.DataFrame(
            {
                "date": pd.to_datetime(out[date_col], errors="coerce"),
                "close": pd.to_numeric(out[close_col], errors="coerce"),
            }
        ).dropna()
        res = res.sort_values("date")
        return [{"date": r["date"].strftime("%Y-%m-%d"), "close": float(r["close"])} for _, r in res.iterrows()]
    except Exception:
        return []


def review_series(symbol: str, lookback_days: int = 90) -> Dict[str, Any]:
    sentiment_df = load_sentiment_history_df()
    raw_df, _ = load_latest_raw_posts()
    daily = symbol_daily_sentiment(sentiment_df, symbol)
    prices = load_price_series(symbol, lookback_days=lookback_days)
    expl = explain_symbol_sentiment(symbol, sentiment_df=sentiment_df, raw_df=raw_df)
    corr: Optional[float] = None
    if daily and prices:
        ddf = pd.DataFrame(daily)
        ddf["trade_date"] = pd.to_datetime(ddf["trade_date"])
        pdf = pd.DataFrame(prices)
        pdf["trade_date"] = pd.to_datetime(pdf["date"])
        merged = pd.merge_asof(
            ddf.sort_values("trade_date"),
            pdf.rename(columns={"date": "trade_date"}).sort_values("trade_date"),
            on="trade_date",
            direction="backward",
        )
        merged["next_ret_1d"] = merged["close"].pct_change().shift(-1)
        valid = merged.dropna(subset=["score", "next_ret_1d"])
        if len(valid) >= 5:
            corr = float(valid["score"].corr(valid["next_ret_1d"]))
    return {
        "ok": bool(daily or prices),
        "symbol": symbol,
        "sentiment_daily": daily,
        "prices": prices,
        "explanation": expl,
        "score_return_corr": corr,
    }


def comments_for_symbol(
    symbol: str,
    top_n: int = 15,
    *,
    include_noise: bool = False,
    lookback_days: Optional[int] = None,
) -> Dict[str, Any]:
    raw_df, path = load_dashboard_raw_posts(
        include_noise=include_noise,
        lookback_days=lookback_days,
    )
    if raw_df.empty:
        return {"ok": False, "message": "No raw posts CSV", "path": path, "rows": []}
    bundle = top_comment_rows(
        raw_df,
        symbol,
        top_n=top_n,
        include_reference=True,
        allow_noise=include_noise,
    )
    rows = flatten_comment_rows(bundle)
    stats = evidence_stats(raw_df, symbol)
    stats["lookback_days"] = lookback_days if lookback_days is not None else _ui_raw_lookback_days()
    stats["include_noise"] = include_noise
    return {
        "ok": True,
        "path": path,
        "stats": stats,
        "rows": rows,
        "count": len(rows),
    }


def sentiment_evidence_posts(
    symbol: str,
    *,
    limit: int = 40,
    include_noise: bool = False,
    lookback_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Clean per-post rows for 舆情 dashboard (multi-day raw)."""
    raw_df, _ = load_dashboard_raw_posts(
        include_noise=include_noise,
        lookback_days=lookback_days,
    )
    if raw_df.empty:
        return []
    sym = symbol.strip().upper()
    base = raw_df[raw_df["symbol"].astype(str).str.upper() == sym]
    if base.empty:
        return []
    comments = filter_comment_evidence(base)
    if comments.empty:
        return []
    comments = comments.copy()
    comments["ai_score"] = pd.to_numeric(comments.get("ai_score", 0), errors="coerce").fillna(
        0.0
    )
    comments = comments.sort_values("ai_score", key=lambda s: s.abs(), ascending=False)
    out: List[Dict[str, Any]] = []
    for _, row in comments.head(limit).iterrows():
        out.append(
            {
                "platform": row.get("platform"),
                "title": row.get("_display") or row.get("title"),
                "ai_score": float(row.get("ai_score") or 0.0),
                "trade_date": row.get("trade_date"),
                "url": row.get("url"),
            }
        )
    return out


def analyst_payload(md: Optional[str] = None, rd: Optional[str] = None) -> Dict[str, Any]:
    all_signals = load_signal_history_rows(md)
    multi_agent_rows: List[Dict[str, Any]] = []
    for row in all_signals:
        scores = row.get("analyst_scores")
        has_scores = bool(scores) and (
            isinstance(scores, dict) or (isinstance(scores, str) and str(scores).strip())
        )
        if has_scores or row.get("consensus_score") is not None:
            multi_agent_rows.append(row)

    cmp_path = Path(rd or report_dir()) / "backtest_comparison.csv"
    comparison: List[Dict[str, Any]] = []
    if cmp_path.is_file():
        cmp_df = pd.read_csv(cmp_path)
        comparison = cmp_df.fillna("").to_dict(orient="records")

    return {
        "ok": True,
        "has_multi_agent": bool(multi_agent_rows),
        "multi_agent_rows": multi_agent_rows,
        "all_signals_count": len(all_signals),
        "comparison_rows": comparison,
        "comparison_path": str(cmp_path) if cmp_path.is_file() else None,
    }


def workspace_profile(username: str) -> Dict[str, Any]:
    ws = UserWorkspace(users_dir())
    profile = ws.load_profile(username) or ws.load_profile("demo")
    if not profile:
        return {"ok": False, "message": "user not found"}
    return {
        "ok": True,
        "username": profile.username,
        "watchlist": profile.watchlist,
        "alert_rules": profile.alert_rules,
        "email": profile.email,
    }


def workspace_inbox(username: str, limit: int = 30) -> Dict[str, Any]:
    ws = UserWorkspace(users_dir())
    return {"ok": True, "messages": ws.list_inbox(username, limit=limit)}


def workspace_add_watch(username: str, symbol: str) -> Dict[str, Any]:
    ws = UserWorkspace(users_dir())
    ws.add_watch(username, symbol.strip())
    return workspace_profile(username)


def workspace_remove_watch(username: str, symbol: str) -> Dict[str, Any]:
    ws = UserWorkspace(users_dir())
    ws.remove_watch(username, symbol.strip())
    return workspace_profile(username)


def workspace_upsert_alert(
    username: str,
    symbol: str,
    score_high: float,
    score_low: float,
    heat_spike_ratio: float,
    email: str = "",
) -> Dict[str, Any]:
    ws = UserWorkspace(users_dir())
    profile = ws.load_profile(username) or ws.load_profile("demo")
    if profile and email.strip():
        profile.email = email.strip()
        ws.save_profile(profile)
    ws.upsert_alert_rule(
        username,
        AlertRule(
            symbol=symbol,
            score_high=score_high,
            score_low=score_low,
            heat_spike_ratio=heat_spike_ratio,
            enabled=True,
        ),
    )
    return workspace_profile(username)


def workspace_run_alerts(username: str) -> Dict[str, Any]:
    ws = UserWorkspace(users_dir())
    sentiment_df = load_sentiment_history_df()
    results = run_watchlist_alert_cycle(username, sentiment_df, workspace=ws)
    return {"ok": True, "triggered": results, "count": len(results)}
