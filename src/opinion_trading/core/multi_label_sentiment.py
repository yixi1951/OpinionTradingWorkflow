"""Multi-label sentiment scaffold (bullish / bearish / uncertainty tags)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

_BULL = (
    "上涨",
    "利好",
    "突破",
    "增长",
    "看多",
    "反弹",
    "盈利",
    "强势",
    "买入",
    "乐观",
    "增持",
    "超预期",
)
_BEAR = (
    "下跌",
    "利空",
    "风险",
    "暴跌",
    "看空",
    "回撤",
    "亏损",
    "弱势",
    "卖出",
    "悲观",
    "减持",
    "暴雷",
)
_UNCERT = (
    "观望",
    "分歧",
    "不确定",
    "震荡",
    "中性",
    "等待",
    "待定",
    "或许",
    "可能",
    "关注",
)


@dataclass
class MultiLabelSentimentConfig:
    enabled: bool = False
    attach_scalar: bool = False  # when True, may adjust keyword_score (default off)


def load_multi_label_sentiment_config(
    raw: Optional[dict] = None,
) -> MultiLabelSentimentConfig:
    import os

    scoring = (raw or {}).get("scoring", {}) or {}
    block = scoring.get("multi_label_sentiment", {}) or {}
    env_on = os.environ.get("MULTI_LABEL_SENTIMENT", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False
    return MultiLabelSentimentConfig(
        enabled=enabled,
        attach_scalar=bool(block.get("attach_scalar", False)),
    )


def infer_multi_labels(text: str) -> Dict[str, float]:
    """Return tag strengths in [0,1] for bullish, bearish, uncertainty."""
    t = str(text or "")
    bull = sum(t.count(w) for w in _BULL)
    bear = sum(t.count(w) for w in _BEAR)
    unc = sum(t.count(w) for w in _UNCERT)
    total = bull + bear + unc
    if total <= 0:
        return {"bullish": 0.0, "bearish": 0.0, "uncertainty": 1.0}
    return {
        "bullish": min(1.0, bull / (total + 2)),
        "bearish": min(1.0, bear / (total + 2)),
        "uncertainty": min(1.0, (unc + 1) / (total + 3)),
    }


def labels_to_schema(tags: Dict[str, float]) -> Dict[str, Any]:
    """JSON-serializable multi-label payload on a raw row."""
    dominant = max(tags, key=tags.get)
    return {
        "tags": {k: round(float(v), 4) for k, v in tags.items()},
        "dominant": dominant,
    }


def enrich_rows_multi_label(
    rows: List[Dict[str, Any]],
    *,
    config: MultiLabelSentimentConfig,
) -> List[Dict[str, Any]]:
    if not config.enabled:
        return rows
    out: List[Dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        title = str(row.get("title") or "")
        body = str(row.get("content") or row.get("summary") or "")
        tags = infer_multi_labels(f"{title} {body}")
        new_row["sentiment_labels"] = labels_to_schema(tags)
        if config.attach_scalar:
            scalar = tags["bullish"] - tags["bearish"]
            if "keyword_score" not in new_row or new_row.get("keyword_score") in (
                None,
                "",
            ):
                new_row["keyword_score"] = max(-1.0, min(1.0, scalar))
        out.append(new_row)
    return out


def batch_infer_multi_labels(texts: Sequence[str]) -> List[Dict[str, Any]]:
    return [labels_to_schema(infer_multi_labels(t)) for t in texts]
