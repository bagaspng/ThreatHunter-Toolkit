"""Requests session construction from cookie snapshots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def build_session_from_snapshot(
    base_cookies: Iterable[Mapping] | None = None,
    camera_cookies: Iterable[Mapping] | None = None,
    default_headers: Mapping[str, str] | None = None,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(default_headers or DEFAULT_HEADERS)
    for cookie in list(base_cookies or []) + list(camera_cookies or []):
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        session.cookies.set(
            name,
            value,
            domain=cookie.get("domain", ""),
            path=cookie.get("path", "/"),
        )
    return session


def fetch_with_session(
    session: requests.Session,
    url: str,
    referer: str = "",
    timeout: int = 10,
    allow_redirects: bool = True,
    extra_headers: Mapping[str, str] | None = None,
) -> requests.Response:
    headers = dict(extra_headers or {})
    if referer:
        headers["Referer"] = referer
    return session.get(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)

