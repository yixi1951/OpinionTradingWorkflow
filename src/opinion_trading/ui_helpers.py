from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yaml

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if _SCRIPTS.exists() and str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from text_quality import (
    is_boilerplate,
    is_news_article,
    is_news_headline,
    is_user_comment,
    pick_comment_text,
)  # noqa: E402

DEFAULT_PLATFORM_WEIGHTS: Dict[str, float] = {
    "guba": 1.40,
    "eastmoney": 1.30,
    "sina_finance": 1.15,
    "xueqiu": 1.10,
    "weibo": 0.95,
    "douyin": 1.05,
}

PLATFORM_LABELS: Dict[str, Dict[str, str]] = {
    "zh": {
        "guba": "股吧",
        "eastmoney": "东方财富",
        "sina_finance": "新浪财经",
        "weibo": "微博",
        "xueqiu": "雪球",
        "douyin": "抖音",
    },
    "en": {
        "guba": "Guba",
        "eastmoney": "Eastmoney",
        "sina_finance": "Sina Finance",
        "weibo": "Weibo",
        "xueqiu": "Xueqiu",
        "douyin": "Douyin",
    },
}

STOCK_NAMES: Dict[str, str] = {
    "600519": "贵州茅台",
    "000001": "平安银行",
    "601318": "中国平安",
}


def platform_label(platform: str, lang: str = "zh") -> str:
    key = str(platform or "").strip()
    if not key:
        return key
    table = PLATFORM_LABELS.get(lang, PLATFORM_LABELS["en"])
    return table.get(key, key)


def symbol_display(symbol: str, lang: str = "zh") -> str:
    text = str(symbol or "").strip().upper()
    if not text or lang != "zh":
        return text
    code = text.split(".", maxsplit=1)[0]
    name = STOCK_NAMES.get(code, "")
    if name:
        return f"{code} {name}"
    return text


def label_platform_column(
    df: pd.DataFrame, lang: str = "zh", column: str = "platform"
) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    out = df.copy()
    out[column] = out[column].astype(str).map(lambda p: platform_label(p, lang))
    return out


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


def full_comment_text(row: pd.Series) -> str:
    title = str(row.get("title", "") or "")
    content = str(row.get("content", "") or "")
    summary = str(row.get("summary", "") or "")
    text = pick_comment_text(summary, title=title, content=content, summary=summary)
    if not text or is_boilerplate(text):
        if title and not is_boilerplate(title) and "Fallback" not in title:
            text = title
        else:
            return ""
    return str(text).strip()


def clean_comment_text(row: pd.Series) -> str:
    text = full_comment_text(row)
    if not text:
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
    view["full_text"] = view.apply(full_comment_text, axis=1)
    view["_display"] = view.apply(clean_comment_text, axis=1)
    view = view[view["_display"].str.len() >= 6].copy()
    return view


