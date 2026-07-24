"""Framework-agnostic HLS proxy orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from pathlib import Path
from collections.abc import Iterable
from typing import Callable

import requests

from .camera_identity import extract_camera_identity
from .cookie_store import CookieStore
from .handshake import CAMERA_COOKIE_NAMES, HandshakeManager, has_base_cookies
from .playlist_rewriter import rewrite_playlist
from .segment_cache import SegmentCache, detect_content_type, parse_range_request
from .url_validation import ProxyUrlError, validate_redirect_location


@dataclass
class ProxyPayload:
    body: bytes | Iterable[bytes]
    status: int
    headers: dict[str, str]


class HlsProxyService:
    def __init__(
        self,
        get_session: Callable[[], requests.Session],
        refresh_base_cookies: Callable[[str], list[dict]],
        handshake_manager: HandshakeManager,
        fetch_with_session: Callable[..., requests.Response],
        cache_path_for_url: Callable[[str], Path],
        referer: str,
        timeout: int,
        portal_url: str,
        logger=None,
        allowed_hosts: set[str] | None = None,
        cookie_store: CookieStore | None = None,
    ):
        self.get_session = get_session
        self.refresh_base_cookies = refresh_base_cookies
        self.handshake_manager = handshake_manager
        self.fetch_with_session = fetch_with_session
        self.cache_path_for_url = cache_path_for_url
        self.referer = referer
        self.timeout = timeout
        self.portal_url = portal_url
        self.logger = logger
        self.allowed_hosts = allowed_hosts or set()
        self.segment_cache = SegmentCache(cache_path_for_url("").parent if cache_path_for_url("").name else cache_path_for_url(""))
        self.cookie_store = cookie_store

    def _session_for_url(self, url: str) -> requests.Session:
        if self.cookie_store is None:
            return self.get_session()
        identity = extract_camera_identity(url)
        camera_cookies = self.cookie_store.get_camera_cookies(identity.camera_key) if identity else []
        from .session_factory import build_session_from_snapshot
        return build_session_from_snapshot(self.cookie_store.load_base_cookies(), camera_cookies)

    def _persist_camera_cookies(self, session: requests.Session, url: str) -> None:
        if self.cookie_store is None:
            return
        identity = extract_camera_identity(url)
        if identity is None:
            return
        cookies = []
        for cookie in session.cookies:
            if cookie.name not in CAMERA_COOKIE_NAMES:
                continue
            cookies.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                }
            )
        if cookies:
            self.cookie_store.set_camera_cookies(identity.camera_key, cookies)

    def _invalidate_camera(self, session: requests.Session, url: str) -> None:
        self.handshake_manager.invalidate_camera_session(session, url)
        if self.cookie_store is not None:
            identity = extract_camera_identity(url)
            if identity is not None:
                self.cookie_store.invalidate_camera_cookies(identity.camera_key)

    def _fetch_playlist_upstream(self, session: requests.Session, url: str) -> requests.Response:
        resp = self.fetch_with_session(session, url, referer=self.referer, timeout=self.timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            redirected_url = validate_redirect_location(url, resp.headers.get("Location"), self.allowed_hosts)
            resp = self.fetch_with_session(session, redirected_url, referer=self.referer, timeout=self.timeout, allow_redirects=False)
            if resp.status_code in (301, 302, 303, 307, 308):
                raise ProxyUrlError("Too many upstream redirects", 502)
        return resp

    def fetch_playlist(self, m3u8_url: str) -> ProxyPayload:
        session = self._session_for_url(m3u8_url)
        if not has_base_cookies(session):
            try:
                self.refresh_base_cookies(self.portal_url)
                session = self._session_for_url(m3u8_url)
            except Exception as exc:
                if self.logger:
                    self.logger.warning(f"[REFRESH] Gagal refresh base cookie: {exc}")

        self.handshake_manager.handshake_stream_session(session, m3u8_url)
        self._persist_camera_cookies(session, m3u8_url)
        resp = self._fetch_playlist_upstream(session, m3u8_url)

        if resp.status_code in (401, 403):
            self._invalidate_camera(session, m3u8_url)
            self.handshake_manager.handshake_stream_session(session, m3u8_url)
            self._persist_camera_cookies(session, m3u8_url)
            resp = self._fetch_playlist_upstream(session, m3u8_url)

        if resp.status_code in (401, 403):
            try:
                self.refresh_base_cookies(self.portal_url)
                session = self._session_for_url(m3u8_url)
                self.handshake_manager.handshake_stream_session(session, m3u8_url)
                self._persist_camera_cookies(session, m3u8_url)
                resp = self._fetch_playlist_upstream(session, m3u8_url)
            except Exception as exc:
                if self.logger:
                    self.logger.warning(f"[REFRESH] Retry refresh base gagal: {exc}")

        if resp.status_code in (401, 403):
            body = (
                f"{resp.status_code} dari CDN - Cookie stream belum terbentuk untuk URL ini. "
                "Coba POST /api/refresh-cookies atau buka stream di browser asli lalu export cookies terbaru."
            ).encode()
            return ProxyPayload(body, resp.status_code, {"Access-Control-Allow-Origin": "*"})

        resp.raise_for_status()
        rewritten = rewrite_playlist(resp.text, m3u8_url).encode()
        return ProxyPayload(
            rewritten,
            200,
            {
                "Content-Type": "application/vnd.apple.mpegurl",
                "Cache-Control": "no-store, no-cache",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Range, Content-Type",
                "Access-Control-Expose-Headers": "Content-Length, Content-Range",
            },
        )

    def _segment_response_headers(self, source_headers: dict, fallback_url: str, body_len: int | None = None) -> dict[str, str]:
        safe_names = {
            "content-type",
            "content-length",
            "content-range",
            "accept-ranges",
            "cache-control",
            "etag",
            "last-modified",
        }
        headers: dict[str, str] = {}
        for key, value in source_headers.items():
            if key.lower() in safe_names:
                headers[key] = value
        headers.setdefault("Content-Type", detect_content_type(fallback_url))
        if body_len is not None:
            headers["Content-Length"] = str(body_len)
        headers.setdefault("Accept-Ranges", "bytes")
        headers.setdefault("Cache-Control", "no-store")
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Headers"] = "Range, If-Range, If-None-Match, If-Modified-Since, Content-Type"
        headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges, ETag, Last-Modified"
        return headers

    def _fetch_segment_upstream(self, session: requests.Session, url: str, request_headers: dict[str, str]) -> requests.Response:
        return self.fetch_with_session(
            session,
            url,
            referer=self.referer,
            timeout=self.timeout,
            extra_headers=request_headers,
        )

    def fetch_segment(
        self,
        seg_url: str,
        range_header: str | None = None,
        request_headers: dict[str, str] | None = None,
    ) -> ProxyPayload:
        request_headers = dict(request_headers or {})
        if range_header and "Range" not in request_headers:
            request_headers["Range"] = range_header
        range_header = request_headers.get("Range")
        cache_file = self.cache_path_for_url(seg_url)

        if cache_file.exists() and not self.segment_cache.is_expired(cache_file):
            body = cache_file.read_bytes()
            body_len = len(body)
            parsed_range = parse_range_request(range_header, body_len)
            if parsed_range is not None and not parsed_range.satisfiable:
                return ProxyPayload(
                    b"",
                    416,
                    self._segment_response_headers(
                        {"Content-Range": f"bytes */{body_len}"},
                        seg_url,
                        0,
                    ),
                )
            if parsed_range is not None:
                sliced = body[parsed_range.start : parsed_range.end + 1]
                return ProxyPayload(
                    sliced,
                    206,
                    self._segment_response_headers(
                        {"Content-Range": f"bytes {parsed_range.start}-{parsed_range.end}/{body_len}"},
                        seg_url,
                        len(sliced),
                    ),
                )
            if self.logger:
                self.logger.debug(f"CACHE HIT: {seg_url.split('/')[-1]}")
            return ProxyPayload(body, 200, self._segment_response_headers({}, seg_url, body_len))

        try:
            session = self._session_for_url(seg_url)
            self.handshake_manager.handshake_stream_session(session, seg_url)
            self._persist_camera_cookies(session, seg_url)
            resp = self._fetch_segment_upstream(session, seg_url, request_headers)
            if resp.status_code == 403:
                self._invalidate_camera(session, seg_url)
                self.handshake_manager.handshake_stream_session(session, seg_url)
                self._persist_camera_cookies(session, seg_url)
                resp = self._fetch_segment_upstream(session, seg_url, request_headers)

            if resp.status_code in {200, 206, 304, 403, 404, 416}:
                body = b"" if resp.status_code == 304 else resp.content
                headers = self._segment_response_headers(getattr(resp, "headers", {}), seg_url, len(body) if resp.status_code != 304 else None)
                if resp.status_code == 200:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    tmp = cache_file.with_name(f"{cache_file.name}.{os.getpid()}.{time.time_ns()}.tmp")
                    with open(tmp, "wb") as handle:
                        handle.write(body)
                    os.replace(tmp, cache_file)
                    self.segment_cache.cleanup()
                    if self.logger:
                        self.logger.debug(f"CACHE MISS: {seg_url.split('/')[-1]} ({len(body)} bytes)")
                return ProxyPayload(body, resp.status_code, headers)

            resp.raise_for_status()
            body = resp.content
            return ProxyPayload(body, resp.status_code, self._segment_response_headers(getattr(resp, "headers", {}), seg_url, len(body)))
        except Exception as exc:
            if self.logger:
                self.logger.error(f"proxy_segment fetch error: {exc}")
            return ProxyPayload(b"", 502, {"Access-Control-Allow-Origin": "*"})









