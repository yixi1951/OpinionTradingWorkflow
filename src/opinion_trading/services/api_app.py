"""Presentation API — thin facade over compute/collector/inference."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import Cookie, HTTPException, Response
from pydantic import BaseModel, Field

from opinion_trading.core.auth_db import AuthUser
from opinion_trading.core.auth_service import AuthService
from opinion_trading.services.clients import (
    collector_client,
    compute_client,
    inference_client,
)
from opinion_trading.services.common import create_service_app

app, metrics = create_service_app("api")
_auth = AuthService()
_SESSION_TTL = 60 * 60 * 24 * 7


def _public_user(user: AuthUser) -> Dict[str, Any]:
    payload = user.public()
    payload["watchlist"] = _auth.db.watchlist(user.id)
    return payload


def _session_user(session: Optional[str]) -> AuthUser:
    if not session:
        raise HTTPException(status_code=401, detail="请先登录研究工作台")
    try:
        user, _csrf = _auth.db.session_user(session)
        return user
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录") from exc


def _set_session(response: Response, user: AuthUser) -> Dict[str, Any]:
    token, csrf, expires = _auth.db.create_session(user.id, _SESSION_TTL)
    response.set_cookie("ot_session", token, httponly=True, samesite="lax", secure=os.environ.get("APP_ENV") == "prod", max_age=_SESSION_TTL, path="/")
    response.set_cookie("ot_csrf", csrf, httponly=False, samesite="lax", secure=os.environ.get("APP_ENV") == "prod", max_age=_SESSION_TTL, path="/")
    return {"user": _public_user(user), "expires_at": expires, "csrf_token": csrf}


class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    email: str = ""


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=256)


class RoleUpdateRequest(BaseModel):
    roles: List[str]


class WatchRequest(BaseModel):
    symbol: str = Field(min_length=6, max_length=12)


@app.post("/v1/auth/login")
def login(req: AuthRequest, response: Response) -> Dict[str, Any]:
    user = _auth.db.authenticate(req.username.strip(), req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"ok": True, **_set_session(response, user)}


@app.post("/v1/auth/register", status_code=201)
def register(req: AuthRequest, response: Response) -> Dict[str, Any]:
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少需要 8 个字符")
    try:
        user = _auth.register(req.username, req.password, req.email.strip())
    except ValueError as exc:
        detail = "用户名已存在" if str(exc) == "user exists" else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
    return {"ok": True, **_set_session(response, user)}


@app.get("/v1/auth/me")
def me(ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    return {"ok": True, "user": _public_user(_session_user(ot_session))}


@app.post("/v1/auth/logout")
def logout(response: Response) -> Dict[str, Any]:
    response.delete_cookie("ot_session", path="/")
    response.delete_cookie("ot_csrf", path="/")
    return {"ok": True}


@app.get("/v1/auth/verify-email")
def verify_email(token: str) -> Dict[str, Any]:
    user_id = _auth.db.consume_token(token, "verify_email")
    if not user_id:
        raise HTTPException(status_code=400, detail="验证链接无效或已过期")
    _auth.db.set_email_verified(user_id)
    return {"ok": True, "message": "邮箱验证成功，请返回研究工作台登录"}


@app.post("/v1/auth/verify-email/resend")
def resend_verification(ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    user = _session_user(ot_session)
    if user.email_verified:
        return {"ok": True, "message": "邮箱已验证"}
    try:
        result = _auth.send_verification(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "验证邮件已发送", "delivery": result.get("mode", "smtp")}


@app.post("/v1/auth/password-reset/request")
def request_password_reset(req: PasswordResetRequest) -> Dict[str, Any]:
    try:
        result = _auth.request_password_reset(req.email)
    except Exception:
        # Do not disclose SMTP configuration or whether an account exists.
        result = {"ok": True}
    return {"ok": True, "message": "如果邮箱已注册，重置链接会发送到该邮箱", "delivery": result.get("mode", "smtp")}


@app.post("/v1/auth/password-reset/confirm")
def confirm_password_reset(req: PasswordResetConfirm) -> Dict[str, Any]:
    try:
        _auth.reset_password(req.token, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "密码已重置，请重新登录"}


def _require_role(user: AuthUser, *roles: str) -> None:
    if not _auth.db.has_role(user.id, *roles):
        raise HTTPException(status_code=403, detail="当前账户没有执行此操作的权限")


@app.get("/v1/admin/users")
def admin_users(ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    user = _session_user(ot_session)
    _require_role(user, "admin")
    return {"ok": True, "users": [u.public() for u in _auth.db.list_users()]}


@app.put("/v1/admin/users/{user_id}/roles")
def update_user_roles(user_id: int, req: RoleUpdateRequest, ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    actor = _session_user(ot_session)
    _require_role(actor, "admin")
    try:
        _auth.db.set_roles(user_id, req.roles)
        target = _auth.db.user_by_id(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "user": _public_user(target)}


def _latest_pick_rows() -> List[Dict[str, Any]]:
    candidates = sorted(Path("data/reports").glob("realtime_picks_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return []
    try:
        frame = pd.read_csv(candidates[0])
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    for _, row in frame.head(20).iterrows():
        platforms = []
        for part in str(row.get("platform_scores", "")).split(","):
            if ":" not in part:
                continue
            name, score = part.strip().split(":", 1)
            try:
                platforms.append({"name": name, "score": float(score)})
            except ValueError:
                continue
        try:
            score = float(row.get("avg_score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        try:
            samples = int(row.get("samples", 0))
        except (TypeError, ValueError):
            samples = 0
        rows.append({"symbol": str(row.get("symbol", "")), "score": score, "samples": samples, "platforms": platforms})
    return [r for r in rows if r["symbol"]]


def _raw_frame() -> pd.DataFrame:
    candidates = sorted(Path("data/raw").glob("raw_posts_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return pd.DataFrame()
    try:
        return pd.read_csv(candidates[0]).fillna("")
    except Exception:
        return pd.DataFrame()


def _quality_summary(frame: pd.DataFrame) -> Dict[str, Any]:
    monitor = sorted(Path("data/reports").glob("quality_monitor_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    text = monitor[0].read_text(encoding="utf-8") if monitor else ""
    match = re.search(r"noise_rate\s*:\s*([0-9.]+)%", text)
    noise = float(match.group(1)) if match else float(pd.to_numeric(frame.get("is_noise", pd.Series(dtype=float)), errors="coerce").fillna(0).mean() * 100 or 0)
    status = "ALERT" if noise > 10 else "PASS"
    return {"status": status, "message": f"噪声率 {noise:.1f}%，质量门槛为 10%" if status == "ALERT" else f"噪声率 {noise:.1f}%，在当前门槛内", "noise_rate": round(noise, 1)}


def _dashboard_payload(username: str) -> Dict[str, Any]:
    picks = _latest_pick_rows()
    frame = _raw_frame()
    platforms = int(frame["platform"].nunique()) if not frame.empty and "platform" in frame else 0
    symbols = int(frame["symbol"].nunique()) if not frame.empty and "symbol" in frame else len(picks)
    samples = len(frame)
    news_share = round(float((frame.get("content_kind", pd.Series(dtype=str)).astype(str).str.lower() == "news").mean() * 100), 1) if samples else 0
    comment_share = round(float((frame.get("content_kind", pd.Series(dtype=str)).astype(str).str.lower().isin(["comment", "ugc", "forum"])).mean() * 100), 1) if samples else 0
    quality = _quality_summary(frame)
    profile = _auth.db.find_user(username)
    evaluation = {"accuracy": 44.44, "sharpe": -2.2497}
    report = Path("data/reports/walk_forward_report.md")
    if report.exists():
        text = report.read_text(encoding="utf-8")
        acc = re.search(r"平均测试集准确率:\s*\*\*([0-9.]+)%", text)
        sharpe = re.search(r"平均测试 Sharpe-like:\s*\*\*([-0-9.]+)", text)
        if acc:
            evaluation["accuracy"] = float(acc.group(1))
        if sharpe:
            evaluation["sharpe"] = float(sharpe.group(1))
    return {"summary": {"symbols": symbols, "samples": samples, "platforms": platforms, "news_share": news_share, "comment_share": comment_share, "noise_share": quality["noise_rate"]}, "quality": quality, "evaluation": evaluation, "picks": picks, "watchlist": _auth.db.watchlist(profile.id) if profile else []}


@app.get("/v1/workspace/dashboard")
def dashboard(ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    return {"ok": True, **_dashboard_payload(_session_user(ot_session).username)}


@app.post("/v1/workspace/watchlist")
def add_watch(req: WatchRequest, ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    user = _session_user(ot_session)
    symbol = req.symbol.strip().upper()
    if not re.fullmatch(r"\d{6}\.(SH|SZ|HK)", symbol):
        raise HTTPException(status_code=400, detail="请输入形如 600519.SH 的股票代码")
    return {"ok": True, "watchlist": _auth.db.add_watch(user.id, symbol)}


@app.delete("/v1/workspace/watchlist/{symbol}")
def remove_watch(symbol: str, ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    return {"ok": True, "watchlist": _auth.db.remove_watch(_session_user(ot_session).id, symbol)}


@app.get("/v1/research/evidence")
def evidence(symbol: str, ot_session: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    _session_user(ot_session)
    frame = _raw_frame()
    symbol = symbol.strip().upper()
    if frame.empty:
        return {"ok": True, "symbol": symbol, "score": 0, "summary": "当前没有可展示的原始证据。", "items": []}
    rows = frame[frame.get("symbol", pd.Series(dtype=str)).astype(str).str.upper() == symbol].copy()
    if rows.empty:
        return {"ok": True, "symbol": symbol, "score": 0, "summary": "当前采集批次没有该标的证据。", "items": []}
    rows["_score"] = pd.to_numeric(rows.get("ai_score", rows.get("keyword_score", 0)), errors="coerce").fillna(0)
    rows = rows.sort_values("_score", key=lambda s: s.abs(), ascending=False).head(24)
    items = []
    for _, row in rows.iterrows():
        items.append({"title": str(row.get("title", "")), "content": str(row.get("content", row.get("summary", ""))), "url": str(row.get("url", "")), "platform": str(row.get("platform", "")), "post_time": str(row.get("post_time", row.get("trade_date", ""))), "score": round(float(row.get("_score", 0)), 3), "kind": str(row.get("content_kind", "news"))})
    score = round(float(pd.to_numeric(rows["_score"], errors="coerce").mean()), 3)
    return {"ok": True, "symbol": symbol, "score": score, "summary": f"本批次收集 {len(items)} 条相关内容，其中新闻与资料会单独标记。", "items": items}


class RunDailyRequest(BaseModel):
    trade_date: Optional[str] = None
    collect: bool = False
    fast_daily: bool = True
    top_n: int = 5


@app.get("/v1/status")
def status() -> Dict[str, Any]:
    out: Dict[str, Any] = {"api": "ok"}
    for name, client_fn in (
        ("collector", collector_client),
        ("inference", inference_client),
        ("compute", compute_client),
    ):
        try:
            out[name] = client_fn().get("/health")
        except Exception as exc:
            out[name] = {"status": "down", "error": str(exc)[:120]}
    return out


@app.post("/v1/run/daily")
def run_daily(req: RunDailyRequest) -> Dict[str, Any]:
    """Orchestrate optional collect → compute; inference is used inside pipeline."""
    metrics.inc("api_run_daily_total")
    collect_result = None
    if req.collect:
        try:
            collect_result = collector_client().post(
                "/v1/collect",
                {"trade_date": req.trade_date},
            )
        except Exception as exc:
            collect_result = {"ok": False, "error": str(exc)[:200]}
    compute_result = compute_client().post(
        "/v1/compute/daily",
        {
            "trade_date": req.trade_date,
            "fast_daily": req.fast_daily or bool(collect_result and collect_result.get("ok")),
            "top_n": req.top_n,
        },
    )
    return {"collect": collect_result, "compute": compute_result}


@app.get("/v1/picks")
def picks(top_n: int = 5) -> Dict[str, Any]:
    try:
        return compute_client().get(f"/v1/picks/latest?top_n={top_n}")
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "picks": []}


class ScoreProxyRequest(BaseModel):
    texts: List[str] = Field(default_factory=list)
    scenario: str = "sentiment"


@app.post("/v1/score")
def score(req: ScoreProxyRequest) -> Dict[str, Any]:
    return inference_client().post(
        "/v1/score", {"texts": req.texts, "scenario": req.scenario}
    )


def _mount_web_app() -> None:
    """Serve the compiled web app from the same origin as the public API."""
    dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    if not dist.is_dir():
        return
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")


# Admin key routes must register before the SPA catch-all mount.
from opinion_trading.services.admin_keys import mount_admin_keys  # noqa: E402

mount_admin_keys(app)
_mount_web_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "opinion_trading.services.api_app:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
