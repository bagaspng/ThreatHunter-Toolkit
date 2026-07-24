"""
app.py â€” Flask HLS Proxy Server

Alur kerja:
    1. /api/refresh-cookies  -> Panggil Selenium refresher internal,
                               simpan cookie ke output/cookies_cache.json
    2. /api/cameras          â†’ Baca cameras.json, kembalikan daftar kamera
    3. /proxy/playlist       â†’ Fetch .m3u8 dari CDN dengan cookie, rewrite URL
                               segmen agar mengarah ke /proxy/segment lokal
    4. /proxy/segment        â†’ Fetch segmen .ts dari CDN dengan cookie,
                               teruskan ke browser (mendukung Range header)
    5. /player               â†’ Halaman UI HLS.js

Bypass SOP (Same-Origin Policy):
    Browser tidak dapat mengirim Cookie cross-origin ke subdomain streaming.
    Proxy ini menyelesaikan masalah tersebut dengan menjadi perantara:
    - Browser hanya berbicara dengan proxy lokal (http://localhost:5000)
    - Proxy menyimpan cookie sesi dan menyertakannya pada setiap request
      ke server CDN eksternal â€” transparan bagi browser.
"""

import json
import threading
import urllib.parse
from pathlib import Path

import requests as req
from flask import Flask, Response, jsonify, render_template, request

import config
from core.camera_identity import (
    CameraIdentity,
    extract_camera_identity as core_extract_camera_identity,
    normalize_camera_path as core_normalize_camera_path,
)
from core.cookie_store import JsonCookieStore
from core.handshake import (
    CAMERA_COOKIE_NAMES as CORE_CAMERA_COOKIE_NAMES,
    BASE_COOKIE_NAMES as CORE_BASE_COOKIE_NAMES,
    HandshakeManager,
    camera_cookie_names as core_camera_cookie_names,
    cookie_domain_matches as core_cookie_domain_matches,
    cookie_path_matches as core_cookie_path_matches,
    has_base_cookies as core_has_base_cookies,
    has_camera_cookies as core_has_camera_cookies,
)
from core.hls_client import HlsProxyService
from core.playlist_rewriter import (
    make_absolute_url as core_make_absolute_url,
    rewrite_playlist as core_rewrite_playlist,
)
from core.session_factory import build_session_from_snapshot
from core.segment_cache import (
    cache_path_for_url as core_cache_path_for_url,
    detect_content_type as core_detect_content_type,
    parse_range as core_parse_range,
)
from upstream_auth.selenium_refresher import (
    BaseCookieTimeout,
    CookieRefreshError,
    InvalidRefreshTarget,
    refresh_base_cookies,
)
from scraper import (
    fetch_with_session,
    logger,
    save_json,
)

_CCTV_API_URL = "https://api-newseribuwajah.bandarlampungkota.go.id/cctvs"
_CCTV_API_KEY = "ParkirIlegalDetectKey2026"

app = Flask(__name__)
_cookie_store = JsonCookieStore(config.COOKIES_CACHE_FILE, config.COOKIES_MANUAL_FILE)
_handshake_manager = HandshakeManager(config.STREAM_REFERER, logger)

# â”€â”€ Session & Cookie State (in-memory, refreshed via /api/refresh-cookies) â”€â”€â”€â”€
_session_lock = threading.Lock()
_proxy_session: req.Session | None = None
_loaded_cookies: list[dict] = []

# â”€â”€ Handshake cache (per kamera, per session) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_handshaked_paths = _handshake_manager.handshaked_paths
_handshake_lock = _handshake_manager._handshake_lock
_handshake_locks = _handshake_manager._camera_locks
_handshake_locks_lock = _handshake_manager._camera_locks_lock

# Refresh cookie service state. Concurrent callers for the same target share the
# in-flight refresh so only one Selenium driver is opened at a time.
_refresh_condition = threading.Condition(threading.Lock())
_refresh_in_progress = False
_last_refresh_target: str | None = None
_last_refresh_cookies: list[dict] | None = None
_last_refresh_error: Exception | None = None

_BASE_COOKIE_NAMES = CORE_BASE_COOKIE_NAMES
_CAMERA_COOKIE_NAMES = CORE_CAMERA_COOKIE_NAMES


