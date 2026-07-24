"""Selenium-based base cookie refresh for the CCTV portal.

This module is importable by the Flask proxy and intentionally does not expose
an HTTP service. It only collects base portal cookies; per-camera stream cookies
are still created by the HTTP handshake in app.py.
"""

from __future__ import annotations

import ipaddress
import time
import urllib.parse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService

import config

REQUIRED_BASE_COOKIE_NAMES = {"cctv_access", "stream_token"}
COOKIE_FIELD_ORDER = [
    "name", "value", "domain", "path",
    "secure", "httpOnly", "sameSite",
    "expiry", "session",
]


class CookieRefreshError(Exception):
    """Base class for safe refresh errors."""


class InvalidRefreshTarget(CookieRefreshError):
    """Raised when a requested refresh target is outside the allowlist."""


class BaseCookieTimeout(CookieRefreshError):
    """Raised when Selenium finishes waiting without required base cookies."""


def allowed_refresh_hosts() -> set[str]:
    hosts = set(getattr(config, "ALLOWED_COOKIE_REFRESH_HOSTS", ()))
    for url in (config.PORTAL_URL, config.STREAM_REFERER):
        parsed = urllib.parse.urlparse(url)
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return {host.lower() for host in hosts if host}


def _is_private_or_local_hostname(hostname: str) -> bool:
    lowered = hostname.lower().rstrip(".")
    if lowered in {"localhost", "localhost.localdomain"}:
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved


def validate_refresh_target_url(target_url: str, allowed_hosts: set[str] | None = None) -> str:
    parsed = urllib.parse.urlparse(target_url or "")
    if parsed.scheme not in {"http", "https"}:
        raise InvalidRefreshTarget("URL refresh harus menggunakan skema http atau https.")
    if not parsed.hostname:
        raise InvalidRefreshTarget("URL refresh harus memiliki hostname.")
    if parsed.username or parsed.password:
        raise InvalidRefreshTarget("URL refresh tidak boleh berisi username atau password.")

    hostname = parsed.hostname.lower()
    allowlist = {host.lower() for host in (allowed_hosts or allowed_refresh_hosts())}
    if hostname not in allowlist:
        raise InvalidRefreshTarget("Hostname refresh tidak diizinkan.")
    if _is_private_or_local_hostname(hostname) and hostname not in allowlist:
        raise InvalidRefreshTarget("Hostname private atau lokal tidak diizinkan.")

    return urllib.parse.urlunparse(parsed._replace(netloc=parsed.netloc.lower()))


def build_chrome_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    try:
        service = ChromeService(executable_path="/usr/bin/chromedriver")
        return webdriver.Chrome(service=service, options=options)
    except Exception:
        return webdriver.Chrome(options=options)


def normalize_cookie(raw: dict) -> dict:
    normalized = {}
    for field in COOKIE_FIELD_ORDER:
        if field == "session":
            normalized["session"] = "expiry" not in raw
        elif field == "expiry":
            if "expiry" in raw:
                normalized["expiry"] = {
                    "unix": raw["expiry"],
                    "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(raw["expiry"])),
                }
        else:
            normalized[field] = raw.get(field, None)
    return normalized


def get_all_cookies(driver: webdriver.Chrome) -> list[dict]:
    try:
        data = driver.execute_cdp_cmd("Network.getAllCookies", {})
        return data.get("cookies", [])
    except Exception:
        return driver.get_cookies()


def _merge_cookies(cookies: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for cookie in cookies:
        name = cookie.get("name")
        if not name or cookie.get("value") is None:
            continue
        key = (name, cookie.get("domain", ""), cookie.get("path", "/"))
        merged[key] = cookie
    return list(merged.values())


def _filter_required_base_cookies(cookies: list[dict]) -> list[dict]:
    return [cookie for cookie in cookies if cookie.get("name") in REQUIRED_BASE_COOKIE_NAMES]


def wait_for_required_base_cookies(driver: webdriver.Chrome, timeout: int = 20) -> list[dict]:
    deadline = time.time() + timeout
    latest: list[dict] = []

    while time.time() < deadline:
        latest = _merge_cookies(get_all_cookies(driver))
        names = {cookie.get("name") for cookie in latest}
        if REQUIRED_BASE_COOKIE_NAMES.issubset(names):
            return _filter_required_base_cookies(latest)
        time.sleep(0.5)

    latest = _merge_cookies(get_all_cookies(driver))
    names = {cookie.get("name") for cookie in latest}
    if REQUIRED_BASE_COOKIE_NAMES.issubset(names):
        return _filter_required_base_cookies(latest)
    raise BaseCookieTimeout("Cookie dasar tidak lengkap setelah menunggu Selenium.")


def refresh_base_cookies(
    target_url: str,
    timeout: int = 20,
    driver_factory=build_chrome_driver,
) -> list[dict]:
    validated_url = validate_refresh_target_url(target_url)
    driver = None
    try:
        driver = driver_factory()
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        driver.get(validated_url)
        raw_cookies = wait_for_required_base_cookies(driver, timeout=timeout)
        return [normalize_cookie(cookie) for cookie in raw_cookies]
    except InvalidRefreshTarget:
        raise
    except BaseCookieTimeout:
        raise
    except TimeoutException as exc:
        raise BaseCookieTimeout("Halaman tidak merespons dalam batas waktu Selenium.") from exc
    except WebDriverException as exc:
        raise CookieRefreshError("WebDriver gagal diinisialisasi atau crash.") from exc
    finally:
        if driver is not None:
            driver.quit()