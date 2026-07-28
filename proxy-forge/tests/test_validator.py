import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
import asyncio

from proxyforge.core.validator import ProxyValidator

def test_pre_filter():
    validator = ProxyValidator(min_anonymity=("elite", "anonymous"))
    raw_data = [
        {"proxy": "socks5://208.102.51.6:58208", "anonymity": "transparent"},
        {"proxy": "http://1.2.3.4:8080", "anonymity": "elite"},
        {"proxy": "http://5.6.7.8:8080", "anonymity": "anonymous"},
        {"proxy": "http://9.0.1.2:8080", "anonymity": "unknown"},
    ]
    
    filtered = validator.pre_filter(raw_data)
    
    assert len(filtered) == 2
    assert filtered[0]["proxy"] == "http://1.2.3.4:8080"
    assert filtered[1]["proxy"] == "http://5.6.7.8:8080"

@pytest.mark.asyncio
async def test_probe_returns_alive_on_200():
    validator = ProxyValidator()
    entry = {"proxy": "http://127.0.0.1:8080"}
    
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"origin": "1.2.3.4"})
    
    mock_session = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__.return_value = mock_response
    mock_context_manager.__aexit__.return_value = None
    mock_session.get.return_value = mock_context_manager
    
    sem = asyncio.Semaphore(1)
    
    result = await validator._probe(mock_session, sem, entry)
    
    assert result["alive"] is True
    assert result["latency_ms"] is not None
