"""
Entry point — Full scrape (Milestone 1 + 2 combined).

Flow:
    1. Download portal HTML
    2. Discover ALL stream channel URLs:
       - Primary:  parse JavaScript `locations[]` array (contains all ~144 cameras)
       - Fallback: collect visible <a class="cctv-link"> links, then paginate
                   via POST ajax_load_more.php until exhausted
    3. For each channel (parallel): fetch stream page → extract uuid/server
       → build websocket → verify codec
    4. Save all results to output/cameras.json

Run:
    python main.py
"""

import concurrent.futures
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config
from scraper import extractor
from scraper.exceptions import StreamConnectionError
from scraper.parser import build_websocket_url
from scraper.utils import download_html, logger, save_json
from scraper.verifier import verify_stream

_AJAX_URL = "https://restabandarlampung.lampung.polri.go.id/identik_layout_config/ajax_load_more.php"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://restabandarlampung.lampung.polri.go.id/cctv",
}


def _collect_urls_via_ajax(initial_soup: BeautifulSoup) -> list[str]:
    """Paginate through AJAX load-more until no more cameras are returned."""
    # Grab CSRF token from initial page
    csrf_token = extractor.extract_csrf_token(initial_soup)
    if not csrf_token:
        logger.warning("CSRF token tidak ditemukan — AJAX pagination dilewati.")
        return []

    # Initial visible links (from the first page HTML)
    urls = extractor.extract_stream_urls(initial_soup)
    offset = len(urls)  # button id = current offset

    logger.info(f"AJAX pagination: {len(urls)} URL awal, memulai dari offset {offset}…")

    while True:
        try:
            response = requests.post(
                _AJAX_URL,
                data={"id": offset, "csrf_token": csrf_token},
                headers=_BROWSER_HEADERS,
                timeout=15,
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"AJAX request gagal pada offset {offset}: {e}")
            break

        chunk_html = response.text.strip()
        if not chunk_html:
            break

        chunk_soup = BeautifulSoup(chunk_html, "html.parser")

        # Parse new camera links from this chunk
        new_urls = []
        for a in chunk_soup.find_all("a"):
            href = a.get("href", "")
            is_cctv_link = "cctv-link" in (a.get("class") or [])
            is_stream = "stream.lihatcctv.com/stream/" in href
            if (is_cctv_link or is_stream) and href not in urls:
                new_urls.append(href)
                urls.append(href)

        if not new_urls:
            break  # nothing new — stop paginating

        logger.info(f"  +{len(new_urls)} kamera (offset {offset} → {offset + len(new_urls)})")

        # Find the next "show more" button id for the next page
        next_btn = chunk_soup.find(class_="show_more")
        if not next_btn or not next_btn.get("id"):
            break  # no next page
        try:
            offset = int(next_btn["id"])
        except ValueError:
            break

    return urls


def scrape_channel(index: int, stream_url: str, name_hint: Optional[str] = None) -> dict | None:
    """Scrape a single channel URL and verify its stream. Returns a camera dict or None on failure."""
    try:
        html = download_html(stream_url)
        soup = BeautifulSoup(html, "html.parser")

        uuid = extractor.extract_uuid(soup)
        server = extractor.extract_server(soup)
        # Prefer the name from the locations[] array (more descriptive)
        name = name_hint or extractor.extract_title(soup) or f"Kamera {index + 1}"

        if not uuid or not server:
            logger.warning(f"[{index + 1}] uuid/server tidak ditemukan di {stream_url}")
            return None

        websocket_url = build_websocket_url(server=server, uuid=uuid)

        video_codec: Optional[str] = None
        is_active = False
        try:
            result = verify_stream(websocket_url, timeout=8, max_bytes=131_072)
            video_codec = result.video_codec
            is_active = result.is_active
        except StreamConnectionError as e:
            logger.warning(f"[{index + 1}] Verifikasi gagal untuk {name}: {e}")

        status = "✅ AKTIF" if is_active else "❌ TIDAK AKTIF"
        logger.info(f"[{index + 1:>3}/{'{total}'}] {status} — {name} | codec: {video_codec}")

        return {
            "id": f"cam-{index + 1:03d}",
            "index": index,
            "name": name,
            "stream_url": stream_url,
            "uuid": uuid,
            "server": server,
            "websocket": websocket_url,
            "video_codec": video_codec,
            "is_active": is_active,
        }

    except Exception as e:
        logger.error(f"[{index + 1}] Gagal scrape {stream_url}: {e}")
        return None


def run(target_url: str = config.TARGET_URL) -> None:
    logger.info(f"Memulai full scrape dari: {target_url}")
    start = time.time()

    portal_html = download_html(target_url, timeout=config.TIMEOUT)
    portal_soup = BeautifulSoup(portal_html, "html.parser")

    # ── Step 1: collect camera names from locations[] array ──
    name_map = extractor.extract_camera_names_from_locations(portal_soup)
    logger.info(f"Nama kamera ditemukan di locations[]: {len(name_map)}")

    # ── Step 2: collect ALL stream URLs ──
    stream_urls = extractor.extract_stream_urls(portal_soup)

    if stream_urls:
        # locations[] array found — all cameras already in stream_urls
        logger.info(f"Ditemukan {len(stream_urls)} channel dari locations[] JS array.")
    else:
        # Fallback: visible links + AJAX pagination
        logger.info("locations[] tidak ditemukan — menggunakan AJAX pagination sebagai fallback.")
        stream_urls = _collect_urls_via_ajax(portal_soup)
        logger.info(f"Total setelah pagination: {len(stream_urls)} channel.")

    if not stream_urls:
        logger.error("Tidak ada URL stream yang ditemukan. Periksa extractor atau koneksi.")
        return

    total = len(stream_urls)

    # ── Step 3: scrape each channel in parallel ──
    cameras: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                scrape_channel,
                i,
                url,
                name_map.get(url),
            ): i
            for i, url in enumerate(stream_urls)
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                # Patch total into log string — already printed, but stored correctly
                result["id"] = f"cam-{result['index'] + 1:03d}"
                cameras.append(result)

    cameras.sort(key=lambda c: c["index"])

    active_count = sum(1 for c in cameras if c["is_active"])
    elapsed = time.time() - start

    save_json({"cameras": cameras}, config.CAMERAS_OUTPUT_FILE)
    logger.info(
        f"✅ Selesai dalam {elapsed:.1f}s — "
        f"{len(cameras)}/{total} channel berhasil di-scrape, "
        f"{active_count} aktif. "
        f"Tersimpan ke {config.CAMERAS_OUTPUT_FILE}"
    )


if __name__ == "__main__":
    run()