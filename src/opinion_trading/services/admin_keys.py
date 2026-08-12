"""Admin HTTP API for uploading LLM / OpenClaw-path API keys.

OpenAPI-style surface (Bearer ``ADMIN_API_TOKEN`` required on all routes):

- ``GET    /v1/admin/keys``                 — list providers + masked status
- ``GET    /v1/admin/keys/{provider}``      — one provider (masked)
- ``PUT    /v1/admin/keys/{provider}``      — set / overwrite key
- ``POST   /v1/admin/keys/{provider}/rotate`` — rotate (same as set)
- ``DELETE /v1/admin/keys/{provider}``      — clear uploaded key

Providers: ``deepseek`` (primary for MultiModelGateway), ``qwen``,
``openclaw`` (optional ``OPENCLAW_TOKEN`` for REST bearer to the proxy).

Persistence: ``data/memory/api_keys.json`` via :mod:`api_key_store`.
Runtime: overlay applied to ``os.environ`` immediately; inference
``MultiModelGateway`` reloads providers on generation change (no process
restart for in-process / file-watching gateways). OpenClaw WS gateway
config under ``~/.openclaw`` is intentionally not rewritten.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from opinion_trading.core.api_key_store import (
    SUPPORTED_PROVIDERS,
    apply_runtime_key_overlay,
    get_api_key_store,
    mask_secret,
)


def _admin_token() -> str:
    return (os.environ.get("ADMIN_API_TOKEN") or "").strip()


def require_admin(
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = _admin_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_API_TOKEN is not configured on the server",
        )
    presented = ""
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    elif x_admin_token:
        presented = x_admin_token.strip()
    if not presented or presented != expected:
        raise HTTPException(status_code=401, detail="invalid or missing admin token")


class KeyUpsertRequest(BaseModel):
    """Body for set / rotate.

    - ``api_key``: required non-empty provider secret (never echoed back full)
    - ``model``: optional model override (e.g. deepseek-chat)
    - ``ttl_seconds``: optional expiry; key auto-purged after TTL
    """

    api_key: str = Field(..., min_length=1, description="Provider API key / token")
    model: Optional[str] = Field(default=None, description="Optional model id override")
    ttl_seconds: Optional[int] = Field(
        default=None, gt=0, description="Optional TTL in seconds"
    )


def create_admin_keys_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/admin/keys",
        tags=["admin-keys"],
        dependencies=[Depends(require_admin)],
    )

    @router.get("")
    def list_keys() -> Dict[str, Any]:
        store = get_api_key_store()
        apply_runtime_key_overlay(store)
        return {
            "providers": store.list_status(),
            "generation": store.generation,
            "note": "Values are masked; uploaded keys overlay process env for scoring.",
        }

    @router.get("/{provider}")
    def get_key(provider: str) -> Dict[str, Any]:
        _validate_provider(provider)
        store = get_api_key_store()
        apply_runtime_key_overlay(store)
        try:
            return store.get_status(provider)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.put("/{provider}")
    def put_key(provider: str, body: KeyUpsertRequest) -> Dict[str, Any]:
        return _upsert(provider, body)

    @router.post("/{provider}/rotate")
    def rotate_key(provider: str, body: KeyUpsertRequest) -> Dict[str, Any]:
        return _upsert(provider, body, rotate=True)

    @router.delete("/{provider}")
    def delete_key(provider: str) -> Dict[str, Any]:
        _validate_provider(provider)
        store = get_api_key_store()
        try:
            status = store.clear_key(provider)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ok": True, "action": "cleared", **status}

    return router


def _validate_provider(provider: str) -> str:
    name = (provider or "").strip().lower()
    if name not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported provider; choose one of: {sorted(SUPPORTED_PROVIDERS)}",
        )
    return name


def _upsert(
    provider: str, body: KeyUpsertRequest, *, rotate: bool = False
) -> Dict[str, Any]:
    name = _validate_provider(provider)
    key = (body.api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="api_key must be non-empty")
    store = get_api_key_store()
    try:
        if rotate:
            status = store.rotate_key(
                name, key, model=body.model, ttl_seconds=body.ttl_seconds
            )
            action = "rotated"
        else:
            status = store.set_key(
                name, key, model=body.model, ttl_seconds=body.ttl_seconds
            )
            action = "set"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "action": action,
        "masked_key": status.get("masked_key") or mask_secret(key),
        **status,
    }


def mount_admin_keys(app: Any) -> None:
    """Attach admin key routes to a FastAPI app (api + inference)."""
    app.include_router(create_admin_keys_router())
