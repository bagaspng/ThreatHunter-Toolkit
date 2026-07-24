from __future__ import annotations

from celery import shared_task

import config
from upstream_auth.selenium_refresher import refresh_base_cookies as selenium_refresh_base_cookies

from . import services


def _safe_error(exc: Exception) -> str:
    return exc.__class__.__name__


@shared_task(bind=True, name="proxy_api.refresh_base_cookies")
def refresh_base_cookies_task(self, target_url: str | None = None) -> dict:
    owner = self.request.id or "eager-refresh"
    store = services.get_cookie_store()
    if hasattr(store, "acquire_refresh_lock") and not store.acquire_refresh_lock(owner):
        status = store.get_refresh_status()
        task_id = status.get("task_id") or owner
        return {"status": "refreshing", "task_id": task_id}

    try:
        if hasattr(store, "set_refresh_status"):
            store.set_refresh_status("refreshing", task_id=owner, error=None)
        cookies = selenium_refresh_base_cookies(target_url or config.PORTAL_URL)
        store.save_base_cookies(cookies)
        services.clear_handshake_cache()
        return {"status": "ready", "task_id": owner, "cookie_count": len(cookies)}
    except Exception as exc:
        if hasattr(store, "set_refresh_status"):
            store.set_refresh_status("failed", task_id=owner, error=_safe_error(exc))
        raise
    finally:
        if hasattr(store, "release_refresh_lock"):
            store.release_refresh_lock(owner)
