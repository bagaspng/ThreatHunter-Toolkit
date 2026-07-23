import argparse
import json
import re
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import traceback

app = Flask(__name__)
CORS(app)

# ── Cookie key ordering untuk konsistensi output ──────────────────
COOKIE_FIELD_ORDER = [
    "name", "value", "domain", "path",
    "secure", "httpOnly", "sameSite",
    "expiry", "session"
]

_STREAM_URL_PATTERN = re.compile(
    r"https?://[^\"'\s>]+/(?:cctv_[0-9]+/index\.m3u8|stream/[0-9a-fA-F\-]+)",
    re.IGNORECASE,
)


def build_chrome_driver() -> webdriver.Chrome:
    """
    Factory function untuk Chrome WebDriver.
    Binary path di-hardcode untuk environment yang sudah install chromium.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    # Sesuaikan path sesuai environment:
    # Docker/Linux: options.binary_location = "/usr/bin/chromium-browser"
    # Windows: biarkan ChromeDriver auto-detect

    try:
        service = ChromeService(executable_path="/usr/bin/chromedriver")
        return webdriver.Chrome(service=service, options=options)
    except Exception:
        # Fallback: biarkan selenium cari chromedriver di PATH
        return webdriver.Chrome(options=options)


def normalize_cookie(raw: dict) -> dict:
    """
    Normalisasi struktur cookie dari Selenium ke format yang konsisten.
    - Konversi expiry Unix timestamp ke ISO 8601
    - Tandai cookie sebagai session jika tidak ada expiry
    - Urutkan field sesuai COOKIE_FIELD_ORDER
    """
    normalized = {}
    for field in COOKIE_FIELD_ORDER:
        if field == "session":
            normalized["session"] = "expiry" not in raw
        elif field == "expiry":
            if "expiry" in raw:
                normalized["expiry"] = {
                    "unix": raw["expiry"],
                    "iso":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(raw["expiry"]))
                }
        else:
            normalized[field] = raw.get(field, None)
    return normalized


def wait_for_cookies(driver: webdriver.Chrome, timeout: int = 15) -> list:
    """
    Strategi tunggu adaptif — polling cookie setiap 500ms
    hingga cookie stabil atau timeout tercapai.
    """
    deadline = time.time() + timeout
    last_count = 0

    while time.time() < deadline:
        cookies = driver.get_cookies()
        current_count = len(cookies)

        if current_count > 0 and current_count == last_count:
            time.sleep(1.0)
            final = driver.get_cookies()
            if len(final) == current_count:
                return final

        last_count = current_count
        time.sleep(0.5)

    return driver.get_cookies()


def get_all_cookies(driver: webdriver.Chrome) -> list[dict]:
    """Ambil semua cookie lintas domain via Chrome DevTools Protocol."""
    try:
        data = driver.execute_cdp_cmd("Network.getAllCookies", {})
        return data.get("cookies", [])
    except Exception:
        return driver.get_cookies()


def wait_for_stream_cookies(driver: webdriver.Chrome, timeout: int = 20) -> list[dict]:
    """Tunggu hingga cookie stream lintas domain muncul."""
    deadline = time.time() + timeout
    last_count = 0

    while time.time() < deadline:
        cookies = get_all_cookies(driver)
        current_count = len(cookies)
        names = {c.get("name") for c in cookies}

        if current_count > 0 and current_count == last_count:
            time.sleep(1.0)
            final = get_all_cookies(driver)
            final_names = {c.get("name") for c in final}
            if len(final) == current_count and ("hlsSession" in final_names or "cookieCheck" in final_names):
                return final

        last_count = current_count
        if "hlsSession" in names or "cookieCheck" in names:
            time.sleep(1.0)
            final = get_all_cookies(driver)
            final_names = {c.get("name") for c in final}
            if "hlsSession" in final_names or "cookieCheck" in final_names:
                return final

        time.sleep(0.5)

    return get_all_cookies(driver)


def extract_stream_urls_from_page(html: str) -> list[str]:
    """Ambil kandidat URL stream dari HTML halaman portal."""
    seen: set[str] = set()
    urls: list[str] = []
    for match in _STREAM_URL_PATTERN.findall(html):
        if match not in seen:
            seen.add(match)
            urls.append(match)
    return urls


def merge_cookies(cookies_list: list[list[dict]]) -> list[dict]:
    """Gabungkan cookie dari beberapa halaman, prioritaskan entri terakhir."""
    merged: dict[tuple[str, str, str], dict] = {}
    for cookies in cookies_list:
        for cookie in cookies:
            name = cookie.get("name")
            if not name or cookie.get("value") is None:
                continue
            key = (name, cookie.get("domain", ""), cookie.get("path", "/"))
            merged[key] = cookie
    return list(merged.values())


def trigger_first_camera_modal(driver: webdriver.Chrome) -> bool:
    """Klik kartu kamera pertama di portal list agar modal player terbuka."""
    try:
        cards = driver.find_elements("css selector", "div.cursor-pointer")
        if not cards:
            return False
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cards[0])
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", cards[0])
        return True
    except Exception:
        return False


@app.route("/")
def health_check():
    return jsonify({
        "status":    "healthy",
        "message":   "Cookie scraper API is running.",
        "endpoints": {"POST /scrape": "Body: {\"url\": \"https://...\"}"},
    }), 200


@app.route("/scrape", methods=["POST"])
def scrape_cookies():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Request body harus berupa JSON dengan field 'url'."}), 400

    target_url = data["url"]
    if not target_url.startswith(("http://", "https://")):
        return jsonify({"error": "URL tidak valid. Harus dimulai dengan http:// atau https://"}), 400

    print(f"[SCRAPE] Target: {target_url}")

    driver = None
    try:
        driver = build_chrome_driver()
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)

        print("[SCRAPE] Navigating...")
        driver.get(target_url)

        print("[SCRAPE] Waiting for cookies (adaptive polling)...")
        collected_cookies = [wait_for_cookies(driver, timeout=15)]

        if "/list" in target_url:
            print("[SCRAPE] Triggering first camera modal...")
            if trigger_first_camera_modal(driver):
                collected_cookies.append(wait_for_stream_cookies(driver, timeout=20))

        html = driver.page_source or ""
        stream_urls = extract_stream_urls_from_page(html)
        if stream_urls:
            print(f"[SCRAPE] Found {len(stream_urls)} stream URL(s); opening first stream page...")
            stream_url = stream_urls[0]
            if stream_url.endswith("index.m3u8"):
                stream_url = stream_url.rsplit("/", 1)[0] + "/"
            driver.get(stream_url)
            collected_cookies.append(wait_for_stream_cookies(driver, timeout=20))

        raw_cookies = merge_cookies(collected_cookies)

        if not raw_cookies:
            return jsonify({
                "url":          target_url,
                "cookie_count": 0,
                "message":      "Tidak ada cookie yang ditemukan.",
                "cookies":      [],
            }), 200

        normalized_cookies = [normalize_cookie(c) for c in raw_cookies]
        output = {
            "url":          target_url,
            "scraped_at":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cookie_count": len(normalized_cookies),
            "cookies":      normalized_cookies,
        }

        print(f"[SCRAPE] Done. {len(normalized_cookies)} cookies found.")
        return jsonify(output), 200

    except TimeoutException:
        return jsonify({"error": "Halaman tidak merespons dalam batas waktu 60 detik.", "url": target_url}), 504

    except WebDriverException as e:
        return jsonify({"error": "WebDriver gagal diinisialisasi atau crash.", "details": str(e)}), 500

    except Exception as e:
        print(f"[ERROR] {traceback.format_exc()}")
        return jsonify({"error": "Internal server error.", "details": str(e)}), 500

    finally:
        if driver:
            driver.quit()
            print("[SCRAPE] WebDriver closed.")


@app.post("/import")
def import_cookies():
    """
    Import cookie langsung dari body request (tanpa Selenium).
    Body JSON: {"cookies": [{"name": "...", "value": "...", "domain": "..."}, ...]}
    """
    body = request.get_json(silent=True)
    if not body or "cookies" not in body:
        return jsonify({"error": "Body harus berisi field 'cookies' (array)."}), 400

    raw_list = body["cookies"]
    normalized = [
        {
            "name":   c["name"],
            "value":  c["value"],
            "domain": c.get("domain", ""),
            "path":   c.get("path", "/"),
            "secure": c.get("secure", False),
        }
        for c in raw_list
        if c.get("name") and c.get("value") is not None
    ]

    if not normalized:
        return jsonify({"error": "Tidak ada cookie valid dalam payload."}), 400

    print(f"[IMPORT] {len(normalized)} cookie diimport.")
    return jsonify({
        "status":       "ok",
        "cookie_count": len(normalized),
        "cookies":      normalized,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cookie Scraper Service")
    parser.add_argument("--port", type=int, default=5001, help="Port server (default: 5001)")
    args = parser.parse_args()

    print(f"[INFO] Cookie Scraper Service berjalan di http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)
