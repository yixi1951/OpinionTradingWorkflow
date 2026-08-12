"""Application-facing authentication and RBAC helpers."""

from __future__ import annotations

import re
import os
from typing import Dict, Optional

from opinion_trading.core.auth_db import AuthDatabase, AuthUser, get_auth_database
from opinion_trading.core.email_service import send_transactional_email


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthService:
    def __init__(self, db: Optional[AuthDatabase] = None) -> None:
        self.db = db or get_auth_database()

    def register(self, username: str, password: str, email: str = "") -> AuthUser:
        email = email.strip().lower()
        if email and not EMAIL_RE.fullmatch(email):
            raise ValueError("邮箱格式不正确")
        user = self.db.create_user(username, password, email, verified=False)
        if email:
            self.send_verification(user)
        return user

    def send_verification(self, user: AuthUser) -> Dict[str, object]:
        if not user.email:
            raise ValueError("请先绑定邮箱")
        token = self.db.issue_token(user.id, "verify_email", 24 * 3600)
        base = (os.environ.get("PUBLIC_BASE_URL") or "http://localhost:8000").rstrip("/")
        return send_transactional_email(user.email, "验证你的 OpenClaw 研究账户", f"请打开以下链接完成邮箱验证：\n{base}/v1/auth/verify-email?token={token}\n\n链接 24 小时内有效。")

    def request_password_reset(self, email: str) -> Dict[str, object]:
        user = self.db.find_user_by_email(email)
        # Deliberately return the same response for unknown emails to prevent enumeration.
        if not user:
            return {"ok": True}
        token = self.db.issue_token(user.id, "reset_password", 30 * 60)
        base = (os.environ.get("PUBLIC_BASE_URL") or "http://localhost:8000").rstrip("/")
        return send_transactional_email(user.email, "重置你的 OpenClaw 密码", f"请打开以下链接设置新密码：\n{base}/reset-password?token={token}\n\n链接 30 分钟内有效。")

    def reset_password(self, token: str, password: str) -> None:
        user_id = self.db.consume_token(token, "reset_password")
        if not user_id:
            raise ValueError("重置链接无效或已过期")
        self.db.update_password(user_id, password)
