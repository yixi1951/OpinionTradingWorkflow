"""Auth DB, email verification, password reset, and research-platform RBAC."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opinion_trading.core.auth_db import AuthDatabase, reset_auth_database
from opinion_trading.core.auth_service import AuthService


@pytest.fixture()
def auth_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthDatabase:
    db_url = f"sqlite:///{tmp_path / 'auth.db'}"
    monkeypatch.setenv("AUTH_DATABASE_URL", db_url)
    monkeypatch.setenv("APP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("EMAIL_SINK_PATH", str(tmp_path / "outbox.jsonl"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    reset_auth_database()
    db = AuthDatabase(db_url)
    yield db
    reset_auth_database()


def test_register_verify_reset_and_roles(auth_db: AuthDatabase, tmp_path: Path):
    svc = AuthService(auth_db)
    user = svc.register("alice", "password123", "alice@example.com")
    assert user.email_verified is False
    assert "viewer" in user.roles

    outbox = Path(tmp_path / "outbox.jsonl")
    lines = outbox.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    mail = json.loads(lines[0])
    assert "verify-email?token=" in mail["text"]
    token = mail["text"].split("token=")[1].split()[0]

    uid = auth_db.consume_token(token, "verify_email")
    assert uid == user.id
    auth_db.set_email_verified(uid)
    refreshed = auth_db.user_by_id(user.id)
    assert refreshed is not None and refreshed.email_verified is True

    auth_db.set_roles(user.id, ["viewer", "analyst"])
    assert auth_db.has_role(user.id, "analyst")

    svc.request_password_reset("alice@example.com")
    reset_mail = json.loads(outbox.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert "reset-password?token=" in reset_mail["text"]
    reset_token = reset_mail["text"].split("token=")[1].split()[0]
    svc.reset_password(reset_token, "newpassword99")
    assert auth_db.authenticate("alice", "newpassword99") is not None
    assert auth_db.authenticate("alice", "password123") is None


def test_password_reset_unknown_email_is_opaque(auth_db: AuthDatabase):
    svc = AuthService(auth_db)
    assert svc.request_password_reset("nobody@example.com") == {"ok": True}


def test_watchlist_persistence(auth_db: AuthDatabase):
    user = auth_db.create_user("bob", "password123", "bob@example.com")
    assert auth_db.add_watch(user.id, "600519.SH") == ["600519.SH"]
    assert auth_db.add_watch(user.id, "000001.SZ") == ["000001.SZ", "600519.SH"]
    assert auth_db.remove_watch(user.id, "600519.SH") == ["000001.SZ"]


def test_postgres_schema_helpers():
    path = Path("deploy/sql/auth_schema.postgres.sql")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS users" in text
    assert "BIGSERIAL" in AuthDatabase._postgres_schema()


def test_smtp_sink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from opinion_trading.core.email_service import send_transactional_email

    sink = tmp_path / "outbox.jsonl"
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("EMAIL_SINK_PATH", str(sink))
    result = send_transactional_email("user@example.com", "probe", "hello")
    assert result["mode"] == "sink"
    line = json.loads(sink.read_text(encoding="utf-8").splitlines()[-1])
    assert line["to"] == "user@example.com"
