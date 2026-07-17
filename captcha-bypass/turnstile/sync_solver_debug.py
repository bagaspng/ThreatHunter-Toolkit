import sys
import time
import logging
from typing import Optional
from dataclasses import dataclass
from patchright.sync_api import sync_playwright


@dataclass
class TurnstileResult:
    turnstile_value: Optional[str]
    elapsed_time_seconds: float
    status: str
    reason: Optional[str] = None


COLORS = {
    'MAGENTA': '\033[35m',
    'BLUE':    '\033[34m',
    'GREEN':   '\033[32m',
    'YELLOW':  '\033[33m',
    'RED':     '\033[31m',
    'RESET':   '\033[0m',
}


class CustomLogger(logging.Logger):
    @staticmethod
    def format_message(level, color, message):
        timestamp = time.strftime('%H:%M:%S')
        return f"[{timestamp}] [{COLORS.get(color)}{level}{COLORS.get('RESET')}] -> {message}"

    def debug(self, message, *args, **kwargs):
        super().debug(self.format_message('DEBUG', 'MAGENTA', message), *args, **kwargs)

    def info(self, message, *args, **kwargs):
        super().info(self.format_message('INFO', 'BLUE', message), *args, **kwargs)

    def success(self, message, *args, **kwargs):
        super().info(self.format_message('SUCCESS', 'GREEN', message), *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        super().warning(self.format_message('WARNING', 'YELLOW', message), *args, **kwargs)

    def error(self, message, *args, **kwargs):
        super().error(self.format_message('ERROR', 'RED', message), *args, **kwargs)


logging.setLoggerClass(CustomLogger)
logger = logging.getLogger("TurnstileDebug")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Turnstile Solver</title>
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</head>
<body style="margin:40px;">
    <!-- cf turnstile -->
    <p>Loading challenge...</p>
</body>
</html>"""


def diagnose_dom(page) -> dict:
    """Jalankan JS di browser untuk snapshot kondisi DOM saat ini."""
    try:
        return page.evaluate("""() => {
            const cf      = document.querySelector('.cf-turnstile');
            const inp     = document.querySelector('[name=cf-turnstile-response]');
            const iframes = Array.from(document.querySelectorAll('iframe'))
                                 .map(f => f.src.substring(0, 100));
            const cfJs    = Array.from(document.querySelectorAll('script'))
                                 .some(s => s.src && s.src.includes('challenges.cloudflare'));
            const allInp  = Array.from(document.querySelectorAll('input'))
                                 .map(i => ({name: i.name, type: i.type, val: (i.value||'').substring(0,40)}));
            return {
                page_title:    document.title,
                cf_div:        cf  ? cf.outerHTML.substring(0, 200)  : 'NOT_FOUND',
                input_exists:  !!inp,
                input_value:   inp ? (inp.value || 'EMPTY') : 'N/A',
                cf_script:     cfJs,
                iframes:       iframes,
                all_inputs:    allInp,
                body_text:     document.body ? document.body.innerText.substring(0,150) : ''
            };
        }""")
    except Exception as e:
        return {"error": str(e)}


def solve_debug(url: str, sitekey: str, headless: bool = False):
    start = time.time()

    url_with_slash = url if url.endswith("/") else url + "/"

    turnstile_div = f'<div class="cf-turnstile" data-sitekey="{sitekey}"></div>'
    page_html = HTML_TEMPLATE.replace("<!-- cf turnstile -->", turnstile_div)

    playwright = sync_playwright().start()

    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-extensions",
            "--disable-dev-shm-usage",
            "--window-size=1280,720",
            "--lang=en-US,en",
        ]
    )

    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )

    page = context.new_page()

    # Intercept URL target dan serve HTML kita
    page.route(url_with_slash, lambda route: route.fulfill(
        body=page_html,
        status=200,
        headers={"Content-Type": "text/html"}
    ))

    logger.info(f"Navigating to: {url_with_slash}")
    page.goto(url_with_slash, wait_until="domcontentloaded", timeout=30000)

    # Tunggu CF script inject dirinya ke DOM
    logger.debug("Waiting for CF script to inject widget...")
    try:
        page.wait_for_function(
            "() => document.querySelector('.cf-turnstile') !== null",
            timeout=15000
        )
        logger.debug("cf-turnstile div confirmed in DOM")
    except Exception as e:
        logger.warning(f"cf-turnstile div wait timed out: {e}")

    # Snapshot DOM awal
    dom = diagnose_dom(page)
    logger.debug(f"[INIT DOM] title={dom.get('page_title')} | cf_script={dom.get('cf_script')} | cf_div={dom.get('cf_div')[:80] if dom.get('cf_div') else 'N/A'}")
    logger.debug(f"[INIT DOM] iframes={dom.get('iframes')}")
    logger.debug(f"[INIT DOM] all_inputs={dom.get('all_inputs')}")

    # Tunggu input cf-turnstile-response muncul di DOM
    try:
        page.wait_for_selector("[name=cf-turnstile-response]", state="attached", timeout=15000)
        logger.debug("cf-turnstile-response input attached to DOM")
    except Exception as e:
        logger.warning(f"cf-turnstile-response input never appeared: {e}")

    token = None
    for attempt in range(15):
        time.sleep(2)
        dom = diagnose_dom(page)

        logger.debug(
            f"[ATT {attempt+1:02d}] input_exists={dom.get('input_exists')} | "
            f"input_value={dom.get('input_value')} | "
            f"iframes={len(dom.get('iframes', []))} iframes | "
            f"cf_script={dom.get('cf_script')}"
        )

        val = dom.get("input_value", "")
        if val and val not in ("EMPTY", "N/A", ""):
            token = val
            logger.success(f"TOKEN FOUND at attempt {attempt+1}: {token[:50]}...")
            break

        # Coba click widget
        selectors = [
            ".cf-turnstile",
            "[class*='cf-turnstile']",
            "//div[contains(@class,'cf-turnstile')]",
        ]
        for sel in selectors:
            try:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.click(timeout=1500)
                    logger.debug(f"Clicked: {sel}")
                    break
            except Exception:
                pass

        # Coba click checkbox di dalam CF iframe
        try:
            ifrm = page.frame_locator("iframe[src*='challenges.cloudflare.com']")
            cb = ifrm.locator(".ctp-checkbox-container")
            if cb.count() > 0:
                cb.click(timeout=1500)
                logger.debug("Clicked CF iframe checkbox")
        except Exception:
            pass

    elapsed = round(time.time() - start, 3)

    try:
        browser.close()
        playwright.stop()
    except Exception:
        pass

    if token:
        return TurnstileResult(token, elapsed, "success")
    return TurnstileResult(None, elapsed, "failure", "Max attempts — see DEBUG logs above")


if __name__ == "__main__":
    result = solve_debug(
        url="https://erpskrip.id/kontak",
        sitekey="0x4AAAAAABbPyJma04ow13Cc",
        headless=False,
    )
    print("\n=== FINAL RESULT ===")
    print(f"Status        : {result.status}")
    print(f"Token         : {result.turnstile_value}")
    print(f"Elapsed       : {result.elapsed_time_seconds}s")
    if result.reason:
        print(f"Reason        : {result.reason}")