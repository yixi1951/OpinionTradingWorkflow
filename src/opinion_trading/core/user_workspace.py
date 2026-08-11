"""Per-user workspace: watchlist, alert rules, inbox (JSON files)."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return salt, digest


@dataclass
class AlertRule:
    symbol: str
    score_high: float = 0.35
    score_low: float = -0.35
    heat_spike_ratio: float = 2.0  # vs prior day post_count
    enabled: bool = True


@dataclass
class UserProfile:
    username: str
    password_salt: str
    password_hash: str
    watchlist: List[str] = field(default_factory=list)
    alert_rules: List[Dict[str, Any]] = field(default_factory=list)
    email: str = ""
    created_at: str = ""


class UserWorkspace:
    """Simple file-backed multi-user store under data/users/."""

    def __init__(self, root: str = "data/users") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.inbox_dir = self.root / "inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_demo_user()

    def _user_path(self, username: str) -> Path:
        safe = "".join(c for c in username if c.isalnum() or c in "-_")[:64]
        return self.root / f"{safe}.json"

    def _ensure_demo_user(self) -> None:
        if self._user_path("demo").exists():
            return
        salt, digest = _hash_password("demo123")
        profile = UserProfile(
            username="demo",
            password_salt=salt,
            password_hash=digest,
            watchlist=["600519.SH", "000001.SZ", "601318.SH"],
            alert_rules=[
                asdict(
                    AlertRule(symbol="600519.SH", score_high=0.3, score_low=-0.3)
                )
            ],
            created_at=_now(),
        )
        self.save_profile(profile)

    def load_profile(self, username: str) -> Optional[UserProfile]:
        path = self._user_path(username)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return UserProfile(
            username=str(data.get("username", username)),
            password_salt=str(data.get("password_salt", "")),
            password_hash=str(data.get("password_hash", "")),
            watchlist=list(data.get("watchlist") or []),
            alert_rules=list(data.get("alert_rules") or []),
            email=str(data.get("email", "")),
            created_at=str(data.get("created_at", "")),
        )

    def save_profile(self, profile: UserProfile) -> None:
        path = self._user_path(profile.username)
        path.write_text(
            json.dumps(asdict(profile), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def register(self, username: str, password: str, email: str = "") -> UserProfile:
        if self.load_profile(username):
            raise ValueError("user exists")
        salt, digest = _hash_password(password)
        profile = UserProfile(
            username=username.strip(),
            password_salt=salt,
            password_hash=digest,
            watchlist=[],
            alert_rules=[],
            email=email,
            created_at=_now(),
        )
        self.save_profile(profile)
        return profile

    def authenticate(self, username: str, password: str) -> Optional[UserProfile]:
        profile = self.load_profile(username)
        if not profile:
            return None
        _, digest = _hash_password(password, profile.password_salt)
        if digest != profile.password_hash:
            return None
        return profile

    def add_watch(self, username: str, symbol: str) -> List[str]:
        profile = self.load_profile(username)
        if not profile:
            raise ValueError("user not found")
        sym = symbol.strip().upper()
        if sym and sym not in profile.watchlist:
            profile.watchlist.append(sym)
            self.save_profile(profile)
        return profile.watchlist

    def remove_watch(self, username: str, symbol: str) -> List[str]:
        profile = self.load_profile(username)
        if not profile:
            raise ValueError("user not found")
        sym = symbol.strip().upper()
        profile.watchlist = [s for s in profile.watchlist if s != sym]
        profile.alert_rules = [
            r for r in profile.alert_rules if str(r.get("symbol", "")).upper() != sym
        ]
        self.save_profile(profile)
        return profile.watchlist

    def upsert_alert_rule(self, username: str, rule: AlertRule) -> None:
        profile = self.load_profile(username)
        if not profile:
            raise ValueError("user not found")
        rules = [
            r
            for r in profile.alert_rules
            if str(r.get("symbol", "")).upper() != rule.symbol.upper()
        ]
        rules.append(asdict(rule))
        profile.alert_rules = rules
        if rule.symbol.upper() not in [s.upper() for s in profile.watchlist]:
            profile.watchlist.append(rule.symbol.upper())
        self.save_profile(profile)

    def push_inbox(self, username: str, message: Dict[str, Any]) -> None:
        path = self.inbox_dir / f"{username}.jsonl"
        row = dict(message)
        row.setdefault("ts", _now())
        row.setdefault("read", False)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def list_inbox(self, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        path = self.inbox_dir / f"{username}.jsonl"
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return list(reversed(rows[-limit:]))

    def mark_inbox_read(self, username: str) -> None:
        path = self.inbox_dir / f"{username}.jsonl"
        if not path.exists():
            return
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            obj["read"] = True
            rows.append(obj)
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )
