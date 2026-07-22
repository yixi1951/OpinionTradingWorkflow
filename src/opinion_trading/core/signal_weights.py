"""Event-type and user-tier impact weights for signal construction."""

from __future__ import annotations

from typing import Dict

# Relative impact multipliers for classified events
EVENT_IMPACT_WEIGHTS: Dict[str, float] = {
    "earnings": 1.35,
    "policy": 1.25,
    "mna": 1.30,
    "risk": 1.40,
    "rumor": 0.70,
    "technical": 0.95,
    "general": 1.00,
    "industry": 1.10,
}

# User / source tier multipliers
USER_TIER_WEIGHTS: Dict[str, float] = {
    "verified": 1.40,  # 认证 / 官方
    "high_followers": 1.25,
    "analyst": 1.35,
    "retail": 1.00,
    "unknown": 0.95,
}


def event_weight(event_type: str) -> float:
    return float(EVENT_IMPACT_WEIGHTS.get(str(event_type or "general"), 1.0))


def user_tier_from_row(row: dict) -> str:
    author = str(row.get("author", row.get("user_name", "")))
    followers = row.get("followers") or row.get("follower_count") or 0
    try:
        followers = int(followers)
    except (TypeError, ValueError):
        followers = 0
    grade = str(row.get("authority_grade", "")).lower()
    blob = f"{author} {row.get('title', '')}"
    if any(x in blob for x in ("认证", "官方", "记者")) or grade == "high":
        if "分析师" in blob or "研报" in blob:
            return "analyst"
        return "verified"
    if followers >= 10000 or "大V" in blob or "意见领袖" in blob:
        return "high_followers"
    if grade == "low":
        return "retail"
    return "unknown"


def user_weight(row: dict) -> float:
    return float(USER_TIER_WEIGHTS.get(user_tier_from_row(row), 1.0))


def combined_post_weight(row: dict) -> float:
    """Combine authority × event × user tier (clamped)."""
    try:
        auth = float(row.get("authority_weight", 1.0) or 1.0)
    except (TypeError, ValueError):
        auth = 1.0
    ew = event_weight(str(row.get("event_type", "general")))
    uw = user_weight(row)
    return max(0.15, min(3.0, auth * ew * uw))
