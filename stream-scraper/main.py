"""
Entry point — Full scrape (Milestone 1 + 2 combined).

Flow:
    1. Download portal HTML
    2. Discover all stream channel URLs (bisa 60+ channel)
    3. For each channel: fetch stream page → extract uuid/server → build websocket → verify codec
    4. Save all results to output/cameras.json

Run:
    python main.py
"""

import concurrent.futures
import time
from dataclasses import asdict

from bs4 import BeautifulSoup

import config
from scraper import extractor
from scraper.exceptions import StreamConnectionError, StreamNotFoundError
from scraper.parser import build_websocket_url
from scraper.utils import download_html, logger, save_json
from scraper.verifier import verify_stream


def scrape_channel(index: int, stream_url: str) -> dict | None:
    """Scrape a single channel URL and verify its stream. Returns a camera dict or None on failure."""
    try:
        html = download_html(stream_url)
        soup = BeautifulSoup(html, "html.parser")

        uuid = extractor.extract_uuid(soup)
        server = extractor.extract_server(soup)
        name = extractor.extract_title(soup) or f"Kamera {index + 1}"

        if not uuid or not server:
            logger.warning(f"[{index}] uuid/server tidak ditemukan di {stream_url}")
            return None

        websocket_url = build_websocket_url(server=server, uuid=uuid)

        # Verify stream and get codec
        video_codec = None
        is_active = False
        try:
            result = verify_stream(websocket_url, timeout=8, max_bytes=131_072)
            video_codec = result.video_codec
            is_active = result.is_active
        except StreamConnectionError as e:
            logger.warning(f"[{index}] Verifikasi gagal untuk {name}: {e}")

        camera = {
            "id": f"cam-{index + 1:02d}",
            "index": index,
            "name": name,
            "stream_url": stream_url,
            "uuid": uuid,
            "server": server,
            "websocket": websocket_url,
            "video_codec": video_codec,
            "is_active": is_active,
        }
        status = "✅ AKTIF" if is_active else "❌ TIDAK AKTIF"
        logger.info(f"[{index}] {status} — {name} | codec: {video_codec}")
        return camera

    except Exception as e:
        logger.error(f"[{index}] Gagal scrape {stream_url}: {e}")
        return None


def run(target_url: str = config.TARGET_URL) -> None:
    logger.info(f"Memulai full scrape dari: {target_url}")
    start = time.time()

    portal_html = download_html(target_url, timeout=config.TIMEOUT)
    portal_soup = BeautifulSoup(portal_html, "html.parser")
    stream_urls = extractor.extract_stream_urls(portal_soup)

    if not stream_urls:
        logger.error("Tidak ada URL stream yang ditemukan di portal. Periksa extractor.")
        return

    logger.info(f"Ditemukan {len(stream_urls)} channel. Memulai scraping paralel...")

    cameras = []
    # Use ThreadPoolExecutor for parallel scraping; limit concurrency to avoid rate-limiting
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(scrape_channel, i, url): i
            for i, url in enumerate(stream_urls)
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                cameras.append(result)

    # Sort by original index so output order matches portal order
    cameras.sort(key=lambda c: c["index"])

    active_count = sum(1 for c in cameras if c["is_active"])
    elapsed = time.time() - start

    save_json({"cameras": cameras}, config.CAMERAS_OUTPUT_FILE)
    logger.info(
        f"Selesai dalam {elapsed:.1f}s. "
        f"{len(cameras)} channel ditemukan, {active_count} aktif. "
        f"Hasil disimpan ke {config.CAMERAS_OUTPUT_FILE}"
    )


if __name__ == "__main__":
    run()