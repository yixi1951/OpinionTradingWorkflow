"""MVP explainability: why a symbol's sentiment score is high/low."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

import pandas as pd

from opinion_trading.core.semantic_enrichment import (
    classify_event,
    enrich_raw_row,
    platform_meta,
)


def explain_symbol_sentiment(
    symbol: str,
    *,
    sentiment_df: Optional[pd.DataFrame] = None,
    raw_df: Optional[pd.DataFrame] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Build a human-readable explanation for one symbol."""
    sym = symbol.strip().upper()
    score = None
    platforms: Dict[str, float] = {}
    if sentiment_df is not None and not sentiment_df.empty:
        sub = sentiment_df[
            sentiment_df["symbol"].astype(str).str.upper() == sym
        ].copy()
        if not sub.empty and "sentiment_score" in sub.columns:
            if "trade_date" in sub.columns:
                sub["trade_date"] = pd.to_datetime(sub["trade_date"], errors="coerce")
                latest_d = sub["trade_date"].max()
                day = sub[sub["trade_date"] == latest_d]
            else:
                day = sub
            score = float(day["sentiment_score"].mean())
            if "platform" in day.columns:
                platforms = {
                    str(p): float(g["sentiment_score"].mean())
                    for p, g in day.groupby("platform")
                }

    comments: List[Dict[str, Any]] = []
    event_counter: Counter = Counter()
    if raw_df is not None and not raw_df.empty:
        raw = raw_df[raw_df["symbol"].astype(str).str.upper() == sym].copy()
        if not raw.empty:
            for _, row in raw.head(80).iterrows():
                enriched = enrich_raw_row(row.to_dict())
                if bool(enriched.get("is_noise")):
                    continue
                et = str(enriched.get("event_type") or classify_event(
                    f"{enriched.get('title','')} {enriched.get('content','')}"
                ))
                event_counter[et] += 1
                title = str(enriched.get("title") or "")[:120]
                content = str(enriched.get("content") or "")[:200]
                sc = enriched.get("ai_score", enriched.get("keyword_score", 0))
                try:
                    sc_f = float(sc)
                except (TypeError, ValueError):
                    sc_f = 0.0
                comments.append(
                    {
                        "platform": enriched.get("platform"),
                        "platform_label": platform_meta(str(enriched.get("platform", ""))).get(
                            "label_zh"
                        ),
                        "title": title,
                        "snippet": content,
                        "score": sc_f,
                        "event_type": et,
                        "authority_grade": enriched.get("authority_grade"),
                    }
                )
            comments.sort(key=lambda x: abs(float(x.get("score") or 0)), reverse=True)
            comments = comments[:top_k]

    direction = "中性"
    if score is not None:
        if score >= 0.35:
            direction = "偏多 / 强势看多"
        elif score >= 0.15:
            direction = "偏多"
        elif score <= -0.35:
            direction = "偏空 / 强势看空"
        elif score <= -0.15:
            direction = "偏空"

    top_events = [e for e, _ in event_counter.most_common(3)]
    drivers = sorted(platforms.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    why_lines = []
    if score is not None:
        why_lines.append(f"综合情感分约 {score:+.3f}（{direction}）。")
    if drivers:
        bits = ", ".join(f"{p}={v:+.2f}" for p, v in drivers)
        why_lines.append(f"主要平台驱动：{bits}。")
    if top_events:
        why_lines.append(f"高频事件类型：{', '.join(top_events)}。")
    if comments:
        why_lines.append(
            f"代表性观点：「{comments[0].get('title') or comments[0].get('snippet')}」"
            f"（{comments[0].get('event_type')} / {comments[0].get('platform_label')}）。"
        )
    if not why_lines:
        why_lines.append("暂无足够样本生成解释，请先运行 daily/realtime 采集。")

    return {
        "symbol": sym,
        "score": score,
        "direction": direction,
        "platform_drivers": dict(drivers),
        "event_types": top_events,
        "key_comments": comments,
        "summary": " ".join(why_lines),
    }
