import asyncio
import logging
from typing import Any

import aiohttp

from .aggregator import aggregate

logger = logging.getLogger("proxyforge.validator")

class ProxyValidator:
    def __init__(
        self,
        probe_url: str = "https://httpbin.org/ip",
        timeout: int = 8,
        concurrency: int = 100,
        min_anonymity: tuple[str, ...] = ("anonymous", "elite", "unknown"),
    ) -> None:
        self.probe_url = probe_url
        self.timeout = timeout
        self.concurrency = concurrency
        self.min_anonymity = min_anonymity

    def pre_filter(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = []
        for entry in raw:
            anonymity = entry.get("anonymity", "").lower()
            if anonymity in self.min_anonymity:
                filtered.append(entry)
        return filtered

    async def _probe(
        self,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        proxy_uri = entry.get("proxy")
        if not proxy_uri:
             return {**entry, "alive": False, "latency_ms": None}
             
        async with sem:
            try:
                start_time = asyncio.get_event_loop().time()
                timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
                async with session.get(
                    self.probe_url, 
                    proxy=proxy_uri, 
                    timeout=timeout_obj
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "origin" in data:
                            latency = (asyncio.get_event_loop().time() - start_time) * 1000
                            return {**entry, "alive": True, "latency_ms": latency}
            except (aiohttp.ClientProxyConnectionError, asyncio.TimeoutError, aiohttp.ClientError, asyncio.CancelledError) as exc:
                logger.debug("Probe failed (%s): %s", proxy_uri, exc)
            
            return {**entry, "alive": False, "latency_ms": None}

    async def validate_all(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(self.concurrency)
        async with aiohttp.ClientSession() as session:
            tasks = [self._probe(session, sem, entry) for entry in candidates]
            results = await asyncio.gather(*tasks)
            return list(results)

    async def run(self) -> list[dict[str, Any]]:
        raw_data = await aggregate()
        candidates = self.pre_filter(raw_data)
        self.last_total_checked = len(candidates)
        validated = await self.validate_all(candidates)
        return [p for p in validated if p.get("alive")]
