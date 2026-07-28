import os
import json
import pytest
from proxyforge.core.pool import ProxyPool

def test_build_pool_scoring():
    entries = [
        {"proxy": "http://1", "alive": True, "latency_ms": 1000, "anonymity": "transparent"}, # score: 100 - 20 + 0 = 80
        {"proxy": "http://2", "alive": True, "latency_ms": 500, "anonymity": "elite"}, # score: 100 - 10 + 20 = 110
        {"proxy": "http://3", "alive": True, "latency_ms": 6000, "anonymity": "anonymous"}, # score: 0 + 10 = 10
        {"proxy": "http://4", "alive": False}, # should be ignored
    ]
    
    pool = ProxyPool.build(entries)
    
    assert len(pool.proxies) == 3
    # http://2 should be first
    assert pool.proxies[0]["proxy"] == "http://2"
    assert pool.proxies[0]["score"] == 110.0
    
    # http://1 should be second
    assert pool.proxies[1]["proxy"] == "http://1"
    assert pool.proxies[1]["score"] == 80.0
    
    # http://3 should be third
    assert pool.proxies[2]["proxy"] == "http://3"
    assert pool.proxies[2]["score"] == 10.0

def test_save_and_load(tmp_path):
    path = tmp_path / "pool.json"
    
    original_pool = ProxyPool(proxies=[{"proxy": "http://test", "score": 100}], updated_at="2026-07-28T00:00:00")
    original_pool.save(str(path))
    
    loaded_pool = ProxyPool.load(str(path))
    
    assert len(loaded_pool.proxies) == 1
    assert loaded_pool.proxies[0]["proxy"] == "http://test"
    assert loaded_pool.updated_at == "2026-07-28T00:00:00"

def test_summary():
    entries = [
        {"proxy": "http://1", "alive": True, "latency_ms": 100, "anonymity": "elite", "geolocation": {"country": "US"}},
        {"proxy": "http://2", "alive": True, "latency_ms": 200, "anonymity": "elite", "geolocation": {"country": "US"}},
        {"proxy": "http://3", "alive": True, "latency_ms": 300, "anonymity": "elite", "geolocation": {"country": "ID"}},
    ]
    
    pool = ProxyPool.build(entries)
    summary = pool.summary()
    
    assert summary["count"] == 3
    assert summary["countries"]["US"] == 2
    assert summary["countries"]["ID"] == 1
    assert summary["top_score"] > 0
