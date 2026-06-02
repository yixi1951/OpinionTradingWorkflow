from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import yaml

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if _SCRIPTS.exists() and str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from text_quality import is_boilerplate, pick_comment_text  # noqa: E402

DEFAULT_PLATFORM_WEIGHTS: Dict[str, float] = {
    "guba": 1.40,
    "eastmoney": 1.30,
    "sina_finance": 1.15,
    "xueqiu": 1.10,
    "weibo": 0.95,
    "douyin": 1.05,
}


def load_platform_weights(
    config_path: str = "config/settings.yaml",
) -> Dict[str, float]:
    path = Path(config_path)
    if not path.exists():
        return DEFAULT_PLATFORM_WEIGHTS.copy()
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        weights = cfg.get("strategy", {}).get("platform_weights", {})
        if isinstance(weights, dict) and weights:
            return {str(k): float(v) for k, v in weights.items()}
    except Exception:
        pass
    return DEFAULT_PLATFORM_WEIGHTS.copy()


def parse_platform_scores(raw_value) -> Dict[str, float]:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return {}
    out: Dict[str, float] = {}
    for part in raw_value.split(","):
        piece = part.strip()
        if ":" not in piece:
            continue
        platform, score_text = piece.split(":", 1)
        try:
            out[platform.strip()] = float(score_text.strip())
        except ValueError:
            continue
    return out


def is_fallback_row(row: pd.Series) -> bool:
    status = str(row.get("capture_status", "")).lower()
    if status == "fallback":
        return True
    noise = row.get("is_noise")
    if noise is True or str(noise).lower() in {"true", "1"}:
        return True
    blob = f"{row.get('title', '')} {row.get('summary', '')} {row.get('content', '')}"
    markers = (
        "Fallback row generated",
        "Stub fallback",
        "fallback record",
        "stub record",
    )
    return any(m in blob for m in markers)


def clean_comment_text(row: pd.Series) -> str:
    title = str(row.get("title", "") or "")
    content = str(row.get("content", "") or "")
    summary = str(row.get("summary", "") or "")
    text = pick_comment_text(summary, title=title, content=content, summary=summary)
    if not text or is_boilerplate(text):
        if title and not is_boilerplate(title) and "Fallback" not in title:
            text = title
        else:
            return ""
    if len(text) > 220:
        return text[:217] + "…"
    return text


