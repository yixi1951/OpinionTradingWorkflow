"""Deep semantic enrichment for raw social/finance posts.

Provides platform taxonomy, ticker entity matching, author authority grading,
and lightweight event classification — rule-based, suitable for student-scale
pipelines without external NLP services.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from opinion_trading.core.symbol_map import get_symbol_mapper

# Platform channel taxonomy (中文业务类型) — 6 大源 + 权威信源扩展位
PLATFORM_TYPES: Dict[str, Dict[str, str]] = {
    "guba": {"type": "forum", "label_zh": "股吧社区", "tier": "ugc"},
    "eastmoney": {"type": "portal", "label_zh": "东方财富门户", "tier": "ugc"},
    "sina_finance": {"type": "news", "label_zh": "财经新闻", "tier": "ugc"},
    "weibo": {"type": "social", "label_zh": "微博财经", "tier": "ugc"},
    "xueqiu": {"type": "investor_community", "label_zh": "雪球", "tier": "ugc"},
    "zhihu": {"type": "qa_community", "label_zh": "知乎", "tier": "ugc"},
    "douyin": {"type": "short_video", "label_zh": "短视频", "tier": "ugc"},
    "cninfo": {"type": "disclosure", "label_zh": "巨潮公告", "tier": "authoritative"},
    "broker_report": {"type": "research", "label_zh": "券商研报摘要", "tier": "authoritative"},
}

_TYPE_AUTHORITY: Dict[str, float] = {
    "disclosure": 1.30,
    "research": 1.25,
    "news": 1.15,
    "portal": 1.10,
    "investor_community": 1.05,
    "qa_community": 1.00,
    "forum": 0.95,
    "social": 0.80,
    "short_video": 0.75,
}

# Re-export seed aliases for backward compatibility

_EVENT_RULES: List[tuple[str, tuple[str, ...]]] = [
    ("earnings", ("业绩", "财报", "净利", "营收", "季报", "年报", "超预期", "低于预期")),
    ("policy", ("政策", "监管", "央行", "降准", "降息", "证监会", "国务院", "补贴")),
    ("mna", ("并购", "重组", "收购", "定增", "增持", "减持", "回购")),
    ("rumor", ("传闻", "据说", "小道", "爆料", "疑似")),
    ("technical", ("突破", "跌破", "放量", "缩量", "金叉", "死叉", "支撑", "压力", "涨停", "跌停")),
    ("risk", ("爆雷", "立案", "处罚", "退市", "造假", "亏损", "暴雷")),
]

_CODE_RE = re.compile(r"(?<!\d)([0-6]\d{5})(?!\d)")
_VIP_MARKERS = ("认证", "官方", "记者", "分析师", "研报", "VIP", "大V", "意见领袖")
_RETAIL_MARKERS = ("打卡", "路过", "求带", "跟风", "梭哈", "加仓了吗", "今天亏")


@dataclass
class SemanticEnrichment:
    platform_type: str
    platform_label_zh: str
    entity_matched: bool
    matched_tokens: List[str]
    authority_grade: str  # high | medium | low
    authority_weight: float
    event_type: str
    content_kind: str  # comment | news | mixed | noise


def platform_meta(platform: str) -> Dict[str, str]:
    meta = PLATFORM_TYPES.get(str(platform).strip().lower())
    if meta:
        return dict(meta)
    return {"type": "unknown", "label_zh": "未知来源"}


def match_entities(
    text: str,
    symbol: str,
    *,
    aliases: Optional[Mapping[str, Sequence[str]]] = None,
) -> tuple[bool, List[str]]:
    """Bind post text to the target symbol via code / alias mentions."""
    if aliases:
        # Ad-hoc map for this call
        from opinion_trading.core.symbol_map import SymbolMapper

        mapper = SymbolMapper(aliases)
        return mapper.match_symbol(text, symbol)
    mapper = get_symbol_mapper()
    return mapper.match_symbol(text, symbol)


def classify_event(text: str) -> str:
    blob = str(text or "")
    scores: Dict[str, int] = {}
    for event, kws in _EVENT_RULES:
        hit = sum(1 for kw in kws if kw in blob)
        if hit:
            scores[event] = hit
    if not scores:
        return "general"
    best = max(scores.values())
    # Tie-break: prefer rumor when tied (often co-occurs with M&A verbs)
    tied = [name for name, sc in scores.items() if sc == best]
    if "rumor" in tied:
        return "rumor"
    return max(scores.items(), key=lambda kv: kv[1])[0]


def classify_content_kind(text: str, platform_type: str) -> str:
    blob = str(text or "")
    news_markers = ("据悉", "报道", "新华社", "证券时报", "财联社", "公告称", "发布公告")
    if any(m in blob for m in news_markers) or platform_type in {"news", "portal"}:
        if len(blob) >= 40:
            return "news"
        return "mixed"
    if len(blob) < 8:
        return "noise"
    return "comment"


def grade_authority(
    *,
    platform: str,
    text: str,
    entity_matched: bool,
    author: str = "",
    content_kind: str = "comment",
) -> tuple[str, float]:
    meta = platform_meta(platform)
    base = float(_TYPE_AUTHORITY.get(meta["type"], 0.85))
    blob = f"{author} {text}"
    bonus = 0.0
    if any(m in blob for m in _VIP_MARKERS):
        bonus += 0.20
    if content_kind == "news":
        bonus += 0.10
    if entity_matched:
        bonus += 0.05
    else:
        bonus -= 0.25
    if any(m in blob for m in _RETAIL_MARKERS):
        bonus -= 0.15
    # Longer structured text slightly more authoritative
    length = len(str(text or ""))
    if length >= 80:
        bonus += 0.05
    elif length < 15:
        bonus -= 0.10

    weight = max(0.35, min(1.35, base + bonus))
    if weight >= 1.05:
        grade = "high"
    elif weight >= 0.80:
        grade = "medium"
    else:
        grade = "low"
    return grade, round(weight, 4)


def enrich_raw_row(
    row: Mapping[str, Any],
    *,
    aliases: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, Any]:
    out = dict(row)
    platform = str(out.get("platform", ""))
    symbol = str(out.get("symbol", ""))
    title = str(out.get("title", ""))
    content = str(out.get("content", ""))
    author = str(out.get("author", out.get("user_name", "")))
    text = f"{title} {content}".strip()

    meta = platform_meta(platform)
    matched, tokens = match_entities(text, symbol, aliases=aliases)
    # Crawler rows already scoped to a symbol page → treat as matched if capture ok
    if not matched and str(out.get("capture_status", "success")).lower() == "success":
        matched = True
        if symbol.split(".", 1)[0] not in tokens:
            tokens = tokens + [symbol.split(".", 1)[0]]

    event_type = classify_event(text)
    content_kind = classify_content_kind(text, meta["type"])
    if bool(out.get("is_noise")):
        content_kind = "noise"
    grade, weight = grade_authority(
        platform=platform,
        text=text,
        entity_matched=matched,
        author=author,
        content_kind=content_kind,
    )

    out["platform_type"] = meta["type"]
    out["platform_label_zh"] = meta["label_zh"]
    out["entity_matched"] = matched
    out["matched_tokens"] = ",".join(tokens)
    out["authority_grade"] = grade
    out["authority_weight"] = weight
    out["event_type"] = event_type
    out["content_kind"] = content_kind
    return out


def enrich_raw_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    aliases: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[Dict[str, Any]]:
    return [enrich_raw_row(r, aliases=aliases) for r in rows]


def semantic_quality_stats(rows: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    total = len(rows)
    if total == 0:
        return {
            "entity_match_rate": 0.0,
            "high_authority_rate": 0.0,
            "news_share": 0.0,
            "comment_share": 0.0,
        }
    ent = sum(1 for r in rows if bool(r.get("entity_matched")))
    high = sum(1 for r in rows if str(r.get("authority_grade", "")) == "high")
    news = sum(1 for r in rows if str(r.get("content_kind", "")) == "news")
    comment = sum(1 for r in rows if str(r.get("content_kind", "")) == "comment")
    return {
        "entity_match_rate": ent / total,
        "high_authority_rate": high / total,
        "news_share": news / total,
        "comment_share": comment / total,
    }
