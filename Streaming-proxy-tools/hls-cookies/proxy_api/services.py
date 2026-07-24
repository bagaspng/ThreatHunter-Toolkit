"""Django wiring for the framework-agnostic core service."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import redis
import requests
from celery.result import AsyncResult
from django.conf import settings

import config
from core.cookie_store import JsonCookieStore, RedisCookieStore
from core.handshake import HandshakeManager, has_base_cookies
from core.hls_client import HlsProxyService
from core.segment_cache import cache_path_for_url
from core.session_factory import build_session_from_snapshot, fetch_with_session
from core.url_validation import validate_proxy_url as validate_core_proxy_url
from scraper import logger

_json_seed_store = JsonCookieStore(config.COOKIES_CACHE_FILE, config.COOKIES_MANUAL_FILE)
_cookie_store = None
_handshake_manager = HandshakeManager(config.STREAM_REFERER, logger)
_session_lock = threading.Lock()
_proxy_session: requests.Session | None = None
_loaded_base_cookie_fingerprint: tuple[tuple[str, str, str, str], ...] = ()


def _cookie_fingerprint(cookies: list[dict]) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(sorted((str(c.get("name", "")), str(c.get("value", "")), str(c.get("domain", "")), str(c.get("path", "/"))) for c in cookies))


def build_cookie_store():
    backend = getattr(settings, "COOKIE_STORE_BACKEND", "json").lower()
    if backend == "redis":
        client = redis.Redis.from_url(getattr(settings, "REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        return RedisCookieStore(
            client,
            base_ttl_seconds=getattr(settings, "COOKIE_BASE_TTL_SECONDS", 3600),
            camera_ttl_seconds=getattr(settings, "COOKIE_CAMERA_TTL_SECONDS", 300),
            lock_ttl_seconds=getattr(settings, "COOKIE_REFRESH_LOCK_TTL_SECONDS", 120),
            seed_store=_json_seed_store,
        )
    return _json_seed_store


def get_cookie_store():
    global _cookie_store
    if _cookie_store is None:
        _cookie_store = build_cookie_store()
    return _cookie_store


def reset_cookie_store_for_tests(store=None) -> None:
    global _cookie_store, _proxy_session, _loaded_base_cookie_fingerprint
    _cookie_store = store
    with _session_lock:
        _proxy_session = None
        _loaded_base_cookie_fingerprint = ()


def clear_handshake_cache() -> None:
    _handshake_manager.clear()


def get_session() -> requests.Session:
    global _proxy_session, _loaded_base_cookie_fingerprint
    cookies = get_cookie_store().load_base_cookies()
    fingerprint = _cookie_fingerprint(cookies)
    with _session_lock:
        if _proxy_session is None or fingerprint != _loaded_base_cookie_fingerprint:
            _proxy_session = build_session_from_snapshot(cookies)
            _loaded_base_cookie_fingerprint = fingerprint
            clear_handshake_cache()
            logger.info(
                f"Session Django dibuat dengan {len(cookies)} cookie "
                f"({'cache' if cookies else 'kosong - kemungkinan 403 dari CDN'})"
            )
        return _proxy_session


def rebuild_session(cookies: list[dict]) -> None:
    global _proxy_session, _loaded_base_cookie_fingerprint
    get_cookie_store().save_base_cookies(cookies)
    with _session_lock:
        _proxy_session = build_session_from_snapshot(cookies)
        _loaded_base_cookie_fingerprint = _cookie_fingerprint(cookies)
    clear_handshake_cache()


def refresh_cookies_internal(target_url: str) -> list[dict]:
    # Compatibility shim for older Flask tests and direct callers.
    from upstream_auth.selenium_refresher import refresh_base_cookies

    cookies = refresh_base_cookies(target_url)
    rebuild_session(cookies)
    return cookies


def allowed_proxy_hosts() -> set[str]:
    return {host.lower() for host in getattr(config, "ALLOWED_COOKIE_REFRESH_HOSTS", ())}


def _use_shared_cookie_store_for_hls() -> bool:
    return isinstance(get_cookie_store(), RedisCookieStore)


def get_hls_service() -> HlsProxyService:
    return HlsProxyService(
        get_session=get_session,
        refresh_base_cookies=refresh_cookies_internal,
        handshake_manager=_handshake_manager,
        fetch_with_session=fetch_with_session,
        cache_path_for_url=lambda url: cache_path_for_url(url, Path("cache_segments")),
        referer=config.STREAM_REFERER,
        timeout=config.TIMEOUT,
        portal_url=config.PORTAL_URL,
        logger=logger,
        allowed_hosts=allowed_proxy_hosts(),
        cookie_store=get_cookie_store() if _use_shared_cookie_store_for_hls() else None,
    )


def validate_proxy_url(raw_url: str | None) -> str:
    return validate_core_proxy_url(raw_url, allowed_proxy_hosts())


def session_has_base_cookies() -> bool:
    return has_base_cookies(get_session())


def refresh_status() -> dict:
    return get_cookie_store().get_refresh_status()


def request_cookie_refresh(target_url: str, force: bool = False, wait: bool = False, wait_timeout: float | None = None) -> dict:
    store = get_cookie_store()
    status = store.get_refresh_status()
    if session_has_base_cookies() and not force:
        return {"http_status": 200, "status": "ready", "version": status.get("version"), "refreshed_at": status.get("refreshed_at")}

    if hasattr(store, "refresh_in_progress") and store.refresh_in_progress():
        return {"http_status": 202, "status": "refreshing", "task_id": status.get("task_id")}

    from .tasks import refresh_base_cookies_task

    result = refresh_base_cookies_task.delay(target_url)
    task_id = getattr(result, "id", None) or status.get("task_id")

    if wait:
        timeout = wait_timeout if wait_timeout is not None else getattr(settings, "REFRESH_WAIT_TIMEOUT_SECONDS", 5.0)
        try:
            task_result = result.get(timeout=timeout)
            return {"http_status": 200, **task_result}
        except Exception:
            latest = store.get_refresh_status()
            if latest.get("status") == "failed":
                return {"http_status": 503, "status": "failed", "task_id": task_id, "message": "Refresh cookie dasar belum berhasil."}

    return {"http_status": 202, "status": "refreshing", "task_id": task_id}


def enqueue_refresh_if_needed(target_url: str) -> dict:
    return request_cookie_refresh(target_url, force=True, wait=False)
