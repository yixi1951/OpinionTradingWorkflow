"""Watchlist alert evaluation + multi-channel push (email / wecom / inbox)."""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import pandas as pd

from opinion_trading.core.alert_notifier import AlertNotifier
from opinion_trading.core.user_workspace import AlertRule, UserWorkspace


def _latest_symbol_stats(sentiment_df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
    if sentiment_df.empty or "symbol" not in sentiment_df.columns:
        return {}
    sub = sentiment_df[sentiment_df["symbol"].astype(str).str.upper() == symbol.upper()].copy()
    if sub.empty:
        return {}
    if "trade_date" in sub.columns:
        sub["trade_date"] = pd.to_datetime(sub["trade_date"], errors="coerce")
        sub = sub.dropna(subset=["trade_date"]).sort_values("trade_date")
    score_col = "sentiment_score" if "sentiment_score" in sub.columns else None
    if score_col is None:
        return {}
    # daily mean score + post heat
    if "trade_date" in sub.columns:
        if "post_count" in sub.columns:
            daily = (
                sub.groupby(sub["trade_date"].dt.date)
                .agg(score=(score_col, "mean"), heat=("post_count", "sum"))
                .reset_index()
            )
        else:
            daily = (
                sub.groupby(sub["trade_date"].dt.date)
                .agg(score=(score_col, "mean"), heat=(score_col, "count"))
                .reset_index()
            )
        daily.columns = ["trade_date", "score", "heat"]
        if daily.empty:
            return {}
        latest = daily.iloc[-1]
        prev = daily.iloc[-2] if len(daily) >= 2 else None
        return {
            "score": float(latest["score"]),
            "heat": float(latest["heat"]),
            "prev_score": float(prev["score"]) if prev is not None else None,
            "prev_heat": float(prev["heat"]) if prev is not None else None,
            "trade_date": str(latest["trade_date"]),
        }
    return {
        "score": float(sub[score_col].mean()),
        "heat": float(sub["post_count"].sum())
        if "post_count" in sub.columns
        else float(len(sub)),
        "prev_score": None,
        "prev_heat": None,
        "trade_date": "",
    }


def evaluate_user_alerts(
    username: str,
    sentiment_df: pd.DataFrame,
    *,
    workspace: Optional[UserWorkspace] = None,
) -> List[Dict[str, Any]]:
    """Check watchlist alert rules; return triggered events."""
    ws = workspace or UserWorkspace()
    profile = ws.load_profile(username)
    if not profile:
        return []
    triggered: List[Dict[str, Any]] = []
    for raw in profile.alert_rules:
        if not bool(raw.get("enabled", True)):
            continue
        rule = AlertRule(
            symbol=str(raw.get("symbol", "")),
            score_high=float(raw.get("score_high", 0.35)),
            score_low=float(raw.get("score_low", -0.35)),
            heat_spike_ratio=float(raw.get("heat_spike_ratio", 2.0)),
            enabled=True,
        )
        if not rule.symbol:
            continue
        stats = _latest_symbol_stats(sentiment_df, rule.symbol)
        if not stats:
            continue
        score = float(stats["score"])
        reasons = []
        if score >= rule.score_high:
            reasons.append(f"情感分 {score:.3f} ≥ 阈值 {rule.score_high}")
        if score <= rule.score_low:
            reasons.append(f"情感分 {score:.3f} ≤ 阈值 {rule.score_low}")
        prev_heat = stats.get("prev_heat")
        heat = float(stats.get("heat") or 0)
        if prev_heat and prev_heat > 0 and heat / prev_heat >= rule.heat_spike_ratio:
            reasons.append(
                f"舆情热度突增 {heat:.0f}/{prev_heat:.0f} (≥{rule.heat_spike_ratio}x)"
            )
        if not reasons:
            continue
        event = {
            "username": username,
            "symbol": rule.symbol,
            "score": score,
            "heat": heat,
            "trade_date": stats.get("trade_date", ""),
            "reasons": reasons,
            "severity": "red" if score <= rule.score_low else "yellow",
            "direction": "up" if score >= rule.score_high else "down",
            "previous_score": stats.get("prev_score") or 0.0,
            "current_score": score,
            "delta": float(score - (stats.get("prev_score") or 0.0)),
            "time": datetime.now().isoformat(timespec="seconds"),
            "channel_hint": "watchlist_alert",
        }
        triggered.append(event)
    return triggered


def _send_email(to_addr: str, subject: str, body: str) -> Dict[str, Any]:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    from_addr = os.environ.get("SMTP_FROM", user).strip()
    if not host or not to_addr or not from_addr:
        return {"enabled": False, "ok": False, "detail": "SMTP not configured"}
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to_addr], msg.as_string())
        return {"enabled": True, "ok": True, "detail": "sent"}
    except Exception as exc:
        return {"enabled": True, "ok": False, "detail": str(exc)[:160]}


def dispatch_alert_event(
    event: Dict[str, Any],
    *,
    email: str = "",
    workspace: Optional[UserWorkspace] = None,
) -> Dict[str, Any]:
    """Push to inbox + WeCom/DingTalk/Telegram + optional email."""
    ws = workspace or UserWorkspace()
    username = str(event.get("username", "demo"))
    reasons = "; ".join(event.get("reasons") or [])
    title = f"[预警] {event.get('symbol')} {reasons}"
    ws.push_inbox(
        username,
        {
            "type": "alert",
            "title": title,
            "symbol": event.get("symbol"),
            "score": event.get("score"),
            "reasons": event.get("reasons"),
            "trade_date": event.get("trade_date"),
        },
    )
    notifier = AlertNotifier()
    push = notifier.push_alert(event)
    email_result = _send_email(
        email,
        subject=title[:80],
        body=(
            f"{title}\n"
            f"date={event.get('trade_date')}\n"
            f"score={event.get('score')}\n"
            f"heat={event.get('heat')}\n"
            "免责声明：本系统仅为舆情数据统计分析，不构成任何投资建议。"
        ),
    )
    return {"inbox": True, "push": push, "email": email_result}


def run_watchlist_alert_cycle(
    username: str,
    sentiment_df: pd.DataFrame,
    *,
    workspace: Optional[UserWorkspace] = None,
) -> List[Dict[str, Any]]:
    ws = workspace or UserWorkspace()
    profile = ws.load_profile(username)
    events = evaluate_user_alerts(username, sentiment_df, workspace=ws)
    results = []
    for ev in events:
        results.append(
            {
                "event": ev,
                "dispatch": dispatch_alert_event(
                    ev, email=profile.email if profile else "", workspace=ws
                ),
            }
        )
    return results
