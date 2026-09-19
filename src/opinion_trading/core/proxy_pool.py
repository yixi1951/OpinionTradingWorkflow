"""Simple crawl proxy rotation (round-robin + failover). Not a captcha/login farm."""

from __future__ import annotations

from typing import List, Optional

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

_ROTATOR: Optional["ProxyRotator"] = None


class ProxyRotator:
    """Round-robin over ``urls``, skipping recently failed entries.

    This is a config hook for HTTP crawl — it does **not** solve captchas,
    manage login cookies, or validate residential proxy quality.
    """

    def __init__(self, urls: Optional[List[str]] = None) -> None:
        self.urls = [str(u).strip() for u in (urls or []) if str(u).strip()]
        self._i = 0
        self._failed: set[str] = set()

    def next(self) -> Optional[str]:
        if not self.urls:
            return None
        n = len(self.urls)
        for _ in range(n):
            url = self.urls[self._i % n]
            self._i += 1
            if url not in self._failed:
                return url
        self._failed.clear()
        url = self.urls[self._i % n]
        self._i += 1
        logger.debug("proxy pool exhausted; retrying from the top")
        return url

    def mark_failure(self, url: Optional[str]) -> None:
        if url:
            self._failed.add(url)
            logger.debug("proxy marked failed: %s", url[:80])

    def mark_success(self, url: Optional[str]) -> None:
        if url and url in self._failed:
            self._failed.discard(url)

    def reset(self) -> None:
        self._i = 0
        self._failed.clear()

    def requests_proxies(self, url: Optional[str] = None) -> Optional[dict]:
        chosen = url if url is not None else self.next()
        if not chosen:
            return None
        return {"http": chosen, "https": chosen}

    @property
    def failed_count(self) -> int:
        return len(self._failed)


def set_proxy_rotator(rotator: Optional[ProxyRotator]) -> None:
    global _ROTATOR
    _ROTATOR = rotator


def get_proxy_rotator(*, reload: bool = False) -> ProxyRotator:
    global _ROTATOR
    if _ROTATOR is None or reload:
        from opinion_trading.core.gateway_health import load_proxy_pool

        _ROTATOR = ProxyRotator(load_proxy_pool())
    return _ROTATOR