def _perform_cookie_refresh(target_url: str) -> list[dict]:
    """Refresh base cookies through the internal Selenium refresher."""
    cookies = refresh_base_cookies(target_url)
    if not cookies:
        raise ValueError(f"Tidak ada cookie yang diterima dari target {target_url}")
    _cookie_store.save_base_cookies(cookies)
    _rebuild_session(cookies)
    return cookies

def _refresh_cookies_from_service(target_url: str) -> list[dict]:
    """Refresh cookie dasar dengan satu proses Selenium aktif per target."""
    global _refresh_in_progress, _last_refresh_target, _last_refresh_cookies, _last_refresh_error

    with _refresh_condition:
        if _refresh_in_progress:
            while _refresh_in_progress:
                _refresh_condition.wait()
            if _last_refresh_target == target_url:
                if _last_refresh_error is not None:
                    raise _last_refresh_error
                if _last_refresh_cookies is not None:
                    return list(_last_refresh_cookies)

        _refresh_in_progress = True

    try:
        cookies = _perform_cookie_refresh(target_url)
    except Exception as exc:
        with _refresh_condition:
            _last_refresh_target = target_url
            _last_refresh_cookies = None
            _last_refresh_error = exc
            _refresh_in_progress = False
            _refresh_condition.notify_all()
        raise

    with _refresh_condition:
        _last_refresh_target = target_url
        _last_refresh_cookies = list(cookies)
        _last_refresh_error = None
        _refresh_in_progress = False
        _refresh_condition.notify_all()
    return cookies

def _get_session() -> req.Session:
    """
    Kembalikan session aktif.

    Urutan sumber cookie:
    1. In-memory session (sudah di-rebuild via /api/refresh-cookies)
    2. output/cookies_cache.json  - dari Selenium refresher internal
    3. cookies.json               â€” dari browser export manual
    4. Session kosong (stream kemungkinan akan 403)
    """
    global _proxy_session
    with _session_lock:
        if _proxy_session is None:
            cookies = _cookie_store.load_base_cookies()
            _proxy_session = build_session_from_snapshot(cookies)
            logger.info(
                f"Session dibuat dengan {len(cookies)} cookie "
                f"({'cache' if cookies else 'kosong â€” kemungkinan 403 dari CDN'})"
            )
        return _proxy_session


def _rebuild_session(cookies: list[dict]) -> None:
    """Rebuild session dengan cookie baru (dipanggil setelah refresh)."""
    global _proxy_session, _loaded_cookies
    with _session_lock:
        _loaded_cookies = cookies
        _proxy_session = build_session_from_snapshot(cookies)
    with _handshake_lock:
        _handshaked_paths.clear()
    logger.info(f"Session di-rebuild dengan {len(cookies)} cookie baru.")


# â”€â”€ Cache segmen .ts di disk â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_CACHE_DIR = Path("cache_segments")
_CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(url: str) -> Path:
    return core_cache_path_for_url(url, _CACHE_DIR)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# API ROUTES
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class _HandshakeAdapter:
    def handshake_stream_session(self, session: req.Session, url: str) -> bool:
        return _handshake_stream_session(session, url)

    def invalidate_camera_session(self, session: req.Session, url: str) -> None:
        _invalidate_camera_session(session, url)


def _make_hls_service() -> HlsProxyService:
    return HlsProxyService(
        get_session=_get_session,
        refresh_base_cookies=_refresh_cookies_from_service,
        handshake_manager=_HandshakeAdapter(),
        fetch_with_session=fetch_with_session,
        cache_path_for_url=_cache_path,
        referer=config.STREAM_REFERER,
        timeout=config.TIMEOUT,
        portal_url=config.PORTAL_URL,
        logger=logger,
        allowed_hosts=set(config.ALLOWED_COOKIE_REFRESH_HOSTS),
    )
