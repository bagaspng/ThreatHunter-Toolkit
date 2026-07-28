"""
ProxyPool module.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("proxyforge.pool")

class ProxyPool:
    def __init__(self, proxies: list[dict[str, Any]] | None = None, updated_at: str | None = None) -> None:
        self.proxies = proxies or []
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()

    @classmethod
    def build(cls, alive_entries: list[dict[str, Any]]) -> "ProxyPool":
        scored_proxies = []
        for entry in alive_entries:
            if not entry.get("alive"):
                continue
            
            latency = entry.get("latency_ms") or 0.0
            anonymity = entry.get("anonymity", "").lower()
            
            if anonymity == "elite":
                bonus = 20.0
            elif anonymity == "anonymous":
                bonus = 10.0
            else:
                bonus = 0.0
                
            score = max(0.0, 100.0 - (latency / 50.0)) + bonus
            
            scored_entry = entry.copy()
            scored_entry["score"] = score
            scored_proxies.append(scored_entry)
            
        scored_proxies.sort(key=lambda x: x["score"], reverse=True)
        return cls(proxies=scored_proxies)

    @classmethod
    def load(cls, path: str) -> "ProxyPool":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(proxies=data.get("proxies", []), updated_at=data.get("updated_at"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Failed to load pool from %s: %s", path, e)
            return cls()

    def save(self, path: str) -> None:
        data = {
            "count": len(self.proxies),
            "updated_at": self.updated_at,
            "proxies": self.proxies
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
    def summary(self) -> dict[str, Any]:
        if not self.proxies:
            return {"count": 0}
            
        latencies = [p["latency_ms"] for p in self.proxies if p.get("latency_ms") is not None]
        top_score = self.proxies[0]["score"] if self.proxies else 0.0
        
        latencies.sort()
        count = len(latencies)
        p50 = latencies[int(count * 0.5)] if count > 0 else 0
        p95 = latencies[int(count * 0.95)] if count > 0 else 0
        
        countries: dict[str, int] = {}
        for p in self.proxies:
            geo = p.get("geolocation", {})
            country = geo.get("country", "Unknown")
            countries[country] = countries.get(country, 0) + 1
            
        return {
            "count": len(self.proxies),
            "updated_at": self.updated_at,
            "latency_p50": p50,
            "latency_p95": p95,
            "top_score": top_score,
            "countries": countries
        }
