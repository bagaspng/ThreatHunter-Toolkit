"""Per-camera stream handshake and cookie validation."""

from __future__ import annotations

import threading
import urllib.parse
from collections.abc import Callable

import requests

from .camera_identity import CameraIdentity, extract_camera_identity, normalize_camera_path

BASE_COOKIE_NAMES = {"cctv_access", "stream_token"}
CAMERA_COOKIE_NAMES = {"hlsSession", "cookieCheck"}


def cookie_domain_matches(hostname: str, cookie_domain: str) -> bool:
    domain = (cookie_domain or "").lstrip(".").lower()
    if not domain:
        return True
    return hostname == domain or hostname.endswith(f".{domain}")


def cookie_path_matches(camera_path: str, cookie_path: str) -> bool:
    return normalize_camera_path(cookie_path or "/") == camera_path


def has_base_cookies(session: requests.Session) -> bool:
    present = {cookie.name for cookie in session.cookies}
    return BASE_COOKIE_NAMES.issubset(present)


def camera_cookie_names(session: requests.Session, identity: CameraIdentity) -> set[str]:
    names: set[str] = set()
    for cookie in session.cookies:
        if cookie.name not in CAMERA_COOKIE_NAMES:
            continue
        if not cookie_domain_matches(identity.hostname, cookie.domain):
            continue
        if not cookie_path_matches(identity.camera_path, cookie.path):
            continue
        names.add(cookie.name)
    return names


def has_camera_cookies(session: requests.Session, identity: CameraIdentity) -> bool:
    return CAMERA_COOKIE_NAMES.issubset(camera_cookie_names(session, identity))


class HandshakeManager:
    def __init__(self, referer: str, logger=None):
        self.referer = referer
        self.logger = logger
        self.handshaked_paths: set[str] = set()
        self._handshake_lock = threading.Lock()
        self._camera_locks: dict[str, threading.Lock] = {}
        self._camera_locks_lock = threading.Lock()

    def _get_camera_lock(self, camera_key: str) -> threading.Lock:
        with self._camera_locks_lock:
            lock = self._camera_locks.get(camera_key)
            if lock is None:
                lock = threading.Lock()
                self._camera_locks[camera_key] = lock
            return lock

    def invalidate_camera_session(self, session: requests.Session, url: str) -> None:
        identity = extract_camera_identity(url)
        if identity is None:
            return

        to_clear = []
        for cookie in session.cookies:
            if cookie.name not in CAMERA_COOKIE_NAMES:
                continue
            if cookie_domain_matches(identity.hostname, cookie.domain) and cookie_path_matches(identity.camera_path, cookie.path):
                to_clear.append((cookie.domain, cookie.path, cookie.name))

        for domain, path, name in to_clear:
            try:
                session.cookies.clear(domain=domain, path=path, name=name)
            except KeyError:
                pass

        with self._handshake_lock:
            self.handshaked_paths.discard(identity.camera_key)

    def clear(self) -> None:
        with self._handshake_lock:
            self.handshaked_paths.clear()

    def handshake_stream_session(self, session: requests.Session, m3u8_url: str) -> bool:
        identity = extract_camera_identity(m3u8_url)
        if identity is None:
            return True

        with self._handshake_lock:
            if identity.camera_key in self.handshaked_paths and has_camera_cookies(session, identity):
                return True
            self.handshaked_paths.discard(identity.camera_key)

        camera_lock = self._get_camera_lock(identity.camera_key)
        with camera_lock:
            with self._handshake_lock:
                if identity.camera_key in self.handshaked_paths and has_camera_cookies(session, identity):
                    return True
                self.handshaked_paths.discard(identity.camera_key)

            parsed = urllib.parse.urlparse(m3u8_url)
            handshake_path = f"{identity.camera_path}/"
            handshake_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, handshake_path, "", "", ""))

            if self.logger:
                self.logger.info(f"[HANDSHAKE] Inisialisasi sesi untuk {identity.camera_key}")
            try:
                resp = session.get(
                    handshake_url,
                    headers={
                        "Referer": self.referer,
                        "Origin": self.referer.rstrip("/"),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Sec-Fetch-Site": "same-site",
                        "Sec-Fetch-Mode": "navigate",
                    },
                    timeout=10,
                    allow_redirects=True,
                )
            except Exception as exc:
                if self.logger:
                    self.logger.warning(f"[HANDSHAKE] Gagal untuk {identity.camera_key}: {exc}")
                return False

            if has_camera_cookies(session, identity):
                with self._handshake_lock:
                    self.handshaked_paths.add(identity.camera_key)
                if self.logger:
                    self.logger.info(f"[HANDSHAKE] HTTP {resp.status_code} | cookie kamera lengkap untuk {identity.camera_key}")
                return True

            if self.logger:
                self.logger.warning(f"[HANDSHAKE] HTTP {resp.status_code} | cookie kamera belum lengkap untuk {identity.camera_key}")
            return False