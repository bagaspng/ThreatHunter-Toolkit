"""
proxy.py — Reverse proxy engine for HLS segments and keys.

Downloads the full resource from the CDN into memory, then returns it
as a complete Flask Response. This avoids the single-threaded Flask dev
server from blocking on streaming generators — which is the root cause
of the seek/skip buffering bug.

Segments are typically 0.5–3 MB each, so holding them in memory is fine.
"""

import time
import logging
from flask import Response
from curl_cffi import requests
from config import REFERER

logger = logging.getLogger("hls_proxy")

# Headers to forward from the CDN response to the client browser
FORWARD_HEADERS = [
    "content-type",
    "content-length",
    "accept-ranges",
    "content-range",
    "etag",
    "cache-control",
]


def proxy_request(url: str, client_headers) -> Response:
    """
    Fetches a resource from the CDN and returns the complete content.
    Forwards Range headers from the client to support seeking.
    """
    start_time = time.time()

    headers = {"Referer": REFERER}

    # Forward the Range header if present (enables video seeking)
    range_header = client_headers.get("Range")
    if range_header:
        headers["Range"] = range_header

    try:
        # Full download (no streaming) — prevents thread-blocking on seek
        response = requests.get(
            url,
            headers=headers,
            impersonate="chrome",
        )

        duration = time.time() - start_time
        content_length = len(response.content)

        logger.info(
            f"PROXY  {response.status_code} | {content_length:>8} bytes | "
            f"{duration:.2f}s | Range: {range_header or 'full'} | {url.split('/')[-1]}"
        )

        # Build response headers to forward back to the browser
        resp_headers = {}
        for key in FORWARD_HEADERS:
            val = response.headers.get(key)
            if val:
                resp_headers[key] = val

        # Always advertise range support
        resp_headers.setdefault("accept-ranges", "bytes")

        return Response(
            response.content,
            status=response.status_code,
            headers=resp_headers,
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"PROXY  FAIL | {duration:.2f}s | {e} | {url}")
        return Response(f"Proxy error: {e}", status=502)
