"""Adapter: AIOHTTP Client"""

from typing import Any
import aiohttp
from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator

class ProxyForgeAiohttpClient:
    def __init__(self, pool_path: str, max_retries: int = 3):
        self.pool = ProxyPool.load(pool_path)
        self.rotator = ProxyRotator(self.pool, max_retries=max_retries)

    async def request(self, method: str, url: str, **kwargs: Any) -> aiohttp.ClientResponse | None:
        retries = min(self.rotator.max_retries, max(1, self.rotator.pool_size))
        
        for attempt in range(retries):
            p = self.rotator._next()
            if not p:
                break
                
            proxy_uri = p["proxy"]
            try:
                async with aiohttp.ClientSession() as session:
                    resp = await session.request(method, url, proxy=proxy_uri, **kwargs)
                    resp.raise_for_status()
                    return resp
            except aiohttp.ClientError:
                self.rotator.evict(proxy_uri)
        return None

    async def get(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse | None:
        return await self.request("GET", url, **kwargs)
