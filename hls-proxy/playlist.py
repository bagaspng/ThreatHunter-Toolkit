"""
playlist.py — Fetches and rewrites the HLS playlist from the CDN.

Rewrites all absolute URLs inside the .m3u8 so the browser routes
segment/key/map requests through our local proxy instead of hitting
the CDN directly (which would fail due to missing Referer).
"""

import re
import time
import logging
import urllib.parse
from flask import Response
from curl_cffi import requests
from config import REFERER, STREAM_URL

logger = logging.getLogger("hls_proxy")


def rewrite_playlist(content: str) -> str:
    """
    Parses the raw .m3u8 text and rewrites internal URLs:
      - #EXT-X-KEY URI  → /key?url=<encoded>
      - #EXT-X-MAP URI  → /segment?url=<encoded>
      - Segment lines   → /segment?url=<encoded>
    """
    lines = content.splitlines()
    result = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            result.append(line)
            continue

        # 1. Rewrite decryption key URI
        if stripped.startswith("#EXT-X-KEY:"):
            match = re.search(r'URI="([^"]+)"', stripped)
            if match:
                original = match.group(1)
                local = f'/key?url={urllib.parse.quote(original, safe="")}'
                result.append(stripped.replace(f'URI="{original}"', f'URI="{local}"'))
            else:
                result.append(line)

        # 2. Rewrite initialization map URI
        elif stripped.startswith("#EXT-X-MAP:"):
            match = re.search(r'URI="([^"]+)"', stripped)
            if match:
                original = match.group(1)
                local = f'/segment?url={urllib.parse.quote(original, safe="")}'
                result.append(stripped.replace(f'URI="{original}"', f'URI="{local}"'))
            else:
                result.append(line)

        # 3. Rewrite segment URLs (non-comment lines starting with http)
        elif not stripped.startswith("#"):
            if stripped.startswith(("http://", "https://")):
                local = f'/segment?url={urllib.parse.quote(stripped, safe="")}'
                result.append(local)
            else:
                result.append(line)
        else:
            result.append(line)

    return "\n".join(result)


def get_playlist_response() -> Response:
    """
    Fetches the remote .m3u8 playlist via curl_cffi, rewrites URLs,
    and returns a Flask Response with the correct MIME type.
    """
    start_time = time.time()

    try:
        response = requests.get(
            STREAM_URL,
            headers={"Referer": REFERER},
            impersonate="chrome",
        )

        duration = time.time() - start_time
        logger.info(
            f"PLAYLIST {response.status_code} | {duration:.2f}s | {STREAM_URL.split('/')[-1]}"
        )

        if response.status_code != 200:
            logger.warning(f"PLAYLIST CDN returned {response.status_code}")
            return Response(
                f"CDN error {response.status_code}: {response.text[:200]}",
                status=response.status_code,
            )

        rewritten = rewrite_playlist(response.text)

        return Response(
            rewritten,
            status=200,
            mimetype="application/vnd.apple.mpegurl",
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"PLAYLIST FAIL | {duration:.2f}s | {e}")
        return Response(f"Playlist error: {e}", status=502)