@app.get("/")
def index():
    return jsonify({
        "service": "HLS Cookie Proxy",
        "endpoints": {
            "GET  /player":                 "Dashboard pemutar HLS",
            "POST /api/refresh-cookies":    "Refresh cookie dasar via Selenium internal",
            "GET  /api/cameras":            "Daftar kamera dari cameras.json",
            "POST /api/scrape":             "Paksa ulang scraping portal",
            "GET  /api/debug-session":      "Tampilkan cookie aktif di session",
            "POST /api/inject-cookies":     "Inject cookie langsung ke session",
            "GET  /proxy/playlist?url=...": "Proxy + rewrite .m3u8",
            "GET  /proxy/segment?url=...":  "Proxy segmen .ts dengan cookie",
        }
    })


@app.get("/player")
def player():
    return render_template("player.html")


@app.post("/api/refresh-cookies")
def refresh_cookies():
    """
    Panggil Selenium refresher internal untuk mendapatkan cookie dasar segar
    dari portal utama, lalu simpan ke cache dan rebuild session.
    """
    try:
        target_url = (request.get_json(silent=True) or {}).get("url") or config.PORTAL_URL
        cookies = _refresh_cookies_from_service(target_url)

        return _deprecated_flask_response(jsonify({
            "status": "ok",
            "cookie_count": len(cookies),
            "cookies": [{"name": c.get("name"), "domain": c.get("domain")} for c in cookies],
        }))

    except InvalidRefreshTarget as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except (BaseCookieTimeout, CookieRefreshError) as e:
        logger.warning(f"refresh_cookies failed: {e}")
        return jsonify({"status": "error", "message": "Refresh cookie dasar belum berhasil."}), 503
    except Exception as e:
        logger.error(f"refresh_cookies error: {e}")
        return jsonify({"status": "error", "message": "Refresh cookie gagal."}), 500


@app.get("/api/cameras")
def cameras_list():
    """
    Kembalikan daftar kamera dari cameras.json.
    Jika file tidak ada, lakukan scraping live dari portal.
    """
    cache_path = Path(config.CAMERAS_OUTPUT_FILE)
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)

    # Scraping live jika cache belum ada
    return _do_scrape()


@app.post("/api/scrape")
def scrape_cameras():
    """Paksa ulang scraping portal dan perbarui cameras.json."""
    return _do_scrape()


def _do_scrape():
    """Fetch semua kamera dari API backend, simpan ke cameras.json."""
    try:
        resp = req.get(
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
                "kelurahan": item.get("kelurahan", {}).get("name", ""),
                "kecamatan": (item.get("kelurahan") or {}).get("kecamatan", {}).get("name", ""),
                "m3u8_url":  m3u8_url,
                "proxy_url": f"/proxy/playlist?url={urllib.parse.quote(m3u8_url, safe='')}" if m3u8_url else "",
                "is_active": item.get("status") in ("online", "aktif"),
            })

        cameras_data = {"total": len(cameras), "cameras": cameras}
        save_json(cameras_data, config.CAMERAS_OUTPUT_FILE)
        logger.info(f"Scraped {len(cameras)} kamera dari API.")
        return jsonify(cameras_data)

    except Exception as e:
        logger.error(f"scrape error: {e}")
        return jsonify({"total": 0, "cameras": [], "error": str(e)}), 500


@app.get("/api/debug-session")
def debug_session():
    """Tampilkan semua cookie aktif di proxy session."""
    session = _get_session()
    cookies_in_session = [
        {
            "name":   c.name,
            "domain": c.domain,
            "path":   c.path,
        }
        for c in session.cookies
    ]
    required = _BASE_COOKIE_NAMES
    present  = {c["name"] for c in cookies_in_session}
    missing  = required - present

    return jsonify({
        "cookie_count": len(cookies_in_session),
        "cookies":      cookies_in_session,
        "required":     sorted(required),
        "present":      sorted(present),
        "missing":      sorted(missing),
        "status":       "ok" if not missing else "incomplete",
        "hint": (
            None if not missing else
            f"Cookie dasar yang kurang: {', '.join(missing)}. "
            f"Refresh cookie dasar lewat POST /api/refresh-cookies atau export ulang cookies.json."
        ),
    })


