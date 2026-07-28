import pytest
from unittest.mock import patch, MagicMock
from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator
import requests

def test_rotator_next_cycle():
    pool = ProxyPool(proxies=[{"proxy": "p1"}, {"proxy": "p2"}])
    rotator = ProxyRotator(pool)
    
    assert rotator._next()["proxy"] == "p1"
    assert rotator._next()["proxy"] == "p2"
    assert rotator._next()["proxy"] == "p1"

def test_evict():
    pool = ProxyPool(proxies=[{"proxy": "p1"}, {"proxy": "p2"}])
    rotator = ProxyRotator(pool)
    
    rotator.evict("p1")
    assert rotator.pool_size == 1
    assert rotator._next()["proxy"] == "p2"
    assert rotator._next()["proxy"] == "p2"

@patch("proxyforge.core.rotator.requests.request")
def test_fetch_success(mock_request):
    pool = ProxyPool(proxies=[{"proxy": "p1"}])
    rotator = ProxyRotator(pool)
    
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_request.return_value = mock_response
    
    result = rotator.fetch("http://example.com")
    
    assert result is mock_response
    mock_request.assert_called_once_with(
        method="GET",
        url="http://example.com",
        proxies={"http": "p1", "https": "p1"},
        timeout=10
    )

@patch("proxyforge.core.rotator.requests.request")
def test_fetch_retries_and_evicts(mock_request):
    pool = ProxyPool(proxies=[{"proxy": "p1"}, {"proxy": "p2"}])
    rotator = ProxyRotator(pool, max_retries=2)
    
    mock_success = MagicMock(spec=requests.Response)
    mock_success.status_code = 200
    
    mock_request.side_effect = [requests.RequestException("Connection error"), mock_success]
    
    result = rotator.fetch("http://example.com")
    
    assert result is mock_success
    assert mock_request.call_count == 2
    assert rotator.pool_size == 1
    assert rotator._pool[0]["proxy"] == "p2"
