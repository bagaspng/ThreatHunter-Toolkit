"""
General utilities: HTTP fetching, JSON persistence, logging.

No parsing/extraction logic belongs here.
"""

import json
import logging
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


def download_html(url: str, timeout: int = 10) -> str:
    """Download raw HTML from a target URL."""
    logger.info(f"Downloading HTML from {url}")
    headers = DEFAULT_HEADERS.copy()
    if "lihatcctv.com" in url:
        headers["Referer"] = "https://restabandarlampung.lampung.polri.go.id/"
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def save_json(data: dict, output_path: str) -> None:
    """Persist a dict as pretty-printed JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved output to {path}")