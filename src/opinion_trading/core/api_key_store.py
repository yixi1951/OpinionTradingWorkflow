"""Runtime API-key registry for LLM / OpenClaw scoring paths.

Operators upload keys via the admin HTTP API; values persist under
``data/memory/api_keys.json`` (override with ``API_KEYS_STORE_PATH``) and are
applied as an ``os.environ`` overlay so ``MultiModelGateway`` / DeepSeek /
optional OpenClaw token pick them up without rewriting ``.env``.

Precedence: uploaded (non-expired) store values override process env.
OpenClaw gateway WS token (``WS_GATEWAY_TOKEN`` / ``~/.openclaw``) is not
mutated here — only ``DEEPSEEK_API_KEY`` / ``QWEN_*`` / ``OPENCLAW_TOKEN`` /
optional model overrides.

Never log or return full key material; use :func:`mask_secret`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

# provider id -> env var(s) written by overlay
PROVIDER_ENV: Dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "QWEN_API_KEY",
    "openclaw": "OPENCLAW_TOKEN",
}

PROVIDER_MODEL_ENV: Dict[str, str] = {
    "deepseek": "DEEPSEEK_MODEL",
    "qwen": "QWEN_MODEL",
    "openclaw": "OPENCLAW_MODEL",
}

SUPPORTED_PROVIDERS = frozenset(PROVIDER_ENV.keys())

_lock = threading.RLock()
_base_env_snapshot: Dict[str, Optional[str]] = {}
_overlay_applied_generation: int = -1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def mask_secret(value: str) -> str:
    """Return a safe display form like ``sk-…abcd`` (never the full key)."""
    s = str(value or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "…" + s[-2:]
    if s.lower().startswith("sk-") and len(s) > 10:
        return f"sk-…{s[-4:]}"
    return f"{s[:2]}…{s[-4:]}"


def default_store_path() -> Path:
    raw = (os.environ.get("API_KEYS_STORE_PATH") or "").strip()
    if raw:
        return Path(raw)
    # Prefer project data/memory relative to cwd (same convention as other memory files)
    return Path("data/memory/api_keys.json")


@dataclass
class StoredKey:
    provider: str
    value: str
    model: Optional[str] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def expired(self, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or _utc_now()) >= self.expires_at

    def to_public(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "configured": bool(self.value) and not self.expired(),
            "masked_key": mask_secret(self.value) if self.value and not self.expired() else None,
            "model": self.model,
            "updated_at": _iso(self.updated_at),
            "expires_at": _iso(self.expires_at),
            "expired": self.expired(),
            "env_var": PROVIDER_ENV.get(self.provider),
        }

    def to_record(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "model": self.model,
            "updated_at": _iso(self.updated_at),
            "expires_at": _iso(self.expires_at),
        }

    @classmethod
    def from_record(cls, provider: str, record: Mapping[str, Any]) -> "StoredKey":
        return cls(
            provider=provider,
            value=str(record.get("value") or "").strip(),
            model=(str(record["model"]).strip() if record.get("model") else None),
            updated_at=_parse_iso(record.get("updated_at")),
            expires_at=_parse_iso(record.get("expires_at")),
        )


class ApiKeyStore:
    """Thread-safe local key store with optional TTL."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_store_path()
        self._generation = 0
        self._keys: Dict[str, StoredKey] = {}
        self._load()

    @property
    def generation(self) -> int:
        with _lock:
            return self._generation

    def _load(self) -> None:
        with _lock:
            if not self.path.is_file():
                self._keys = {}
                self._generation = 0
                return
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to read API key store %s: %s", self.path, type(exc).__name__)
                self._keys = {}
                self._generation = 0
                return
            keys_raw = data.get("keys") if isinstance(data, dict) else None
            loaded: Dict[str, StoredKey] = {}
            if isinstance(keys_raw, dict):
                for name, rec in keys_raw.items():
                    provider = str(name).strip().lower()
                    if provider not in SUPPORTED_PROVIDERS or not isinstance(rec, dict):
                        continue
                    sk = StoredKey.from_record(provider, rec)
                    if sk.value:
                        loaded[provider] = sk
            self._keys = loaded
            self._generation = int(data.get("generation") or 0) if isinstance(data, dict) else 0

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._generation += 1
        payload = {
            "generation": self._generation,
            "updated_at": _iso(_utc_now()),
            "keys": {name: sk.to_record() for name, sk in sorted(self._keys.items())},
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def reload(self) -> None:
        self._load()

    def list_status(self) -> List[Dict[str, Any]]:
        with _lock:
            self._purge_expired_unlocked()
            out = []
            for provider in sorted(SUPPORTED_PROVIDERS):
                sk = self._keys.get(provider)
                if sk is None:
                    out.append(
                        {
                            "provider": provider,
                            "configured": False,
                            "masked_key": None,
                            "model": None,
                            "updated_at": None,
                            "expires_at": None,
                            "expired": False,
                            "env_var": PROVIDER_ENV[provider],
                            "env_fallback": bool(
                                (os.environ.get(PROVIDER_ENV[provider]) or "").strip()
                            ),
                        }
                    )
                else:
                    pub = sk.to_public()
                    pub["env_fallback"] = bool(
                        (os.environ.get(PROVIDER_ENV[provider]) or "").strip()
                    )
                    out.append(pub)
            return out

    def get_status(self, provider: str) -> Dict[str, Any]:
        provider = provider.strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise KeyError(f"unsupported provider: {provider}")
        with _lock:
            self._purge_expired_unlocked()
            for item in self.list_status():
                if item["provider"] == provider:
                    return item
        raise KeyError(provider)

    def get_value(self, provider: str) -> Optional[str]:
        provider = provider.strip().lower()
        with _lock:
            self._purge_expired_unlocked()
            sk = self._keys.get(provider)
            if sk is None or sk.expired() or not sk.value:
                return None
            return sk.value

    def set_key(
        self,
        provider: str,
        api_key: str,
        *,
        model: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        provider = provider.strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise KeyError(f"unsupported provider: {provider}")
        key = str(api_key or "").strip()
        if not key:
            raise ValueError("api_key must be non-empty")
        expires_at = None
        if ttl_seconds is not None:
            ttl = int(ttl_seconds)
            if ttl <= 0:
                raise ValueError("ttl_seconds must be positive when set")
            expires_at = datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc)
        with _lock:
            prev = self._keys.get(provider)
            model_val = (
                str(model).strip()
                if model is not None and str(model).strip()
                else (prev.model if prev else None)
            )
            self._keys[provider] = StoredKey(
                provider=provider,
                value=key,
                model=model_val,
                updated_at=_utc_now(),
                expires_at=expires_at,
            )
            self._persist()
            apply_runtime_key_overlay(self)
            logger.info(
                "API key set for provider=%s masked=%s ttl=%s",
                provider,
                mask_secret(key),
                ttl_seconds,
            )
            return self.get_status(provider)

    def rotate_key(
        self,
        provider: str,
        api_key: str,
        *,
        model: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Alias of set_key (explicit rotate semantics for the HTTP API)."""
        return self.set_key(provider, api_key, model=model, ttl_seconds=ttl_seconds)

    def clear_key(self, provider: str) -> Dict[str, Any]:
        provider = provider.strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise KeyError(f"unsupported provider: {provider}")
        with _lock:
            removed = self._keys.pop(provider, None)
            if removed is not None:
                self._persist()
            _restore_env_for_provider(provider)
            apply_runtime_key_overlay(self)
            logger.info("API key cleared for provider=%s", provider)
            return self.get_status(provider)

    def active_overlay(self) -> Dict[str, str]:
        """Return env var -> value for non-expired stored keys (and models)."""
        with _lock:
            self._purge_expired_unlocked()
            out: Dict[str, str] = {}
            for provider, sk in self._keys.items():
                if sk.expired() or not sk.value:
                    continue
                env_name = PROVIDER_ENV[provider]
                out[env_name] = sk.value
                if sk.model:
                    model_env = PROVIDER_MODEL_ENV.get(provider)
                    if model_env:
                        out[model_env] = sk.model
            return out

    def _purge_expired_unlocked(self) -> None:
        now = _utc_now()
        expired = [name for name, sk in self._keys.items() if sk.expired(now)]
        if not expired:
            return
        for name in expired:
            self._keys.pop(name, None)
            _restore_env_for_provider(name)
        self._persist()
        logger.info("Purged expired API keys: %s", ",".join(expired))


_store_singleton: Optional[ApiKeyStore] = None


def get_api_key_store(path: Path | None = None) -> ApiKeyStore:
    global _store_singleton
    with _lock:
        if path is not None:
            return ApiKeyStore(path)
        if _store_singleton is None:
            _store_singleton = ApiKeyStore()
        else:
            # Pick up cross-process writes (api service vs inference)
            _store_singleton.reload()
        return _store_singleton


def reset_api_key_store_singleton() -> None:
    """Test helper: drop cached singleton."""
    global _store_singleton, _overlay_applied_generation, _base_env_snapshot
    with _lock:
        _store_singleton = None
        _overlay_applied_generation = -1
        _base_env_snapshot = {}


def _ensure_base_snapshot(env_names: List[str]) -> None:
    global _base_env_snapshot
    for name in env_names:
        if name not in _base_env_snapshot:
            _base_env_snapshot[name] = os.environ.get(name)


def _restore_env_for_provider(provider: str) -> None:
    env_name = PROVIDER_ENV.get(provider)
    model_env = PROVIDER_MODEL_ENV.get(provider)
    for name in (env_name, model_env):
        if not name:
            continue
        base = _base_env_snapshot.get(name)
        if base is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = base


def apply_runtime_key_overlay(store: ApiKeyStore | None = None) -> Dict[str, str]:
    """Apply non-expired uploaded keys onto ``os.environ``; return applied map.

    Safe to call repeatedly. Does not rewrite ``.env`` on disk.
    """
    global _overlay_applied_generation
    store = store or get_api_key_store()
    overlay = store.active_overlay()
    with _lock:
        tracked = list(PROVIDER_ENV.values()) + list(PROVIDER_MODEL_ENV.values())
        _ensure_base_snapshot(tracked)
        # Restore providers not in overlay back to base, then apply overlay
        for provider, env_name in PROVIDER_ENV.items():
            model_env = PROVIDER_MODEL_ENV[provider]
            if env_name not in overlay:
                _restore_env_for_provider(provider)
        for env_name, value in overlay.items():
            os.environ[env_name] = value
        _overlay_applied_generation = store.generation
    if overlay:
        masked = {k: mask_secret(v) for k, v in overlay.items() if k.endswith("_KEY") or k.endswith("_TOKEN")}
        if masked:
            logger.debug("Applied runtime key overlay: %s", masked)
    return overlay


def runtime_key_generation() -> int:
    store = get_api_key_store()
    return store.generation


def effective_secret(env_name: str, default: str = "") -> str:
    """Read secret preferring runtime store overlay semantics (after apply)."""
    apply_runtime_key_overlay()
    return (os.environ.get(env_name) or default).strip()
