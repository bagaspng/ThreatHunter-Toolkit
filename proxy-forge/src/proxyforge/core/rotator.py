"""
ProxyRotator module.
"""
import itertools
import logging
from typing import Any
import requests

from .pool import ProxyPool

logger = logging.getLogger("proxyforge.rotator")

class ProxyRotator:
    def __init__(self, pool: ProxyPool, max_retries: int = 3) -> None:
        self.pool = pool
        self.max_retries = max_retries
        self._pool = pool.proxies.copy()
        if self._pool:
            self._cycle = itertools.cycle(self._pool)
        else:
            self._cycle = itertools.cycle([])

    @property
    def pool_size(self) -> int:
        return len(self._pool)

    def _next(self) -> dict[str, Any] | None:
        if not self._pool:
            return None
        return next(self._cycle)

    def fetch(self, url: str, method: str = "GET", timeout: int = 10, **kwargs: Any) -> requests.Response | None:
        if not self._pool:
            logger.warning("Fetch failed: No proxies available in the pool.")
            return None

        # Attempt up to max_retries or pool_size, whichever is smaller
        retries = min(self.max_retries, max(1, self.pool_size))

        for attempt in range(retries):
            proxy_entry = self._next()
            if not proxy_entry:
                break
                
            proxy_uri = proxy_entry.get("proxy")
            if not proxy_uri:
                continue

            proxies = {
                "http": proxy_uri,
                "https": proxy_uri,
            }

            try:
                logger.debug("Fetching %s via %s (attempt %d/%d)", url, proxy_uri, attempt + 1, retries)
                response = requests.request(
                    method=method,
                    url=url,
                    proxies=proxies,
                    timeout=timeout,
                    **kwargs
                )
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.debug("Request failed via %s: %s", proxy_uri, e)
                self.evict(proxy_uri)

        logger.warning("Fetch failed after %d retries for url %s", retries, url)
        return None

    def evict(self, proxy_uri: str) -> None:
        original_len = len(self._pool)
        self._pool = [p for p in self._pool if p.get("proxy") != proxy_uri]
        
        if len(self._pool) < original_len:
            logger.info("Evicted dead proxy: %s | Remaining in pool: %d", proxy_uri, len(self._pool))
            if self._pool:
                self._cycle = itertools.cycle(self._pool)
            else:
                self._cycle = itertools.cycle([])
