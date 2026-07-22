"""
app.py — Flask HLS Proxy Server

Alur kerja:
    1. /api/refresh-cookies  → Panggil cookies-exp.py Selenium service,
                               simpan cookie ke output/cookies_cache.json
    2. /api/cameras          → Baca cameras.json, kembalikan daftar kamera
    3. /proxy/playlist       → Fetch .m3u8 dari CDN dengan cookie, rewrite URL
                               segmen agar mengarah ke /proxy/segment lokal
    4. /proxy/segment        → Fetch segmen .ts dari CDN dengan cookie,
                               teruskan ke browser (mendukung Range header)
    5. /player               → Halaman UI HLS.js

Bypass SOP (Same-Origin Policy):
    Browser tidak dapat mengirim Cookie cross-origin ke subdomain streaming.
    Proxy ini menyelesaikan masalah tersebut dengan menjadi perantara:
    - Browser hanya berbicara dengan proxy lokal (http://localhost:5000)
    - Proxy menyimpan cookie sesi dan menyertakannya pada setiap request
      ke server CDN eksternal — transparan bagi browser.
"""

import hashlib
import json
import os
import threading
import urllib.parse
from pathlib import Path

import requests as req
from flask import Flask, Response, jsonify, render_template, request

import config
from scraper import (
    build_session,
    fetch_with_session,
    load_cookies_from_file,
    logger,
    save_json,
)

_CCTV_API_URL = "https://api-newseribuwajah.bandarlampungkota.go.id/cctvs"
_CCTV_API_KEY = "ParkirIlegalDetectKey2026"

app = Flask(__name__)

# ── Session & Cookie State (in-memory, refreshed via /api/refresh-cookies) ────
_session_lock = threading.Lock()
_proxy_session: req.Session | None = None
_loaded_cookies: list[dict] = []

# ── Handshake cache (per kamera, per session) ─────────────────────────────────
_handshaked_paths: set[str] = set()
_handshake_lock = threading.Lock()


