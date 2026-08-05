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
        self._current_proxy: dict[str, Any] | None = None

    @property
    def pool_size(self) -> int:
        return len(self._pool)

    def _get_current_proxy(self) -> dict[str, Any] | None:
        if not self._pool:
            self._current_proxy = None
            return None
            
        if self._current_proxy is None or self._current_proxy not in self._pool:
            self._current_proxy = self._pool[0]
            
        return self._current_proxy

    @property
    def current_proxy_uri(self) -> str | None:
        p = self._get_current_proxy()
        return p.get("proxy") if p else None

    def _next(self) -> dict[str, Any] | None:
        """Alias for compatibility, returns current sticky proxy."""
        return self._get_current_proxy()

    def fetch(self, url: str, method: str = "GET", timeout: int = 10, **kwargs: Any) -> requests.Response | None:
        if not self._pool:
            logger.warning("Fetch failed: No proxies available in the pool.")
            return None

        retries = min(self.max_retries, max(1, self.pool_size))

        for attempt in range(retries):
            proxy_entry = self._get_current_proxy()
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
                logger.debug("Fetching %s via sticky proxy %s (attempt %d/%d)", url, proxy_uri, attempt + 1, retries)
                response = requests.request(
                    method=method,
                    url=url,
                    proxies=proxies,
                    timeout=timeout,
                    **kwargs
                )
                
                # Burn condition: status code != 200
                if response.status_code != 200:
                    logger.warning(
                        "Burn condition triggered for %s: HTTP status %d != 200. Evicting...", 
                        proxy_uri, response.status_code
                    )
                    self.evict(proxy_uri)
                    continue

                return response

            except requests.RequestException as e:
                logger.warning("Burn condition triggered for %s: %s. Evicting...", proxy_uri, e)
                self.evict(proxy_uri)

        logger.warning("Fetch failed after %d retries for url %s", retries, url)
        return None

    def evict(self, proxy_uri: str) -> None:
        original_len = len(self._pool)
        self._pool = [p for p in self._pool if p.get("proxy") != proxy_uri]
        
        if self._current_proxy and self._current_proxy.get("proxy") == proxy_uri:
            self._current_proxy = None

        if len(self._pool) < original_len:
            logger.info("Evicted dead/burned proxy: %s | Remaining in pool: %d", proxy_uri, len(self._pool))