def filter_comment_evidence(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Keep rows that look like user opinions, excluding news headlines."""
    view = filter_usable_raw(raw_df)
    if view.empty:
        return view
    keep = view.apply(
        lambda row: is_user_comment(
            str(row.get("full_text") or row.get("_display") or ""),
            platform=str(row.get("platform", "") or ""),
            url=str(row.get("url", "") or ""),
        ),
        axis=1,
    )
    return view[keep].copy()


def _dedupe_comment_rows(view: pd.DataFrame) -> pd.DataFrame:
    if view.empty:
        return view
    seen: set[str] = set()
    rows: List[pd.Series] = []
    platform_rank = {
        "guba": 0,
        "xueqiu": 1,
        "eastmoney": 2,
        "weibo": 3,
        "douyin": 4,
        "sina_finance": 5,
    }
    ordered = view.copy()
    ordered["_plat_rank"] = ordered["platform"].map(
        lambda p: platform_rank.get(str(p), 99)
    )
    ordered = ordered.sort_values(["_plat_rank", "ai_score"], ascending=[True, False])
    for _, row in ordered.iterrows():
        key = re.sub(r"\s+", "", str(row.get("full_text") or row.get("_display") or ""))[
            :80
        ]
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.drop(columns=["_plat_rank"], errors="ignore")


def infer_score_source(row: pd.Series) -> str:
    explicit = str(row.get("score_source", "") or "").strip().lower()
    if explicit in {"openclaw", "keyword"}:
        return explicit
    kw = pd.to_numeric(row.get("keyword_score"), errors="coerce")
    ai = pd.to_numeric(row.get("ai_score"), errors="coerce")
    if pd.notna(kw) and pd.notna(ai) and abs(float(ai) - float(kw)) > 0.0001:
        return "openclaw"
    return "keyword"


def classify_content_type(row: pd.Series) -> str:
    text = str(row.get("full_text") or row.get("_display") or "")
    platform = str(row.get("platform", "") or "")
    url = str(row.get("url", "") or "")
    if is_user_comment(text, platform=platform, url=url):
        return "user_comment"
    if is_news_headline(text, platform=platform) or is_news_article(
        text, platform=platform, url=url
    ):
        return "news"
    return "reference"


def _prepare_comment_view(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    usable = filter_usable_raw(raw_df)
    if usable.empty:
        return usable
    view = usable[usable["symbol"] == symbol].copy()
    if view.empty:
        return view
    view["ai_score"] = pd.to_numeric(view.get("ai_score", 0), errors="coerce").fillna(
        0.0
    )
    view["display_text"] = view["_display"]
    view["full_text"] = view.get("full_text", view["_display"])
    view["score_source"] = view.apply(infer_score_source, axis=1)
    view["content_type"] = view.apply(classify_content_type, axis=1)
    return view


def top_comment_rows(
    raw_df: pd.DataFrame,
    symbol: str,
    top_n: int = 12,
    *,
    include_reference: bool = True,
    ref_n: int = 8,
) -> Dict[str, pd.DataFrame]:
    all_view = _prepare_comment_view(raw_df, symbol)
    if all_view.empty:
        return {
            "positive": pd.DataFrame(),
            "negative": pd.DataFrame(),
            "reference": pd.DataFrame(),
        }

    user_view = all_view[all_view["content_type"] == "user_comment"].copy()
    if user_view.empty:
        user_view = all_view[all_view["content_type"] != "news"].copy()
    user_view = _dedupe_comment_rows(user_view)

    positive = (
        user_view[user_view["ai_score"] > 0]
        .sort_values("ai_score", ascending=False)
        .head(top_n)
    )
    negative = (
        user_view[user_view["ai_score"] < 0]
        .sort_values("ai_score", ascending=True)
        .head(top_n)
    )
    if positive.empty:
        positive = user_view.sort_values("ai_score", ascending=False).head(top_n)
    if negative.empty:
        negative = user_view.sort_values("ai_score", ascending=True).head(top_n)

    reference = pd.DataFrame()
    if include_reference:
        used_keys = {
            re.sub(r"\s+", "", str(r.get("full_text") or ""))[:80]
            for _, r in pd.concat([positive, negative], ignore_index=True).iterrows()
        }
        extras = all_view.copy()
        extras["_key"] = extras["full_text"].map(
            lambda t: re.sub(r"\s+", "", str(t))[:80]
        )
        extras = extras[~extras["_key"].isin(used_keys)].drop(columns=["_key"])
        extras = _dedupe_comment_rows(extras)
        reference = extras.sort_values("ai_score", key=abs, ascending=False).head(
            ref_n
        )

    return {"positive": positive, "negative": negative, "reference": reference}


def build_openclaw_summary(raw_df: pd.DataFrame, picks_df: pd.DataFrame) -> Dict[str, object]:
    total = len(raw_df) if not raw_df.empty else 0
    usable = filter_usable_raw(raw_df) if not raw_df.empty else pd.DataFrame()
    comments = filter_comment_evidence(raw_df) if not raw_df.empty else pd.DataFrame()
    openclaw_rows = 0
    keyword_rows = 0
    if not usable.empty:
        sources = usable.apply(infer_score_source, axis=1)
        openclaw_rows = int((sources == "openclaw").sum())
        keyword_rows = int((sources == "keyword").sum())
    return {
        "total_raw": total,
        "usable": len(usable),
        "user_comments": len(comments),
        "openclaw_scored": openclaw_rows,
        "keyword_scored": keyword_rows,
        "pick_count": len(picks_df) if not picks_df.empty else 0,
    }


def build_openclaw_activity_feed(
    raw_df: pd.DataFrame, limit: int = 25, lang: str = "zh"
) -> pd.DataFrame:
    if raw_df.empty:
        return pd.DataFrame()
    view = filter_usable_raw(raw_df).copy()
    if view.empty:
        return pd.DataFrame()
    view["ai_score"] = pd.to_numeric(view.get("ai_score", 0), errors="coerce").fillna(0.0)
    view["score_source"] = view.apply(infer_score_source, axis=1)
    view["content_type"] = view.apply(classify_content_type, axis=1)
    view = view.sort_values("fetch_time", ascending=False).head(limit)

    type_labels = {
        "zh": {
            "user_comment": "用户观点",
            "news": "新闻资讯",
            "reference": "参考文本",
            "openclaw": "OpenClaw AI",
            "keyword": "关键词",
        },
        "en": {
            "user_comment": "User opinion",
            "news": "News",
            "reference": "Reference",
            "openclaw": "OpenClaw AI",
            "keyword": "Keyword",
        },
    }.get(lang if lang in {"zh", "en"} else "en", {})

    rows: List[Dict[str, object]] = []
    for _, row in view.iterrows():
        text = str(row.get("full_text") or row.get("_display") or "")
        preview = text if len(text) <= 56 else f"{text[:56]}…"
        rows.append(
            {
                "time": str(row.get("post_time") or row.get("fetch_time") or "")[:19],
                "platform": platform_label(str(row.get("platform", "")), lang),
                "symbol": symbol_display(str(row.get("symbol", "")), lang),
                "preview": preview,
                "score": f"{float(row.get('ai_score', 0)):+.3f}",
                "engine": type_labels.get(
                    str(row.get("score_source", "keyword")), "Keyword"
                ),
                "type": type_labels.get(
                    str(row.get("content_type", "reference")), "Reference"
                ),
            }
        )
    col_labels = {
        "zh": {
            "time": "时间",
            "platform": "平台",
            "symbol": "股票",
            "preview": "文本摘要",
            "score": "情感分",
            "engine": "分析引擎",
            "type": "内容类型",
        },
        "en": {
            "time": "Time",
            "platform": "Platform",
            "symbol": "Symbol",
            "preview": "Preview",
            "score": "Score",
            "engine": "Engine",
            "type": "Type",
        },
    }.get(lang if lang in {"zh", "en"} else "en", {})
    df = pd.DataFrame(rows)
    return df.rename(columns=col_labels)


def build_picks_detail_table(picks_df: pd.DataFrame, lang: str = "zh") -> pd.DataFrame:
    """Expand picks into a readable table with localized column names."""
    labels = {
        "zh": {
            "rank": "排名",
            "symbol": "股票",
            "avg_score": "综合情感分",
            "tone": "情感倾向",
            "platform": "平台",
            "platform_score": "平台情感分",
        },
        "en": {
            "rank": "Rank",
            "symbol": "Symbol",
            "avg_score": "Avg sentiment",
            "tone": "Tone",
            "platform": "Platform",
            "platform_score": "Platform score",
        },
    }[lang if lang in {"zh", "en"} else "en"]

    if picks_df.empty:
        return pd.DataFrame(columns=list(labels.values()))

    view = picks_df.copy()
    view["avg_score"] = pd.to_numeric(view.get("avg_score"), errors="coerce").fillna(0.0)
    view = view.sort_values("avg_score", ascending=False).reset_index(drop=True)

    def _tone(score: float) -> str:
        if lang == "zh":
            return "偏多" if score > 0.05 else "偏空" if score < -0.05 else "中性"
        return "bullish" if score > 0.05 else "bearish" if score < -0.05 else "neutral"

    rows: List[Dict[str, object]] = []
    for rank, (_, row) in enumerate(view.iterrows(), start=1):
        symbol = str(row.get("symbol", ""))
        avg = float(row.get("avg_score", 0.0))
        tone = _tone(avg)
        scores = parse_platform_scores(row.get("platform_scores", ""))
        if scores:
            for platform, pscore in sorted(
                scores.items(), key=lambda x: abs(x[1]), reverse=True
            ):
                rows.append(
                    {
                        labels["rank"]: rank,
                        labels["symbol"]: symbol_display(symbol, lang),
                        labels["avg_score"]: f"{avg:+.4f}",
                        labels["tone"]: tone,
                        labels["platform"]: platform_label(platform, lang),
                        labels["platform_score"]: f"{pscore:+.3f}",
                    }
                )
        else:
            rows.append(
                {
                    labels["rank"]: rank,
                    labels["symbol"]: symbol_display(symbol, lang),
                    labels["avg_score"]: f"{avg:+.4f}",
                    labels["tone"]: tone,
                    labels["platform"]: "—",
                    labels["platform_score"]: "—",
                }
            )
    return pd.DataFrame(rows)


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

    usable = filter_comment_evidence(raw_df)
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
    usable = filter_comment_evidence(raw_df)
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
            f"**{symbol_display(symbol, lang)}** 综合舆情 {avg_score:+.3f}（{tone}）。",
            f"有效评论 **{n_comments}** 条，有信号平台 **{n_active}/{n_platforms}**。",
        ]
        if not active.empty:
            drivers = []
            for _, row in active.head(3).iterrows():
                drivers.append(
                    f"{platform_label(row['platform'], lang)} {row['platform_score']:+.2f}（贡献 {row['weight_pct']:.0f}%）"
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
            f"{platform_label(r['platform'], lang)} {r['platform_score']:+.2f} ({r['weight_pct']:.0f}%)"
            for _, r in active.head(3).iterrows()
        ]
        parts.append("Key drivers: " + "; ".join(drivers) + ".")
    if n_comments < 5:
        parts.append("⚠️ Low sample size — interpret with caution.")
    return " ".join(parts)


def evidence_stats(raw_df: pd.DataFrame, symbol: str) -> Dict[str, int]:
    sym = raw_df[raw_df["symbol"] == symbol] if not raw_df.empty else pd.DataFrame()
    total = len(sym)
    usable = filter_usable_raw(raw_df)
    comments = filter_comment_evidence(raw_df)
    valid = len(comments[comments["symbol"] == symbol]) if not comments.empty else 0
    raw_valid = len(usable[usable["symbol"] == symbol]) if not usable.empty else 0
    news_filtered = max(0, raw_valid - valid)
    fallback = total - raw_valid
    platforms = (
        comments[comments["symbol"] == symbol]["platform"].nunique()
        if not comments.empty
        else 0
    )
    return {
        "total": total,
        "valid": valid,
        "fallback": max(0, fallback),
        "news_filtered": news_filtered,
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
