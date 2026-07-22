"""
Extractor module.

Responsibility: pull RAW data out of HTML. Does not build websocket URLs,
does not produce JSON — that's parser.py's job.

Extraction priority (per AGENT.md):
    1. <input id="uuid">
    2. <input id="server">
    3. data-uuid attribute
    4. data-server attribute
    5. inline <script> content (including `locations` JS array for portal pages)
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

# Matches entries inside the JavaScript `locations` array on the portal page.
# Actual field names: link_cctv and nama_cctv
_LOCATIONS_URL_PATTERN = re.compile(
    r'"link_cctv"\s*:\s*"(https?://stream\.lihatcctv\.com/stream/[0-9a-fA-F\-]+)"'
)


def _search_inline_scripts(soup: BeautifulSoup, patterns: list[str]) -> Optional[str]:
    script_text = "\n".join(tag.string for tag in soup.find_all("script") if tag.string)
    for pattern in patterns:
        match = re.search(pattern, script_text)
        if match:
            return match.group(1)
    return None


def _get_all_script_text(soup: BeautifulSoup) -> str:
    return "\n".join(tag.string for tag in soup.find_all("script") if tag.string)


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
    """Extract all stream page URLs from the portal page.

    Strategy (in priority order):
    1. Parse the inline JavaScript `locations` array — contains ALL cameras
       including those hidden behind "Show More" pagination.
    2. Fallback: collect <a class="cctv-link"> anchor hrefs from visible HTML.
    3. Fallback: iframe src.
    """
    # ── Strategy 1: locations[] JS array (most complete, all cameras) ──
    script_text = _get_all_script_text(soup)
    locations_urls = _LOCATIONS_URL_PATTERN.findall(script_text)
    if locations_urls:
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for u in locations_urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    # ── Strategy 2: visible <a class="cctv-link"> links in HTML ──
    urls: list[str] = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if href:
            is_cctv_link = "cctv-link" in (a.get("class") or [])
            is_stream_pattern = "stream.lihatcctv.com/stream/" in href
            if (is_cctv_link or is_stream_pattern) and href not in urls:
                urls.append(href)

    # ── Strategy 3: iframe src ──
    iframe_src = extract_iframe(soup)
    if iframe_src and iframe_src not in urls:
        urls.append(iframe_src)

    return urls


def extract_camera_names_from_locations(soup: BeautifulSoup) -> dict[str, str]:
    """Extract a mapping of {stream_url: name} from the JS `locations` array.

    The locations array contains `name` fields (e.g. location descriptions)
    that are more descriptive than page titles on individual stream pages.
    """
    script_text = _get_all_script_text(soup)

    # Match full location objects:  { "name": "...", ..., "url": "..." }
    # Match full location objects using actual field names: nama_cctv and link_cctv
    entry_pattern = re.compile(
        r'\{[^{}]*?"nama_cctv"\s*:\s*"([^"]+)"[^{}]*?"link_cctv"\s*:\s*"(https?://stream\.lihatcctv\.com/stream/[^"]+)"[^{}]*?\}'
        r'|\{[^{}]*?"link_cctv"\s*:\s*"(https?://stream\.lihatcctv\.com/stream/[^"]+)"[^{}]*?"nama_cctv"\s*:\s*"([^"]+)"[^{}]*?\}',
        re.DOTALL,
    )
    name_map: dict[str, str] = {}
    for match in entry_pattern.finditer(script_text):
        if match.group(1):  # nama_cctv before link_cctv
            name, url = match.group(1), match.group(2)
        else:  # link_cctv before nama_cctv
            name, url = match.group(4), match.group(3)
        if url not in name_map:
            name_map[url] = name

    return name_map


def extract_csrf_token(soup: BeautifulSoup) -> Optional[str]:
    """Extract the CSRF token used for AJAX pagination requests."""
    token_input = soup.find("input", {"name": "csrf_token"})
    if token_input and token_input.get("value"):
        return token_input["value"]
    return None
