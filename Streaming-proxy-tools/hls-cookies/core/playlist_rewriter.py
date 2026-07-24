"""HLS playlist URL rewriting."""

from __future__ import annotations

import re
import urllib.parse

URI_ATTRIBUTE_TAGS = (
    "#EXT-X-KEY",
    "#EXT-X-MAP",
    "#EXT-X-MEDIA",
    "#EXT-X-I-FRAME-STREAM-INF",
)
_URI_ATTR_RE = re.compile(r'URI="([^"]+)"')


def make_absolute_url(base_url: str, line: str) -> str:
    if line.startswith("http://") or line.startswith("https://"):
        return line
    return urllib.parse.urljoin(base_url, line)


def _proxy_url(abs_url: str, playlist: bool) -> str:
    endpoint = "/proxy/playlist" if playlist else "/proxy/segment"
    return f"{endpoint}?url={urllib.parse.quote(abs_url, safe='')}"


def _is_playlist_uri(uri: str) -> bool:
    parsed = urllib.parse.urlparse(uri)
    return parsed.path.lower().endswith(".m3u8")


def _rewrite_uri_attribute(line: str, base_url: str) -> str:
    def replace(match: re.Match) -> str:
        original = match.group(1)
        abs_url = make_absolute_url(base_url, original)
        return f'URI="{_proxy_url(abs_url, _is_playlist_uri(abs_url))}"'

    return _URI_ATTR_RE.sub(replace, line)


def rewrite_playlist(content: str, base_url: str) -> str:
    lines = content.splitlines()
    rewritten: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            rewritten.append(line)
            continue

        if stripped.startswith("#"):
            if any(stripped.startswith(tag) for tag in URI_ATTRIBUTE_TAGS):
                rewritten.append(_rewrite_uri_attribute(line, base_url))
            else:
                rewritten.append(line)
            continue

        abs_url = make_absolute_url(base_url, stripped)
        rewritten.append(_proxy_url(abs_url, _is_playlist_uri(abs_url)))

    return "\n".join(rewritten) + "\n"