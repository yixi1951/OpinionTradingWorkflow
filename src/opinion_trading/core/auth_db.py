"""Durable identity, session, role, watchlist and token storage.

SQLite is the zero-configuration development backend. Production should set
``AUTH_DATABASE_URL`` to a PostgreSQL DSN (requires ``psycopg``). Schema is
migrated on connect so a fresh deployment never needs hand-made user files.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


SCHEMA_VERSION = 2
ROLE_NAMES = ("viewer", "analyst", "admin")


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 240_000
    ).hex()
    return salt, digest


def _hash_token(token: str) -> str:
    pepper = (os.environ.get("APP_SESSION_SECRET") or "development-only").encode()
    return hmac.new(pepper, token.encode(), hashlib.sha256).hexdigest()


def _now() -> int:
    return int(time.time())


def _row_get(row: Any, key: str, index: int = 0) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row[key]
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[index]


def _row_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    email: str
    email_verified: bool
    active: bool
    roles: tuple[str, ...]

    def public(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "email_verified": self.email_verified,
            "active": self.active,
            "roles": list(self.roles),
        }


class _ConnAdapter:
    """Normalize SQLite / psycopg execute APIs and ``?`` placeholders."""

    def __init__(self, conn: Any, backend: str) -> None:
        self._conn = conn
        self.backend = backend

    def execute(self, sql: str, params: tuple | list = ()) -> Any:
        if self.backend == "postgres":
            sql = sql.replace("?", "%s")
        return self._conn.execute(sql, params)

    def executescript(self, script: str) -> None:
        if self.backend == "sqlite":
            self._conn.executescript(script)
            return
        for stmt in script.split(";"):
            text = stmt.strip()
            if text:
                self._conn.execute(text)


class AuthDatabase:
    def __init__(self, url: Optional[str] = None) -> None:
        self.url = (
            url or os.environ.get("AUTH_DATABASE_URL") or "sqlite:///data/auth.db"
        ).strip()
        self.path: Optional[Path] = None
        if self.url.startswith("sqlite:///"):
            self.backend = "sqlite"
            self.path = Path(self.url.removeprefix("sqlite:///"))
            if not self.path.is_absolute():
                self.path = Path.cwd() / self.path
            self.path.parent.mkdir(parents=True, exist_ok=True)
        elif self.url.startswith("postgres"):
            self.backend = "postgres"
            try:
                import psycopg  # noqa: F401
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL auth storage requires psycopg — "
                    "pip install 'psycopg[binary]'"
                ) from exc
        else:
            raise ValueError(
                "AUTH_DATABASE_URL must be sqlite:///... or postgresql://..."
            )
        self.migrate()
        if self.backend == "sqlite":
            self.migrate_legacy_users()

    @contextmanager
    def connection(self) -> Iterator[_ConnAdapter]:
        if self.backend == "sqlite":
            assert self.path is not None
            conn = sqlite3.connect(str(self.path), timeout=15, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            try:
                yield _ConnAdapter(conn, "sqlite")
            finally:
                conn.close()
            return

        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(self.url, row_factory=dict_row, autocommit=True)
        try:
            yield _ConnAdapter(conn, "postgres")
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.connection() as c:
            if self.backend == "sqlite":
                c.executescript(self._sqlite_schema())
            else:
                c.executescript(self._postgres_schema())
            for role in ROLE_NAMES:
                if self.backend == "sqlite":
                    c.execute("INSERT OR IGNORE INTO roles(name) VALUES (?)", (role,))
                else:
                    c.execute(
                        "INSERT INTO roles(name) VALUES (?) ON CONFLICT DO NOTHING",
                        (role,),
                    )
            if self.backend == "sqlite":
                c.execute(
                    "INSERT OR REPLACE INTO schema_meta(key,value) VALUES(?,?)",
                    ("version", str(SCHEMA_VERSION)),
                )
            else:
                c.execute(
                    "INSERT INTO schema_meta(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                    ("version", str(SCHEMA_VERSION)),
                )

    @staticmethod
    def _sqlite_schema() -> str:
        return """
                CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    email TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users(email) WHERE email <> '';
                CREATE TABLE IF NOT EXISTS roles (name TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role TEXT NOT NULL REFERENCES roles(name),
                    PRIMARY KEY(user_id, role)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_token TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS email_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    purpose TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    used_at INTEGER,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS watchlists (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY(user_id, symbol)
                );
                CREATE TABLE IF NOT EXISTS alert_rules (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    score_high REAL NOT NULL DEFAULT 0.35,
                    score_low REAL NOT NULL DEFAULT -0.35,
                    heat_spike_ratio REAL NOT NULL DEFAULT 2.0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(user_id, symbol)
                );
                CREATE TABLE IF NOT EXISTS broker_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    account_label TEXT NOT NULL,
                    encrypted_config TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    verified_at INTEGER,
                    created_at INTEGER NOT NULL,
                    UNIQUE(user_id, provider, account_label)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    request_id TEXT NOT NULL UNIQUE,
                    broker_account_id INTEGER REFERENCES broker_accounts(id),
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    order_type TEXT NOT NULL,
                    limit_price REAL,
                    status TEXT NOT NULL,
                    broker_order_id TEXT,
                    raw_response TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                """

    @staticmethod
    def _postgres_schema() -> str:
        return """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL DEFAULT '',
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at BIGINT NOT NULL,
                    updated_at BIGINT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique
                    ON users (email) WHERE email <> '';
                CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_unique
                    ON users (lower(username));
                CREATE TABLE IF NOT EXISTS roles (name TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role TEXT NOT NULL REFERENCES roles(name),
                    PRIMARY KEY(user_id, role)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_token TEXT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    created_at BIGINT NOT NULL,
                    last_seen_at BIGINT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS email_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    purpose TEXT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    used_at BIGINT,
                    created_at BIGINT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS watchlists (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    created_at BIGINT NOT NULL,
                    PRIMARY KEY(user_id, symbol)
                );
                CREATE TABLE IF NOT EXISTS alert_rules (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    score_high DOUBLE PRECISION NOT NULL DEFAULT 0.35,
                    score_low DOUBLE PRECISION NOT NULL DEFAULT -0.35,
                    heat_spike_ratio DOUBLE PRECISION NOT NULL DEFAULT 2.0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(user_id, symbol)
                );
                CREATE TABLE IF NOT EXISTS broker_accounts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    account_label TEXT NOT NULL,
                    encrypted_config TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    verified_at BIGINT,
                    created_at BIGINT NOT NULL,
                    UNIQUE(user_id, provider, account_label)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    request_id TEXT NOT NULL UNIQUE,
                    broker_account_id BIGINT REFERENCES broker_accounts(id),
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    order_type TEXT NOT NULL,
                    limit_price DOUBLE PRECISION,
                    status TEXT NOT NULL,
                    broker_order_id TEXT,
                    raw_response TEXT,
                    created_at BIGINT NOT NULL,
                    updated_at BIGINT NOT NULL
                );
                """

    def migrate_legacy_users(self) -> None:
        """Import old JSON profiles once, never use them as the source of truth."""
        legacy = Path(os.environ.get("LEGACY_USERS_DIR", "data/users"))
        if not legacy.is_dir():
            return
        for path in legacy.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                username = str(data.get("username") or path.stem).strip()
                if not username or not data.get("password_hash"):
                    continue
                with self.connection() as c:
                    existing = c.execute(
                        "SELECT id FROM users WHERE lower(username)=lower(?)",
                        (username,),
                    ).fetchone()
                    if existing:
                        continue
                    now = _now()
                    row = c.execute(
                        "INSERT INTO users(username,email,password_salt,password_hash,"
                        "email_verified,created_at,updated_at) VALUES(?,?,?,?,?,?,?) "
                        "RETURNING id",
                        (
                            username,
                            str(data.get("email") or ""),
                            str(data["password_salt"]),
                            str(data["password_hash"]),
                            1 if username == "demo" else 0,
                            now,
                            now,
                        ),
                    ).fetchone()
                    user_id = int(_row_get(row, "id"))
                    if self.backend == "sqlite":
                        c.execute(
                            "INSERT OR IGNORE INTO user_roles(user_id,role) VALUES(?,?)",
                            (user_id, "viewer"),
                        )
                    else:
                        c.execute(
                            "INSERT INTO user_roles(user_id,role) VALUES(?,?) "
                            "ON CONFLICT DO NOTHING",
                            (user_id, "viewer"),
                        )
                    for symbol in data.get("watchlist") or []:
                        if self.backend == "sqlite":
                            c.execute(
                                "INSERT OR IGNORE INTO watchlists(user_id,symbol,created_at) "
                                "VALUES(?,?,?)",
                                (user_id, str(symbol).upper(), now),
                            )
                        else:
                            c.execute(
                                "INSERT INTO watchlists(user_id,symbol,created_at) "
                                "VALUES(?,?,?) ON CONFLICT DO NOTHING",
                                (user_id, str(symbol).upper(), now),
                            )
            except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error):
                continue

    def _user_from_row(self, row: Any, c: _ConnAdapter) -> AuthUser:
        roles = tuple(
            _row_get(r, "role", 0)
            for r in c.execute(
                "SELECT role FROM user_roles WHERE user_id=? ORDER BY role",
                (_row_get(row, "id"),),
            ).fetchall()
        )
        return AuthUser(
            int(_row_get(row, "id")),
            str(_row_get(row, "username")),
            str(_row_get(row, "email")),
            bool(_row_get(row, "email_verified")),
            bool(_row_get(row, "active")),
            roles,
        )

    def find_user(self, username: str) -> Optional[AuthUser]:
        with self.connection() as c:
            row = c.execute(
                "SELECT * FROM users WHERE lower(username)=lower(?)",
                (username.strip(),),
            ).fetchone()
            return self._user_from_row(row, c) if row else None

    def find_user_by_email(self, email: str) -> Optional[AuthUser]:
        with self.connection() as c:
            row = c.execute(
                "SELECT * FROM users WHERE lower(email)=lower(?) AND email<>''",
                (email.strip().lower(),),
            ).fetchone()
            return self._user_from_row(row, c) if row else None

    def authenticate(self, username: str, password: str) -> Optional[AuthUser]:
        with self.connection() as c:
            row = c.execute(
                "SELECT * FROM users WHERE lower(username)=lower(?) AND active=1",
                (username.strip(),),
            ).fetchone()
            if not row:
                return None
            _, digest = _hash_password(password, str(_row_get(row, "password_salt")))
            legacy = hashlib.sha256(
                f"{_row_get(row, 'password_salt')}:{password}".encode("utf-8")
            ).hexdigest()
            stored = str(_row_get(row, "password_hash"))
            if not hmac.compare_digest(digest, stored) and not hmac.compare_digest(
                legacy, stored
            ):
                return None
            if hmac.compare_digest(legacy, stored):
                salt, upgraded = _hash_password(
                    password, str(_row_get(row, "password_salt"))
                )
                c.execute(
                    "UPDATE users SET password_salt=?,password_hash=?,updated_at=? WHERE id=?",
                    (salt, upgraded, _now(), _row_get(row, "id")),
                )
                row = c.execute(
                    "SELECT * FROM users WHERE id=?", (_row_get(row, "id"),)
                ).fetchone()
                assert row is not None
            return self._user_from_row(row, c)

    def create_user(
        self,
        username: str,
        password: str,
        email: str = "",
        *,
        verified: bool = False,
        role: str = "viewer",
    ) -> AuthUser:
        username = username.strip()
        if not 3 <= len(username) <= 64:
            raise ValueError("用户名长度需要在 3 到 64 个字符之间")
        if len(password) < 8:
            raise ValueError("密码至少需要 8 个字符")
        if role not in ROLE_NAMES:
            raise ValueError("invalid role")
        salt, digest = _hash_password(password)
        now = _now()
        with self.connection() as c:
            try:
                row = c.execute(
                    "INSERT INTO users(username,email,password_salt,password_hash,"
                    "email_verified,created_at,updated_at) VALUES(?,?,?,?,?,?,?) "
                    "RETURNING id",
                    (
                        username,
                        email.strip().lower(),
                        salt,
                        digest,
                        int(verified),
                        now,
                        now,
                    ),
                ).fetchone()
            except Exception as exc:
                # sqlite3.IntegrityError / psycopg.errors.UniqueViolation
                name = type(exc).__name__
                if "Integrity" in name or "Unique" in name or "unique" in str(exc).lower():
                    raise ValueError("user exists") from exc
                raise
            user_id = int(_row_get(row, "id"))
            c.execute(
                "INSERT INTO user_roles(user_id,role) VALUES(?,?)", (user_id, role)
            )
            row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            assert row is not None
            return self._user_from_row(row, c)

    def set_email_verified(self, user_id: int) -> None:
        with self.connection() as c:
            c.execute(
                "UPDATE users SET email_verified=1,updated_at=? WHERE id=?",
                (_now(), user_id),
            )

    def user_by_id(self, user_id: int) -> Optional[AuthUser]:
        with self.connection() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return self._user_from_row(row, c) if row else None

    def update_password(self, user_id: int, password: str) -> None:
        if len(password) < 8:
            raise ValueError("密码至少需要 8 个字符")
        salt, digest = _hash_password(password)
        with self.connection() as c:
            c.execute(
                "UPDATE users SET password_salt=?,password_hash=?,updated_at=? WHERE id=?",
                (salt, digest, _now(), user_id),
            )
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

    def create_session(
        self, user_id: int, ttl_seconds: int = 604800
    ) -> tuple[str, str, int]:
        token, csrf, now = secrets.token_urlsafe(48), secrets.token_urlsafe(24), _now()
        with self.connection() as c:
            c.execute("DELETE FROM sessions WHERE expires_at<?", (now,))
            c.execute(
                "INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at,"
                "created_at,last_seen_at) VALUES(?,?,?,?,?,?)",
                (_hash_token(token), user_id, csrf, now + ttl_seconds, now, now),
            )
        return token, csrf, now + ttl_seconds

    def session_user(self, token: str) -> tuple[AuthUser, str]:
        with self.connection() as c:
            row = c.execute(
                "SELECT s.csrf_token AS csrf_token, u.* FROM sessions s "
                "JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.expires_at>? AND u.active=1",
                (_hash_token(token), _now()),
            ).fetchone()
            if not row:
                raise ValueError("invalid session")
            c.execute(
                "UPDATE sessions SET last_seen_at=? WHERE token_hash=?",
                (_now(), _hash_token(token)),
            )
            return self._user_from_row(row, c), str(_row_get(row, "csrf_token"))

    def delete_session(self, token: str) -> None:
        with self.connection() as c:
            c.execute(
                "DELETE FROM sessions WHERE token_hash=?", (_hash_token(token),)
            )

    def issue_token(self, user_id: int, purpose: str, ttl_seconds: int) -> str:
        token, now = secrets.token_urlsafe(36), _now()
        with self.connection() as c:
            c.execute(
                "DELETE FROM email_tokens WHERE user_id=? AND purpose=? AND used_at IS NULL",
                (user_id, purpose),
            )
            c.execute(
                "INSERT INTO email_tokens(token_hash,user_id,purpose,expires_at,created_at) "
                "VALUES(?,?,?,?,?)",
                (_hash_token(token), user_id, purpose, now + ttl_seconds, now),
            )
        return token

    def consume_token(self, token: str, purpose: str) -> Optional[int]:
        with self.connection() as c:
            row = c.execute(
                "SELECT user_id FROM email_tokens WHERE token_hash=? AND purpose=? "
                "AND used_at IS NULL AND expires_at>?",
                (_hash_token(token), purpose, _now()),
            ).fetchone()
            if not row:
                return None
            c.execute(
                "UPDATE email_tokens SET used_at=? WHERE token_hash=?",
                (_now(), _hash_token(token)),
            )
            return int(_row_get(row, "user_id"))

    def has_role(self, user_id: int, *roles: str) -> bool:
        allowed = set(roles)
        with self.connection() as c:
            rows = c.execute(
                "SELECT role FROM user_roles WHERE user_id=?", (user_id,)
            ).fetchall()
            current = {str(_row_get(r, "role", 0)) for r in rows}
        return bool(current & allowed) or "admin" in current

    def list_roles(self, user_id: int) -> List[str]:
        with self.connection() as c:
            return [
                str(_row_get(r, "role", 0))
                for r in c.execute(
                    "SELECT role FROM user_roles WHERE user_id=? ORDER BY role",
                    (user_id,),
                ).fetchall()
            ]

    def list_users(self) -> List[AuthUser]:
        with self.connection() as c:
            return [
                self._user_from_row(row, c)
                for row in c.execute("SELECT * FROM users ORDER BY id").fetchall()
            ]

    def set_roles(self, user_id: int, roles: List[str]) -> None:
        if not roles or any(r not in ROLE_NAMES for r in roles):
            raise ValueError("at least one valid role is required")
        with self.connection() as c:
            c.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
            for role in sorted(set(roles)):
                c.execute(
                    "INSERT INTO user_roles(user_id,role) VALUES(?,?)",
                    (user_id, role),
                )

    def watchlist(self, user_id: int) -> List[str]:
        with self.connection() as c:
            return [
                str(_row_get(r, "symbol", 0))
                for r in c.execute(
                    "SELECT symbol FROM watchlists WHERE user_id=? ORDER BY symbol",
                    (user_id,),
                ).fetchall()
            ]

    def add_watch(self, user_id: int, symbol: str) -> List[str]:
        with self.connection() as c:
            if self.backend == "sqlite":
                c.execute(
                    "INSERT OR IGNORE INTO watchlists(user_id,symbol,created_at) VALUES(?,?,?)",
                    (user_id, symbol.upper(), _now()),
                )
            else:
                c.execute(
                    "INSERT INTO watchlists(user_id,symbol,created_at) VALUES(?,?,?) "
                    "ON CONFLICT DO NOTHING",
                    (user_id, symbol.upper(), _now()),
                )
        return self.watchlist(user_id)

    def remove_watch(self, user_id: int, symbol: str) -> List[str]:
        with self.connection() as c:
            c.execute(
                "DELETE FROM watchlists WHERE user_id=? AND symbol=?",
                (user_id, symbol.upper()),
            )
        return self.watchlist(user_id)


_database: Optional[AuthDatabase] = None


def get_auth_database() -> AuthDatabase:
    global _database
    desired = os.environ.get("AUTH_DATABASE_URL") or "sqlite:///data/auth.db"
    if _database is None or _database.url != desired:
        _database = AuthDatabase(desired)
    return _database


def reset_auth_database() -> None:
    global _database
    _database = None