def _refresh_cookies_from_service(target_url: str) -> list[dict]:
    """Minta cookie service menavigasi target URL tertentu lalu kembalikan cookies."""
    resp = req.post(
        f"{config.COOKIE_SERVICE_URL}/scrape",
        json={"url": target_url},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    cookies = data.get("cookies", [])
    if not cookies:
        raise ValueError(f"Tidak ada cookie yang diterima dari target {target_url}")
    save_json({"url": target_url, "cookies": cookies}, config.COOKIES_CACHE_FILE)
    _rebuild_session(cookies)
    return cookies


def _get_session() -> req.Session:
    """
    Kembalikan session aktif.

    Urutan sumber cookie:
    1. In-memory session (sudah di-rebuild via /api/refresh-cookies)
    2. output/cookies_cache.json  — dari Selenium service
    3. cookies.json               — dari browser export manual
    4. Session kosong (stream kemungkinan akan 403)
    """
    global _proxy_session
    with _session_lock:
        if _proxy_session is None:
            cookies = load_cookies_from_file(config.COOKIES_CACHE_FILE)
            if not cookies:
                cookies = load_cookies_from_file(config.COOKIES_MANUAL_FILE)
            _proxy_session = build_session(cookies)
            logger.info(
                f"Session dibuat dengan {len(cookies)} cookie "
                f"({'cache' if cookies else 'kosong — kemungkinan 403 dari CDN'})"
            )
        return _proxy_session


def _rebuild_session(cookies: list[dict]) -> None:
    """Rebuild session dengan cookie baru (dipanggil setelah refresh)."""
    global _proxy_session, _loaded_cookies
    with _session_lock:
        _loaded_cookies = cookies
        _proxy_session = build_session(cookies)
    with _handshake_lock:
        _handshaked_paths.clear()
    logger.info(f"Session di-rebuild dengan {len(cookies)} cookie baru.")


# ── Cache segmen .ts di disk ───────────────────────────────────────────────────
_CACHE_DIR = Path("cache_segments")
_CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(url: str) -> Path:
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return _CACHE_DIR / f"{url_hash}.dat"


# ─────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return jsonify({
        "service": "HLS Cookie Proxy",
        "endpoints": {
            "GET  /player":                 "Dashboard pemutar HLS",
            "POST /api/refresh-cookies":    "Refresh cookie dari Selenium service",
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
    Panggil cookies-exp.py Selenium service untuk mendapatkan cookie segar
    dari portal utama, lalu simpan ke cache dan rebuild session.
    """
    try:
        target_url = (request.get_json(silent=True) or {}).get("url") or config.PORTAL_URL
        cookies = _refresh_cookies_from_service(target_url)

        return jsonify({
            "status": "ok",
            "cookie_count": len(cookies),
            "cookies": [{"name": c.get("name"), "domain": c.get("domain")} for c in cookies],
        })

    except req.ConnectionError:
        return jsonify({
            "status": "error",
            "message": f"Tidak dapat terhubung ke Selenium service di {config.COOKIE_SERVICE_URL}. "
                       f"Pastikan cookies-exp.py berjalan (port 5001).",
        }), 503
    except Exception as e:
        logger.error(f"refresh_cookies error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


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
            "value":  c.value[:40] + "…" if len(c.value) > 40 else c.value,
            "domain": c.domain,
            "path":   c.path,
        }
        for c in session.cookies
    ]
    required = {"cctv_access", "stream_token", "hlsSession", "cookieCheck"}
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
            f"Cookie yang kurang: {', '.join(missing)}. "
            f"Export ulang cookies.json dari browser SETELAH membuka halaman player kamera, "
            f"lalu panggil POST /api/inject-cookies."
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
        logger.info(f"[INJECT] {name} → domain={domain} path={path}")

    with _handshake_lock:
        _handshaked_paths.clear()

    return jsonify({"status": "ok", "injected": len(injected), "cookies": injected})


# ─────────────────────────────────────────────────────────────────────────────
# HLS PROXY ROUTES
# ─────────────────────────────────────────────────────────────────────────────

def _make_absolute_url(base_url: str, line: str) -> str:
    if line.startswith("http://") or line.startswith("https://"):
        return line
    return urllib.parse.urljoin(base_url, line)


def _rewrite_playlist(content: str, base_url: str) -> str:
    """
    Tulis ulang isi file .m3u8 agar setiap segmen dan sub-playlist
    mengarah ke endpoint proxy lokal, bukan langsung ke CDN.
    """
    lines = content.splitlines()
    rewritten: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            rewritten.append(line)
            continue

        abs_url = _make_absolute_url(base_url, stripped)
        encoded = urllib.parse.quote(abs_url, safe="")

        if stripped.endswith(".m3u8"):
            rewritten.append(f"/proxy/playlist?url={encoded}")
        else:
            rewritten.append(f"/proxy/segment?url={encoded}")

    return "\n".join(rewritten) + "\n"


def _handshake_stream_session(session: req.Session, m3u8_url: str) -> None:
    """
    Lakukan handshake ke streaming server CDN untuk memperoleh cookie
    `hlsSession` dan `cookieCheck` yang diperlukan sebelum mengakses .m3u8.
    Hanya dilakukan sekali per kamera per session aktif.
    """
    parsed = urllib.parse.urlparse(m3u8_url)
    path_parts = parsed.path.rstrip("/").split("/")

    cam_segment = ""
    for part in path_parts:
        if part.startswith("cctv_"):
            cam_segment = part
            break

    if not cam_segment:
        return

    base_path = f"/{cam_segment}/"
    handshake_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, base_path, "", "", ""))
    handshake_key = f"{parsed.netloc}{base_path}"

    with _handshake_lock:
        if handshake_key in _handshaked_paths:
            return

    logger.info(f"[HANDSHAKE] Inisialisasi sesi untuk {cam_segment}…")
    try:
        resp = session.get(
            handshake_url,
            headers={
                "Referer":        config.STREAM_REFERER,
                "Origin":         config.STREAM_REFERER.rstrip("/"),
                "Accept":         "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "navigate",
            },
            timeout=10,
            allow_redirects=True,
        )

        # Ambil hlsSession + cookieCheck yang baru di-set server,
        # lalu duplikasi ke path "/" agar berlaku untuk SEMUA sub-path
        # (server set cookie dengan path=/cctv_X, tapi requests hanya
        # mengirimnya ke URL yang path-nya cocok — duplikasi ke "/" fix ini).
        hls_val = None
        check_val = None
        for c in session.cookies:
            if c.name == "hlsSession" and c.path == base_path:
                hls_val = c.value
            if c.name == "cookieCheck" and c.path == base_path:
                check_val = c.value

        if hls_val:
            session.cookies.set("hlsSession", hls_val,
                                domain=parsed.netloc, path="/")
        if check_val:
            session.cookies.set("cookieCheck", check_val,
                                domain=parsed.netloc, path="/")

        hls_session = hls_val or "(belum didapat)"
        cookie_check = check_val or "(belum didapat)"

        logger.info(
            f"[HANDSHAKE] HTTP {resp.status_code} | "
            f"hlsSession={hls_session[:8] if hls_val else hls_session}… | "
            f"cookieCheck={cookie_check}"
        )

        with _handshake_lock:
            _handshaked_paths.add(handshake_key)

    except Exception as e:
        logger.warning(f"[HANDSHAKE] Gagal (akan tetap mencoba fetch): {e}")


@app.route("/proxy/playlist", methods=["GET", "OPTIONS"])
def proxy_playlist():
    if request.method == "OPTIONS":
        return _cors_preflight()

    m3u8_url = request.args.get("url")
    if not m3u8_url:
        return Response("Missing 'url' parameter", status=400)

    try:
        session = _get_session()
        required = {"cctv_access", "stream_token", "hlsSession", "cookieCheck"}
        present = {c.name for c in session.cookies}
        if not required.issubset(present):
            try:
                _refresh_cookies_from_service(config.PORTAL_URL)
                session = _get_session()
            except Exception as refresh_error:
                logger.warning(f"[REFRESH] Gagal refresh via service untuk portal: {refresh_error}")

        _handshake_stream_session(session, m3u8_url)

        resp = fetch_with_session(session, m3u8_url, referer=config.STREAM_REFERER, timeout=config.TIMEOUT)

        if resp.status_code in (401, 403):
            parsed = urllib.parse.urlparse(m3u8_url)
            for part in parsed.path.rstrip("/").split("/"):
                if part.startswith("cctv_"):
                    key = f"{parsed.netloc}/{part}/"
                    with _handshake_lock:
                        _handshaked_paths.discard(key)
                    break

            try:
                _refresh_cookies_from_service(config.PORTAL_URL)
                session = _get_session()
                _handshake_stream_session(session, m3u8_url)
                resp = fetch_with_session(session, m3u8_url, referer=config.STREAM_REFERER, timeout=config.TIMEOUT)
            except Exception as refresh_error:
                logger.warning(f"[REFRESH] Retry refresh gagal untuk {m3u8_url}: {refresh_error}")

            if resp.status_code in (401, 403):
                return Response(
                    f"{resp.status_code} dari CDN — Cookie stream belum terbentuk untuk URL ini. "
                    f"Coba POST /api/refresh-cookies dengan url stream yang sama atau buka stream di browser asli lalu export cookies terbaru.",
                    status=resp.status_code,
                    headers={"Access-Control-Allow-Origin": "*"},
                )

        resp.raise_for_status()
        rewritten = _rewrite_playlist(resp.text, m3u8_url)

        return Response(
            rewritten,
            status=200,
            headers={
                "Content-Type":                    "application/vnd.apple.mpegurl",
                "Cache-Control":                   "no-store, no-cache",
                "Access-Control-Allow-Origin":     "*",
                "Access-Control-Allow-Headers":    "Range, Content-Type",
                "Access-Control-Expose-Headers":   "Content-Length, Content-Range",
            },
        )
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

    cache_file = _cache_path(seg_url)

    if cache_file.exists():
        body = cache_file.read_bytes()
        logger.debug(f"CACHE HIT: {seg_url.split('/')[-1]}")
    else:
        try:
            session = _get_session()
            resp = fetch_with_session(session, seg_url, referer=config.STREAM_REFERER, timeout=config.TIMEOUT)
            if resp.status_code == 403:
                return Response(b"", status=403, headers={"Access-Control-Allow-Origin": "*"})
            resp.raise_for_status()
            body = resp.content

            tmp = str(cache_file) + ".tmp"
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, cache_file)
            logger.debug(f"CACHE MISS: {seg_url.split('/')[-1]} ({len(body)} bytes)")

        except Exception as e:
            logger.error(f"proxy_segment fetch error: {e}")
            return Response(b"", status=502, headers={"Access-Control-Allow-Origin": "*"})

    range_header = request.headers.get("Range")
    body_len = len(body)
    content_type = _detect_content_type(seg_url)

    if range_header:
        start, end = _parse_range(range_header, body_len)
        sliced = body[start: end + 1]
        return Response(
            sliced,
            status=206,
            headers={
                "Content-Type":                  content_type,
                "Content-Length":                str(len(sliced)),
                "Content-Range":                 f"bytes {start}-{end}/{body_len}",
                "Accept-Ranges":                 "bytes",
                "Cache-Control":                 "no-store",
                "Access-Control-Allow-Origin":   "*",
                "Access-Control-Expose-Headers": "Content-Length, Content-Range",
            },
        )

    return Response(
        body,
        status=200,
        headers={
            "Content-Type":                  content_type,
            "Content-Length":                str(body_len),
            "Accept-Ranges":                 "bytes",
            "Cache-Control":                 "no-store",
            "Access-Control-Allow-Origin":   "*",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

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
    try:
        parts = range_header.replace("bytes=", "").strip().split("-")
        start = int(parts[0]) if parts[0] else 0
        end   = int(parts[1]) if len(parts) > 1 and parts[1] else file_len - 1
        return max(0, start), min(end, file_len - 1)
    except Exception:
        return 0, file_len - 1


def _detect_content_type(url: str) -> str:
    clean = url.split("?")[0].lower()
    if clean.endswith(".m4s") or clean.endswith(".mp4"):
        return "video/mp4"
    if clean.endswith(".aac") or clean.endswith(".m4a"):
        return "audio/aac"
    return "video/mp2t"


if __name__ == "__main__":
    logger.info(f"HLS Cookie Proxy berjalan di http://{config.PROXY_HOST}:{config.PROXY_PORT}")
    logger.info(f"Pastikan cookies-exp.py berjalan di port 5001")
    app.run(host=config.PROXY_HOST, port=config.PROXY_PORT, debug=True, threaded=True)
