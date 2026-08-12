"""Shared HTTP/WS retry with exponential backoff + idempotency helpers."""

from __future__ import annotations

import hashlib
import random
import time
import uuid
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


def make_idempotency_key(*parts: str, prefix: str = "ot") -> str:
    """Stable key from parts, or random UUID when parts empty."""
    blob = "|".join(str(p) for p in parts if p is not None)
    if not blob.strip():
        return f"{prefix}-{uuid.uuid4()}"
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.4,
    max_delay: float = 8.0,
    jitter: float = 0.2,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    should_retry: Optional[Callable[[BaseException], bool]] = None,
) -> T:
    """Call ``fn`` with exponential backoff. Raises last exception if all fail."""
    attempts = max(1, int(max_attempts))
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            if should_retry is not None and not should_retry(exc):
                raise
            if i >= attempts - 1:
                break
            delay = min(max_delay, base_delay * (2**i))
            delay *= 1.0 + random.uniform(-jitter, jitter)
            time.sleep(max(0.0, delay))
    assert last_exc is not None
    raise last_exc
