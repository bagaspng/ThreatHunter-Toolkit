"""Manual one-shot Selenium base cookie refresh.

Milestone 2 removes the old Flask HTTP cookie service. This script is kept as a
small CLI wrapper around upstream_auth.selenium_refresher.refresh_base_cookies.
"""

from __future__ import annotations

import argparse
import json
import time

import config
from scraper import save_json
from upstream_auth.selenium_refresher import (
    BaseCookieTimeout,
    CookieRefreshError,
    InvalidRefreshTarget,
    refresh_base_cookies,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh base CCTV cookies once with Selenium")
    parser.add_argument("url", nargs="?", default=config.PORTAL_URL, help="Target portal/stream URL")
    parser.add_argument(
        "--output",
        default=config.COOKIES_CACHE_FILE,
        help="Output JSON path (default: output/cookies_cache.json)",
    )
    parser.add_argument("--timeout", type=int, default=20, help="Cookie wait timeout in seconds")
    args = parser.parse_args()

    try:
        cookies = refresh_base_cookies(args.url, timeout=args.timeout)
    except InvalidRefreshTarget as exc:
        print(f"[ERROR] Target refresh ditolak: {exc}")
        return 2
    except BaseCookieTimeout as exc:
        print(f"[ERROR] Cookie dasar tidak lengkap: {exc}")
        return 3
    except CookieRefreshError as exc:
        print(f"[ERROR] Refresh Selenium gagal: {exc}")
        return 4

    output = {
        "url": args.url,
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cookie_count": len(cookies),
        "cookies": cookies,
    }
    save_json(output, args.output)
    visible = [{"name": cookie.get("name"), "domain": cookie.get("domain"), "path": cookie.get("path")} for cookie in cookies]
    print(json.dumps({"status": "ok", "cookie_count": len(cookies), "cookies": visible}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())