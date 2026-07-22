"""
main.py — Camera Prober

Sesuai AGENT.md §2.3:
  Probe sequential camera URLs (cctv_1, cctv_2, …) dan simpan yang aktif
  ke output/cameras.json.

Penggunaan:
  python main.py                  # probe via API backend (direkomendasikan)
  python main.py --probe 50       # probe sequential cctv_1..cctv_50 via HEAD request
  python main.py --probe 50 --workers 10
"""

import argparse
import concurrent.futures
import json
import sys
import urllib.parse
from pathlib import Path

import requests

import config
from scraper import build_session, load_cookies_from_file, logger, save_json

# ── Streaming server base ──────────────────────────────────────────────────────
_STREAM_BASE   = "https://stream-newseribuwajah.bandarlampungkota.go.id"
_CCTV_API_URL  = "https://api-newseribuwajah.bandarlampungkota.go.id/cctvs"
_CCTV_API_KEY  = "ParkirIlegalDetectKey2026"


# ─────────────────────────────────────────────────────────────────────────────
# Mode 1: Fetch dari API backend (lengkap, akurat)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_from_api() -> list[dict]:
    """Ambil semua kamera dari API backend."""
    logger.info(f"Fetching camera list dari API: {_CCTV_API_URL}")
    resp = requests.get(
        _CCTV_API_URL,
        headers={
            "x-api-key":  _CCTV_API_KEY,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer":    config.STREAM_REFERER,
        },
        timeout=config.TIMEOUT,
    )
    resp.raise_for_status()
    raw = resp.json()

    cameras = []
    for item in raw:
        if item.get("isHidden"):
            continue
        m3u8_url = item.get("streamUrl") or ""
        cameras.append({
            "id":        item["id"],
            "name":      item.get("name", f"CCTV {item['id']}"),
            "category":  item.get("category", ""),
            "address":   item.get("address", ""),
            "status":    item.get("status", "unknown"),
            "kelurahan": (item.get("kelurahan") or {}).get("name", ""),
            "kecamatan": ((item.get("kelurahan") or {}).get("kecamatan") or {}).get("name", ""),
            "m3u8_url":  m3u8_url,
            "proxy_url": f"/proxy/playlist?url={urllib.parse.quote(m3u8_url, safe='')}" if m3u8_url else "",
            "is_active": item.get("status") in ("online", "aktif"),
        })

    logger.info(f"API mengembalikan {len(cameras)} kamera (dari {len(raw)} total, isHidden difilter).")
    return cameras


# ─────────────────────────────────────────────────────────────────────────────
# Mode 2: Sequential probe via HEAD request
# ─────────────────────────────────────────────────────────────────────────────

def _probe_one(session: requests.Session, n: int) -> dict | None:
    """
    Probe satu URL kamera dengan HEAD request.
    Return dict jika aktif (2xx/3xx), None jika 401/403/404.
    """
    m3u8_url = f"{_STREAM_BASE}/cctv_{n}/index.m3u8"
    try:
        resp = session.head(
            m3u8_url,
            headers={"Referer": config.STREAM_REFERER},
            timeout=config.TIMEOUT,
            allow_redirects=True,
        )
        status = resp.status_code
        is_active = status < 400
        logger.info(f"  cctv_{n:>3} → HTTP {status} {'✓' if is_active else '✗'}")
        return {
            "id":        n,
            "name":      f"CCTV {n:03d}",
            "category":  "",
            "address":   "",
            "status":    "online" if is_active else "offline",
            "kelurahan": "",
            "kecamatan": "",
            "m3u8_url":  m3u8_url,
            "proxy_url": f"/proxy/playlist?url={urllib.parse.quote(m3u8_url, safe='')}",
            "is_active": is_active,
            "http_status": status,
        }
    except Exception as e:
        logger.warning(f"  cctv_{n:>3} → ERROR: {e}")
        return None


def probe_sequential(count: int, workers: int = 8) -> list[dict]:
    """Probe cctv_1 sampai cctv_<count> secara paralel."""
    cookies = load_cookies_from_file(config.COOKIES_CACHE_FILE)
    if not cookies:
        cookies = load_cookies_from_file(config.COOKIES_MANUAL_FILE)
    session = build_session(cookies)

    logger.info(f"Probing cctv_1 .. cctv_{count} dengan {workers} workers …")
    cameras = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_probe_one, session, n): n for n in range(1, count + 1)}
        for fut in concurrent.futures.as_completed(futures):
            result = fut.result()
            if result:
                cameras.append(result)

    cameras.sort(key=lambda c: c["id"])
    active = sum(1 for c in cameras if c["is_active"])
    logger.info(f"Probe selesai: {active} aktif dari {count} yang dicek.")
    return cameras


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Camera prober — temukan CCTV aktif dan simpan ke cameras.json"
    )
    parser.add_argument(
        "--probe", type=int, metavar="N",
        help="Probe sequential cctv_1..cctv_N via HEAD request. "
             "Tanpa flag ini, fetch dari API backend (lebih lengkap).",
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="Jumlah thread paralel untuk mode --probe (default: 8).",
    )
    args = parser.parse_args()

    Path("output").mkdir(exist_ok=True)

    if args.probe:
        cameras = probe_sequential(args.probe, workers=args.workers)
    else:
        cameras = fetch_from_api()

    data = {"total": len(cameras), "cameras": cameras}
    save_json(data, config.CAMERAS_OUTPUT_FILE)
    logger.info(f"Disimpan {len(cameras)} kamera ke {config.CAMERAS_OUTPUT_FILE}")

    # Ringkasan ke stdout
    active = sum(1 for c in cameras if c["is_active"])
    print(f"\nTotal: {len(cameras)} kamera | Aktif: {active} | Offline: {len(cameras) - active}")
    print(f"Output: {config.CAMERAS_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