@app.post("/api/inject-cookies")
def inject_cookies():
    """
    Inject cookie dari JSON body langsung ke proxy session yang sedang berjalan.

    Body JSON:
        {"cookies": [{"name":"hlsSession","value":"...","domain":"stream-...","path":"/cctv_1"}, ...]}
    """
    global _proxy_session

    body = request.get_json(silent=True)
    if not body or "cookies" not in body:
        return jsonify({"error": "Body harus berisi field 'cookies' (array)."}), 400

    session = _get_session()
    injected = []

    for ck in body["cookies"]:
        name   = ck.get("name")
        value  = ck.get("value")
        domain = ck.get("domain", "")
        path   = ck.get("path", "/")

        if not name or value is None:
            continue

        session.cookies.set(name, value, domain=domain, path=path)
        injected.append({"name": name, "domain": domain, "path": path})
        logger.info(f"[INJECT] {name} â†’ domain={domain} path={path}")

    with _handshake_lock:
        _handshaked_paths.clear()

    return jsonify({"status": "ok", "injected": len(injected), "cookies": injected})


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# HLS PROXY ROUTES
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _extract_camera_identity(url: str) -> CameraIdentity | None:
    return core_extract_camera_identity(url)


def _normalize_camera_path(path: str) -> str | None:
    return core_normalize_camera_path(path)


def _cookie_domain_matches(hostname: str, cookie_domain: str) -> bool:
    return core_cookie_domain_matches(hostname, cookie_domain)


def _cookie_path_matches(camera_path: str, cookie_path: str) -> bool:
    return core_cookie_path_matches(camera_path, cookie_path)


def _has_base_cookies(session: req.Session) -> bool:
    return core_has_base_cookies(session)


def _camera_cookie_names(session: req.Session, identity: CameraIdentity) -> set[str]:
    return core_camera_cookie_names(session, identity)


def _has_camera_cookies(session: req.Session, identity: CameraIdentity) -> bool:
    return core_has_camera_cookies(session, identity)


def _get_camera_lock(camera_key: str) -> threading.Lock:
    return _handshake_manager._get_camera_lock(camera_key)


def _invalidate_camera_session(session: req.Session, url: str) -> None:
    _handshake_manager.invalidate_camera_session(session, url)


def _make_absolute_url(base_url: str, line: str) -> str:
    return core_make_absolute_url(base_url, line)


def _rewrite_playlist(content: str, base_url: str) -> str:
    return core_rewrite_playlist(content, base_url)


def _handshake_stream_session(session: req.Session, m3u8_url: str) -> bool:
    return _handshake_manager.handshake_stream_session(session, m3u8_url)


def _deprecated_flask_response(response: Response) -> Response:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Django DRF endpoint is the primary API surface"
    return response
@app.route("/proxy/playlist", methods=["GET", "OPTIONS"])
def proxy_playlist():
    if request.method == "OPTIONS":
        return _cors_preflight()

    m3u8_url = request.args.get("url")
    if not m3u8_url:
        return Response("Missing 'url' parameter", status=400)

    try:
        payload = _make_hls_service().fetch_playlist(m3u8_url)
        return _deprecated_flask_response(Response(payload.body, status=payload.status, headers=payload.headers))
    except Exception as e:
        logger.error(f"proxy_playlist error ({m3u8_url}): {e}")
        return Response(f"Proxy error: {e}", status=502)

@app.route("/proxy/segment", methods=["GET", "OPTIONS"])
def proxy_segment():
    if request.method == "OPTIONS":
        return _cors_preflight()

    seg_url = request.args.get("url")
    if not seg_url:
        return Response("Missing 'url' parameter", status=400)

    payload = _make_hls_service().fetch_segment(seg_url, request.headers.get("Range"))
    return _deprecated_flask_response(Response(payload.body, status=payload.status, headers=payload.headers))

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# HELPERS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _cors_preflight() -> Response:
    return Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Headers": "Range, Content-Type",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Max-Age":       "86400",
        },
    )


def _parse_range(range_header: str, file_len: int) -> tuple[int, int]:
    return core_parse_range(range_header, file_len)


def _detect_content_type(url: str) -> str:
    return core_detect_content_type(url)


if __name__ == "__main__":
    logger.info(f"HLS Cookie Proxy berjalan di http://{config.PROXY_HOST}:{config.PROXY_PORT}")
    app.run(host=config.PROXY_HOST, port=config.PROXY_PORT, debug=True, threaded=True)





















