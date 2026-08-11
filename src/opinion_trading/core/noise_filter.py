"""Garbage / spam post filters targeting noise rate <= 10%."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

# Ads / spam / water posts
SPAM_MARKERS = (
    "加微信",
    "加V",
    "加vx",
    "免费荐股",
    "荐股群",
    "内部消息私聊",
    "扫码进群",
    "代操",
    "稳赚不赔",
    "百分百收益",
    "点击领取",
    "优惠券",
    "推广",
    "广告",
    "刷单",
    "加我好友",
)

WATER_PATTERNS = (
    re.compile(r"^(哈哈|呵呵|嘿嘿|666+|111+|嗯+|哦+|啊+)+\s*$"),
    re.compile(r"^(转发|打卡|路过|顶|沙发|围观)\s*$"),
    re.compile(r"^[\W\d_]+$"),
    re.compile(r"(.)\1{5,}"),  # char spam aaaaaa
)


def is_spam_or_ad(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    low = s.lower()
    if any(m.lower() in low for m in SPAM_MARKERS):
        return True
    # URL-heavy short posts
    if s.count("http") >= 1 and len(s) < 40:
        return True
    return False


def is_water_post(text: str) -> bool:
    s = re.sub(r"\s+", "", str(text or ""))
    if len(s) < 4:
        return True
    return any(p.search(s) for p in WATER_PATTERNS)


def is_duplicate_near(text: str, seen_keys: set[str]) -> bool:
    key = re.sub(r"\s+", "", str(text or ""))[:80]
    if not key:
        return True
    if key in seen_keys:
        return True
    seen_keys.add(key)
    return False


def classify_noise(
    row: Dict[str, Any] | str, seen_keys: set[str] | None = None
) -> Tuple[bool, str]:
    """Return (is_noise, reason). Accepts a post dict or a plain text string."""
    if isinstance(row, str):
        row = {"title": "", "content": row}
    title = str(row.get("title", ""))
    content = str(row.get("content", ""))
    blob = f"{title} {content}".strip()
    if row.get("is_noise") is True:
        return True, "premarked"
    if is_spam_or_ad(blob):
        return True, "spam_ad"
    if is_water_post(blob):
        return True, "water"
    if seen_keys is not None and is_duplicate_near(blob, seen_keys):
        return True, "duplicate"
    return False, ""


def filter_noisy_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    mark_only: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Filter/mark spam water duplicates. Returns rows + stats.

    ``mark_only=True`` keeps rows but sets is_noise / noise_reason (default).
    """
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    reasons = {"spam_ad": 0, "water": 0, "duplicate": 0, "premarked": 0, "clean": 0}
    total = 0
    for row in rows:
        total += 1
        item = dict(row)
        noisy, reason = classify_noise(item, seen)
        if noisy:
            item["is_noise"] = True
            item["noise_reason"] = reason
            reasons[reason] = reasons.get(reason, 0) + 1
            if mark_only:
                out.append(item)
        else:
            item["is_noise"] = False
            item["noise_reason"] = ""
            reasons["clean"] += 1
            out.append(item)
    noise_n = total - reasons["clean"]
    stats = {
        "total": float(total),
        "noise_rate": (noise_n / total) if total else 0.0,
        "spam_ad_rate": reasons["spam_ad"] / total if total else 0.0,
        "water_rate": reasons["water"] / total if total else 0.0,
        "duplicate_rate": reasons["duplicate"] / total if total else 0.0,
        "clean_rate": reasons["clean"] / total if total else 0.0,
    }
    return out, stats
