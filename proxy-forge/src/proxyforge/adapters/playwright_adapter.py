"""Adapter: Playwright"""

from typing import Any
from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator

class ProxyForgePlaywrightAdapter:
    def __init__(self, pool_path: str):
        self.pool = ProxyPool.load(pool_path)
        self.rotator = ProxyRotator(self.pool)

    def get_launch_options(self, **kwargs: Any) -> dict[str, Any]:
        """Inject proxy into playwright launch options."""
        p = self.rotator._next()
        if p:
            kwargs["proxy"] = {"server": p["proxy"]}
        return kwargs
