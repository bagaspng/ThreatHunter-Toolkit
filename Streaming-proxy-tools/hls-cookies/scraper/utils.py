"""
General utilities: HTTP fetching, cookie loading, JSON persistence, logging.
"""

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger("stream_scraper")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.stream = open(
        _handler.stream.fileno(),
        mode="w",
        encoding="utf-8",
        errors="replace",
        closefd=False,
        buffering=1,
    )
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def download_html(url: str, timeout: int = 10, retries: int = 3) -> str:
    """Download raw HTML from a target URL with retry on rate-limit errors."""
    logger.info(f"Downloading HTML from {url}")
    headers = DEFAULT_HEADERS.copy()
    if "lihatcctv.com" in url:
        headers["Referer"] = "https://restabandarlampung.lampung.polri.go.id/"
    for attempt in range(retries):
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 429:
            wait = 5 * (attempt + 1)
            logger.warning(f"429 Too Many Requests â€” menunggu {wait}s sebelum retry... ({url})")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.text
    raise Exception(f"Gagal download setelah {retries} percobaan: {url}")


def load_cookies_from_file(path: str) -> list[dict]:
    """
    Muat cookie dari file JSON.

    Format yang didukung:
      - Array langsung: [{...}, ...]
      - Dict dengan key 'cookies': {"cookies": [{...}, ...]}
      - Dict dengan key 'url' + 'cookies': {"url": "...", "cookies": [{...}, ...]}

    Return list cookie yang sudah dinormalisasi, atau [] jika file tidak ada / error.
    """
    p = Path(path)
    if not p.exists():
        return []

    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Gagal membaca {p.name}: {e}")
        return []

    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        raw_list = data.get("cookies", [])
    else:
        return []

    normalized = []
    for ck in raw_list:
        if not ck.get("name") or ck.get("value") is None:
            continue
        normalized.append({
            "name":   ck["name"],
            "value":  ck["value"],
            "domain": ck.get("domain", ""),
            "path":   ck.get("path", "/"),
            "secure": ck.get("secure", False),
        })

    logger.info(f"Dimuat {len(normalized)} cookie dari {p.name}")
    return normalized


def build_session(cookies: list[dict]) -> requests.Session:
    """Buat requests.Session dengan cookie yang sudah dinormalisasi."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    for ck in cookies:
        session.cookies.set(
            ck["name"],
            ck["value"],
            domain=ck.get("domain", ""),
            path=ck.get("path", "/"),
        )
    return session


def fetch_with_session(
    session: requests.Session,
    url: str,
    referer: str = "",
    timeout: int = 10,
    allow_redirects: bool = True,
    extra_headers: dict[str, str] | None = None,
) -> requests.Response:
    """GET dengan session + referer header."""
    headers = dict(extra_headers or {})
    if referer:
        headers["Referer"] = referer
    return session.get(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)


def save_json(data: dict, output_path: str) -> None:
    """Persist a dict as pretty-printed JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f"Tersimpan ke {path}")


