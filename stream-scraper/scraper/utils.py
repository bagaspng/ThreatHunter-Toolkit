"""
General utilities: HTTP fetching, JSON persistence, logging.

No parsing/extraction logic belongs here.
"""

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger("stream_scraper")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

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
            logger.warning(f"429 Too Many Requests — menunggu {wait}s sebelum retry... ({url})")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.text
    raise Exception(f"Gagal download setelah {retries} percobaan: {url}")


def save_json(data: dict, output_path: str) -> None:
    """Persist a dict as pretty-printed JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved output to {path}")