def filter_usable_raw(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df.empty:
        return raw_df
    view = raw_df.copy()
    mask = ~view.apply(is_fallback_row, axis=1)
    view = view[mask].copy()
    view["_display"] = view.apply(clean_comment_text, axis=1)
    view = view[view["_display"].str.len() >= 6].copy()
    return view


def top_comment_rows(
    raw_df: pd.DataFrame, symbol: str, top_n: int = 8
) -> Dict[str, pd.DataFrame]:
    usable = filter_usable_raw(raw_df)
    if usable.empty:
        return {"positive": pd.DataFrame(), "negative": pd.DataFrame()}
    view = usable[usable["symbol"] == symbol].copy()
    if view.empty:
        return {"positive": pd.DataFrame(), "negative": pd.DataFrame()}
    view["ai_score"] = pd.to_numeric(view.get("ai_score", 0), errors="coerce").fillna(
        0.0
    )
    view["display_text"] = view["_display"]
    positive = (
        view[view["ai_score"] > 0].sort_values("ai_score", ascending=False).head(top_n)
    )
    negative = (
        view[view["ai_score"] < 0].sort_values("ai_score", ascending=True).head(top_n)
    )
    if positive.empty:
        positive = view.sort_values("ai_score", ascending=False).head(top_n)
    if negative.empty:
        negative = view.sort_values("ai_score", ascending=True).head(top_n)
    return {"positive": positive, "negative": negative}


def build_pick_contribution(
    symbol: str,
    picks_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    sentiment_df: pd.DataFrame,
    lookback_days: int = 30,
) -> pd.DataFrame:
    """Merge realtime platform scores with raw-post sample counts."""
    weights_cfg = load_platform_weights()
    pick_row = picks_df[picks_df["symbol"] == symbol].head(1)
    scores = (
        parse_platform_scores(pick_row["platform_scores"].iloc[0])
        if not pick_row.empty and "platform_scores" in pick_row.columns
        else {}
    )
    if not scores and not sentiment_df.empty:
        latest = sentiment_df[sentiment_df["symbol"] == symbol].copy()
        if not latest.empty:
            latest["sentiment_score"] = pd.to_numeric(
                latest.get("sentiment_score"), errors="coerce"
            )
            latest = latest.dropna(subset=["sentiment_score"])
            if not latest.empty:
                latest = latest.sort_values("trade_date").drop_duplicates(
                    "platform", keep="last"
                )
                scores = dict(
                    zip(latest["platform"], latest["sentiment_score"].astype(float))
                )

    usable = filter_usable_raw(raw_df)
    sym_raw = usable[usable["symbol"] == symbol] if not usable.empty else pd.DataFrame()
    obs_map: Dict[str, int] = {}
    if not sym_raw.empty and "platform" in sym_raw.columns:
        obs_map = sym_raw.groupby("platform").size().to_dict()

    rows: List[dict] = []
    platforms = sorted(
        set(list(scores.keys()) + list(obs_map.keys()) + list(weights_cfg.keys()))
    )
    for platform in platforms:
        score = float(scores.get(platform, 0.0))
        cfg_w = float(weights_cfg.get(platform, 1.0))
        weighted = score * cfg_w
        rows.append(
            {
                "platform": platform,
                "platform_score": round(score, 4),
                "config_weight": cfg_w,
                "weighted_contrib": round(weighted, 4),
                "observations": int(obs_map.get(platform, 0)),
            }
        )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    abs_sum = out["weighted_contrib"].abs().sum()
    out["weight_pct"] = (
        (out["weighted_contrib"].abs() / abs_sum * 100).round(2) if abs_sum else 0.0
    )
    out["direction"] = out["platform_score"].apply(
        lambda s: "bull" if s > 0.05 else "bear" if s < -0.05 else "neutral"
    )
    return out.sort_values("weight_pct", ascending=False)


def build_pick_narrative(
    symbol: str,
    avg_score: float,
    contrib_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    lang: str = "zh",
) -> str:
    usable = filter_usable_raw(raw_df)
    n_comments = len(usable[usable["symbol"] == symbol]) if not usable.empty else 0
    active = (
        contrib_df[contrib_df["platform_score"].abs() > 0.05]
        if not contrib_df.empty
        else pd.DataFrame()
    )
    n_active = len(active)
    n_platforms = len(contrib_df) if not contrib_df.empty else 0

    if lang == "zh":
        tone = "偏多" if avg_score > 0.05 else "偏空" if avg_score < -0.05 else "中性"
        parts = [
            f"**{symbol}** 综合舆情 {avg_score:+.3f}（{tone}）。",
            f"有效评论 **{n_comments}** 条，有信号平台 **{n_active}/{n_platforms}**。",
        ]
        if not active.empty:
            drivers = []
            for _, row in active.head(3).iterrows():
                drivers.append(
                    f"{row['platform']} {row['platform_score']:+.2f}（贡献 {row['weight_pct']:.0f}%）"
                )
            parts.append("主要驱动：" + "；".join(drivers) + "。")
        else:
            parts.append("各平台分数接近 0，信号较弱，建议结合更多数据源。")
        if n_comments < 5:
            parts.append("⚠️ 样本偏少，结论仅供参考。")
        return " ".join(parts)

    tone = (
        "bullish" if avg_score > 0.05 else "bearish" if avg_score < -0.05 else "neutral"
    )
    parts = [
        f"**{symbol}** aggregate sentiment {avg_score:+.3f} ({tone}).",
        f"Valid comments: **{n_comments}**; active platforms: **{n_active}/{n_platforms}**.",
    ]
    if not active.empty:
        drivers = [
            f"{r['platform']} {r['platform_score']:+.2f} ({r['weight_pct']:.0f}%)"
            for _, r in active.head(3).iterrows()
        ]
        parts.append("Key drivers: " + "; ".join(drivers) + ".")
    if n_comments < 5:
        parts.append("⚠️ Low sample size — interpret with caution.")
    return " ".join(parts)


def evidence_stats(raw_df: pd.DataFrame, symbol: str) -> Dict[str, int]:
    total = len(raw_df[raw_df["symbol"] == symbol]) if not raw_df.empty else 0
    usable = filter_usable_raw(raw_df)
    valid = len(usable[usable["symbol"] == symbol]) if not usable.empty else 0
    fallback = total - valid
    platforms = (
        usable[usable["symbol"] == symbol]["platform"].nunique()
        if not usable.empty
        else 0
    )
    return {
        "total": total,
        "valid": valid,
        "fallback": max(0, fallback),
        "platforms": platforms,
    }


def monthly_methodology_text(lang: str = "zh") -> Tuple[str, str]:
    if lang == "zh":
        title = "月度训练与预测说明"
        body = """
**训练逻辑**：取过去 N 个月的舆情交易信号，与次日/下一周期股价涨跌对照，按月统计准确率与胜率。

**怎样算「正确」**：
- 信号为 **买入/看多** 且下一周期收益 > 0 → 正确
- 信号为 **卖出/看空** 且下一周期收益 < 0 → 正确
- 其余情况记为错误

**预测方向**：根据最近一个月信号净倾向（看多 vs 看空）与滚动成功率，给出下一月 **BULLISH / BEARISH / NEUTRAL** 参考方向（非实盘建议）。

**如何读图**：
- 折线图：各月准确率 / 胜率走势，看信号是否稳定
- 柱状图：每月信号数量，柱色越深表示当月准确率越高
- 表格：逐月明细，可用于核对具体月份表现
"""
        return title, body.strip()
    title = "Monthly training & forecast guide"
    body = """
**Training**: Compare historical sentiment signals with next-period returns, aggregated by month.

**Correct signal**: bullish + positive return, or bearish + negative return.

**Forecast direction**: Derived from latest net signal bias and rolling success rate (research only, not trading advice).

**Charts**: line = accuracy/win-rate trend; bars = signal count colored by accuracy; table = monthly breakdown.
"""
    return title, body.strip()
