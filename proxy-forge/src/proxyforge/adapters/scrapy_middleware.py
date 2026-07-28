"""Adapter: Scrapy Middleware"""

from typing import Any
from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator

class ProxyForgeMiddleware:
    def __init__(self, pool_path: str):
        pool = ProxyPool.load(pool_path)
        self.rotator = ProxyRotator(pool)

    @classmethod
    def from_crawler(cls, crawler: Any) -> "ProxyForgeMiddleware":
        pool_path = crawler.settings.get("PROXYFORGE_POOL_PATH", "working_proxies.json")
        return cls(pool_path)

    def process_request(self, request: Any, spider: Any) -> None:
        p = self.rotator._next()
        if p:
            proxy_url = p["proxy"]
            request.meta["proxy"] = proxy_url
            spider.logger.debug("Using proxy: %s", proxy_url)
            
    def process_exception(self, request: Any, exception: Exception, spider: Any) -> None:
        if "proxy" in request.meta:
            self.rotator.evict(request.meta["proxy"])
            spider.logger.info("Evicted proxy: %s", request.meta["proxy"])
