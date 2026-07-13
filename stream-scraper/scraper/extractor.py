"""
Extractor module.

Responsibility: pull RAW data out of HTML. Does not build websocket URLs,
does not produce JSON — that's parser.py's job.

Extraction priority (per AGENT.md):
    1. <input id="uuid">
    2. <input id="server">
    3. data-uuid attribute
    4. data-server attribute
    5. inline <script> content
    6. regex (last resort)
"""

import re
from typing import Optional

from bs4 import BeautifulSoup

# Regex patterns used only as a last resort, when nothing else matched.
_UUID_REGEX = [
    r'uuid["\']?\s*[:=]\s*["\']([0-9a-fA-F-]{8,36})["\']',
    r'/stream/([0-9a-fA-F-]{8,36})/',
]
_SERVER_REGEX = [
    r'server["\']?\s*[:=]\s*["\']([a-zA-Z0-9.\-]+)["\']',
    r'wss?://([a-zA-Z0-9.\-]+)',
]


def _search_inline_scripts(soup: BeautifulSoup, patterns: list[str]) -> Optional[str]:
    script_text = "\n".join(tag.string for tag in soup.find_all("script") if tag.string)
    for pattern in patterns:
        match = re.search(pattern, script_text)
        if match:
            return match.group(1)
    return None


def extract_uuid(soup: BeautifulSoup) -> Optional[str]:
    """Extract the uuid value, following the priority order."""
    input_tag = soup.find("input", id="uuid")
    if input_tag and input_tag.get("value"):
        return input_tag["value"]

    data_tag = soup.find(attrs={"data-uuid": True})
    if data_tag:
        return data_tag["data-uuid"]

    return _search_inline_scripts(soup, _UUID_REGEX)


def extract_server(soup: BeautifulSoup) -> Optional[str]:
    """Extract the server value, following the priority order."""
    input_tag = soup.find("input", id="server")
    if input_tag and input_tag.get("value"):
        return input_tag["value"]

    data_tag = soup.find(attrs={"data-server": True})
    if data_tag:
        return data_tag["data-server"]

    return _search_inline_scripts(soup, _SERVER_REGEX)


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract the page title, useful for logging/identification only."""
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def extract_iframe(soup: BeautifulSoup) -> Optional[str]:
    """Extract an iframe src if the player is embedded via iframe."""
    iframe = soup.find("iframe")
    if iframe and iframe.get("src"):
        return iframe["src"]
    return None


def extract_stream_urls(soup: BeautifulSoup) -> list[str]:
    """Extract all stream page URLs (from links or iframe srcs)."""
    urls = []
    # 1. Look for anchor links
    for a in soup.find_all("a"):
        href = a.get("href")
        if href:
            # check class cctv-link or if URL matches a stream pattern
            is_cctv_link = "cctv-link" in (a.get("class") or [])
            is_stream_pattern = "stream.lihatcctv.com/stream/" in href or "/stream/" in href
            if (is_cctv_link or is_stream_pattern) and href not in urls:
                urls.append(href)
    # 2. Look for iframe src
    iframe_src = extract_iframe(soup)
    if iframe_src and iframe_src not in urls:
        urls.append(iframe_src)
    return urls
