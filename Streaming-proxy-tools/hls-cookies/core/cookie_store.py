"""Cookie store abstractions for base and per-camera cookies."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CookieFileSnapshot:
    status: str
    cookies: list[dict]
    path: str
    version: int | None = None
    refreshed_at: str | None = None
    error: str | None = None


class CookieStore(Protocol):
    def load_base_cookies(self) -> list[dict]: ...
    def save_base_cookies(self, cookies: list[dict]) -> None: ...
    def get_camera_cookies(self, camera_key: str) -> list[dict]: ...
    def set_camera_cookies(self, camera_key: str, cookies: list[dict]) -> None: ...
    def invalidate_camera_cookies(self, camera_key: str) -> None: ...
    def get_refresh_status(self) -> dict: ...


def normalize_cookie_list(raw_list: list[dict]) -> list[dict]:
    normalized = []
    for cookie in raw_list:
        if not cookie.get("name") or cookie.get("value") is None:
            continue
        normalized.append(
            {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie.get("domain", ""),
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", False),
            }
        )
    return normalized


class JsonCookieStore:
    def __init__(self, cache_path: str | Path, manual_path: str | Path | None = None):
        self.cache_path = Path(cache_path)
        self.manual_path = Path(manual_path) if manual_path else None
        self._camera_cookies: dict[str, list[dict]] = {}
        self._version = 0
        self._refreshed_at: str | None = None
        self._last_snapshot = CookieFileSnapshot("missing", [], str(self.cache_path))

    def _read_cookie_file(self, path: Path) -> CookieFileSnapshot:
        if not path.exists():
            return CookieFileSnapshot("missing", [], str(path))
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            return CookieFileSnapshot("corrupt", [], str(path), error=str(exc))

        version = None
        refreshed_at = None
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict):
            raw_list = data.get("cookies", [])
            version = data.get("version")
            refreshed_at = data.get("refreshed_at") or data.get("scraped_at")
        else:
            return CookieFileSnapshot("empty", [], str(path))

        cookies = normalize_cookie_list(raw_list)
        if not cookies:
            return CookieFileSnapshot("empty", [], str(path), version=version, refreshed_at=refreshed_at)
        return CookieFileSnapshot("ok", cookies, str(path), version=version, refreshed_at=refreshed_at)

    def load_base_cookies(self) -> list[dict]:
        cache_snapshot = self._read_cookie_file(self.cache_path)
        self._last_snapshot = cache_snapshot
        if cache_snapshot.status == "ok":
            self._version = int(cache_snapshot.version or self._version or 0)
            self._refreshed_at = cache_snapshot.refreshed_at
            return list(cache_snapshot.cookies)

        if self.manual_path:
            manual_snapshot = self._read_cookie_file(self.manual_path)
            if manual_snapshot.status == "ok":
                self._last_snapshot = manual_snapshot
                return list(manual_snapshot.cookies)

        return []

    def save_base_cookies(self, cookies: list[dict]) -> None:
        normalized = normalize_cookie_list(cookies)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._version += 1
        self._refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload = {
            "version": self._version,
            "refreshed_at": self._refreshed_at,
            "cookie_count": len(normalized),
            "cookies": normalized,
        }
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.cache_path.name}.", suffix=".tmp", dir=str(self.cache_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4, ensure_ascii=False)
            os.replace(tmp_name, self.cache_path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        self._last_snapshot = CookieFileSnapshot("ok", normalized, str(self.cache_path), self._version, self._refreshed_at)

    def get_camera_cookies(self, camera_key: str) -> list[dict]:
        return list(self._camera_cookies.get(camera_key, []))

    def set_camera_cookies(self, camera_key: str, cookies: list[dict]) -> None:
        self._camera_cookies[camera_key] = normalize_cookie_list(cookies)

    def invalidate_camera_cookies(self, camera_key: str) -> None:
        self._camera_cookies.pop(camera_key, None)

    def get_refresh_status(self) -> dict:
        return {
            "source": self._last_snapshot.path,
            "status": self._last_snapshot.status,
            "version": self._version,
            "refreshed_at": self._refreshed_at,
            "error": self._last_snapshot.error,
        }
class RedisCookieStore:
    BASE_KEY = "hls:auth:base"
    STATUS_KEY = "hls:auth:refresh-status"
    LOCK_KEY = "hls:auth:refresh-lock"

    def __init__(
        self,
        client,
        base_ttl_seconds: int = 3600,
        camera_ttl_seconds: int = 300,
        lock_ttl_seconds: int = 120,
        seed_store: CookieStore | None = None,
    ):
        self.client = client
        self.base_ttl_seconds = base_ttl_seconds
        self.camera_ttl_seconds = camera_ttl_seconds
        self.lock_ttl_seconds = lock_ttl_seconds
        self.seed_store = seed_store

    def _get_json(self, key: str) -> dict | None:
        raw = self.client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def _set_json(self, key: str, payload: dict, ex: int | None = None) -> None:
        self.client.set(key, json.dumps(payload, ensure_ascii=False), ex=ex)

    def _camera_key(self, camera_key: str) -> str:
        digest = hashlib.sha256(camera_key.encode("utf-8")).hexdigest()
        return f"hls:auth:camera:{digest}"

    def load_base_cookies(self) -> list[dict]:
        payload = self._get_json(self.BASE_KEY)
        if payload:
            return normalize_cookie_list(payload.get("cookies", []))
        if self.seed_store:
            seeded = self.seed_store.load_base_cookies()
            if seeded:
                self.save_base_cookies(seeded)
                return seeded
        return []

    def save_base_cookies(self, cookies: list[dict]) -> None:
        normalized = normalize_cookie_list(cookies)
        current = self._get_json(self.BASE_KEY) or {}
        version = int(current.get("version") or 0) + 1
        refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload = {
            "version": version,
            "refreshed_at": refreshed_at,
            "cookie_count": len(normalized),
            "cookies": normalized,
        }
        self._set_json(self.BASE_KEY, payload, ex=self.base_ttl_seconds)
        self.set_refresh_status("ready", version=version, refreshed_at=refreshed_at, error=None)

    def get_camera_cookies(self, camera_key: str) -> list[dict]:
        payload = self._get_json(self._camera_key(camera_key))
        return normalize_cookie_list(payload.get("cookies", [])) if payload else []

    def set_camera_cookies(self, camera_key: str, cookies: list[dict]) -> None:
        payload = {
            "camera_key": camera_key,
            "cookies": normalize_cookie_list(cookies),
            "stored_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        self._set_json(self._camera_key(camera_key), payload, ex=self.camera_ttl_seconds)

    def invalidate_camera_cookies(self, camera_key: str) -> None:
        self.client.delete(self._camera_key(camera_key))

    def get_refresh_status(self) -> dict:
        return self._get_json(self.STATUS_KEY) or {"status": "missing", "version": 0, "refreshed_at": None, "error": None}

    def set_refresh_status(
        self,
        status: str,
        task_id: str | None = None,
        version: int | None = None,
        refreshed_at: str | None = None,
        error: str | None = None,
    ) -> None:
        payload = self.get_refresh_status()
        payload.update({"status": status, "task_id": task_id, "error": error})
        if version is not None:
            payload["version"] = version
        if refreshed_at is not None:
            payload["refreshed_at"] = refreshed_at
        self._set_json(self.STATUS_KEY, payload)

    def acquire_refresh_lock(self, owner: str) -> bool:
        return bool(self.client.set(self.LOCK_KEY, owner, nx=True, ex=self.lock_ttl_seconds))

    def release_refresh_lock(self, owner: str) -> None:
        current = self.client.get(self.LOCK_KEY)
        if isinstance(current, bytes):
            current = current.decode("utf-8")
        if current == owner:
            self.client.delete(self.LOCK_KEY)

    def refresh_in_progress(self) -> bool:
        return self.client.get(self.LOCK_KEY) is not None

