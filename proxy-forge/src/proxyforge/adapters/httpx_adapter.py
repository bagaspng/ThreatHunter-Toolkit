"""Adapter: HTTPX Async Client"""

from typing import Any
from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator
import httpx

class ProxyForgeAsyncClient:
    def __init__(self, pool_path: str, max_retries: int = 3):
        self.pool = ProxyPool.load(pool_path)
        self.rotator = ProxyRotator(self.pool, max_retries=max_retries)

    @classmethod
    def from_pool_file(cls, pool_path: str, max_retries: int = 3) -> "ProxyForgeAsyncClient":
        return cls(pool_path, max_retries)

    async def __aenter__(self) -> "ProxyForgeAsyncClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response | None:
        retries = min(self.rotator.max_retries, max(1, self.rotator.pool_size))
        
        for attempt in range(retries):
            p = self.rotator._next()
            if not p:
                break
                
            proxy_uri = p["proxy"]
            try:
                async with httpx.AsyncClient(proxy=proxy_uri, verify=False) as client:
                    resp = await client.request(method, url, **kwargs)
                    resp.raise_for_status()
                    return resp
            except httpx.RequestError:
                self.rotator.evict(proxy_uri)
        return None

    async def get(self, url: str, **kwargs: Any) -> httpx.Response | None:
        return await self.request("GET", url, **kwargs)
