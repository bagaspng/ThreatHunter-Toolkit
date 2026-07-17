import sys
import time
import random
import logging
from typing import Optional
from dataclasses import dataclass

# patchright patches CDP detection vectors that CF Turnstile checks
from patchright.sync_api import sync_playwright


@dataclass
class TurnstileResult:
    turnstile_value: Optional[str]
    elapsed_time_seconds: float
    status: str
    reason: Optional[str] = None


COLORS = {
    'MAGENTA': '\033[35m',
    'BLUE': '\033[34m',
    'GREEN': '\033[32m',
    'YELLOW': '\033[33m',
    'RED': '\033[31m',
    'RESET': '\033[0m',
}


# Register custom SUCCESS log level
SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


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
        if self.isEnabledFor(SUCCESS_LEVEL):
            self._log(SUCCESS_LEVEL, self.format_message('SUCCESS', 'GREEN', message), args, **kwargs)

    def warning(self, message, *args, **kwargs):
        super().warning(self.format_message('WARNING', 'YELLOW', message), *args, **kwargs)

    def error(self, message, *args, **kwargs):
        super().error(self.format_message('ERROR', 'RED', message), *args, **kwargs)


logging.setLoggerClass(CustomLogger)
logger = logging.getLogger("TurnstileAPIServer")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)


class TurnstileSolver:
    """Cloudflare Turnstile solver — hybrid approach.

    Uses patchright (CDP-patched Playwright) to bypass CF's automation
    detection, but navigates to the REAL page like RecaptchaSolver's
    demo approach. Best of both worlds:
    - patchright patches CDP detection vectors
    - Real page gives genuine origin + sitekey context
    - Human-like interactions pass behavioral telemetry checks
    """

    SETTLE_DELAY = 3

    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verification</title>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async></script>
    </head>
    <body>
        <div style="display:flex;justify-content:center;align-items:center;min-height:100vh">
            <!-- cf turnstile -->
        </div>
    </body>
    </html>
    """

    def __init__(self, debug: bool = False, headless: bool = False,
                 useragent: Optional[str] = None):
        self.debug = debug
        self.headless = headless
        self.useragent = useragent

    def _simulate_human(self, page):
        """Simulate human-like interactions for CF telemetry."""
        if self.debug:
            logger.debug("Simulating human behaviour...")

        try:
            # Mouse movements
            width = 1280
            height = 720
            for _ in range(random.randint(3, 6)):
                x = random.randint(100, width - 100)
                y = random.randint(100, height - 100)
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.1, 0.3))

            # Scroll down
            page.mouse.wheel(0, random.randint(200, 400))
            time.sleep(0.5)
        except Exception:
            pass

        if self.debug:
            logger.debug("Human simulation done")

    def _get_token(self, page) -> Optional[str]:
        """Read the cf-turnstile-response token.

        Uses page.input_value() which reads the real DOM value directly
        (not page.evaluate which runs in an isolated JS context).
        """
        # Method 1: Use Playwright's native input_value() — reads live DOM
        try:
            loc = page.locator("[name=cf-turnstile-response]")
            if loc.count() > 0:
                val = loc.first.input_value(timeout=1000)
                if val and len(val) > 10:
                    return val
        except Exception:
            pass

        # Method 2: Try getting the attribute 'value' (backup)
        try:
            loc = page.locator("[name=cf-turnstile-response]")
            if loc.count() > 0:
                val = loc.first.get_attribute("value", timeout=1000)
                if val and len(val) > 10:
                    return val
        except Exception:
            pass

        # Method 3: Try all hidden inputs with id containing 'response'
        try:
            locs = page.locator("input[type=hidden][id*=response]")
            for i in range(locs.count()):
                try:
                    val = locs.nth(i).input_value(timeout=500)
                    if val and len(val) > 100:
                        return val
                except Exception:
                    continue
        except Exception:
            pass

        return None

    def _diagnose(self, page) -> dict:
        """Quick DOM diagnostic using Playwright APIs (not evaluate)."""
        r = {}
        try:
            # Count CF frames via page.frames (sees cross-origin frames)
            cf_frames = [f for f in page.frames
                         if "challenges.cloudflare.com" in (f.url or "")]
            r["cf_frames"] = len(cf_frames)
            r["cf_frame_urls"] = [f.url[:100] for f in cf_frames]

            # Token value via locator
            try:
                loc = page.locator("[name=cf-turnstile-response]")
                r["input_exists"] = loc.count() > 0
                if r["input_exists"]:
                    r["input_val"] = (loc.first.input_value(timeout=500) or "")[:50]
            except Exception:
                r["input_val"] = "read_error"

            # All frames
            r["total_frames"] = len(page.frames)
        except Exception as e:
            r["error"] = str(e)
        return r

    def _try_render(self, page, sitekey: str) -> bool:
        """Manually render the Turnstile widget."""
        try:
            result = page.evaluate(f"""
                () => {{
                    if (typeof turnstile === 'undefined') return 'no_api';
                    let container = document.getElementById('cf-turnstile')
                        || document.querySelector('.cf-turnstile');
                    if (!container) {{
                        container = document.createElement('div');
                        container.id = 'cf-turnstile';
                        const form = document.querySelector('form');
                        const btn = document.querySelector('button[type="submit"]');
                        if (btn) btn.parentNode.insertBefore(container, btn);
                        else if (form) form.appendChild(container);
                        else document.body.appendChild(container);
                    }}
                    try {{
                        container.innerHTML = '';
                        const wid = turnstile.render(container, {{
                            sitekey: '{sitekey}',
                            callback: function(token) {{
                                const inp = document.querySelector('[name=cf-turnstile-response]');
                                if (inp) inp.value = token;
                            }}
                        }});
                        return 'rendered:' + wid;
                    }} catch(e) {{
                        return 'error:' + e.message;
                    }}
                }}
            """)
            if self.debug:
                logger.debug(f"Render: {result}")
            return result and str(result).startswith("rendered")
        except Exception as e:
            if self.debug:
                logger.debug(f"Render failed: {e}")
            return False

    def _try_reset(self, page) -> bool:
        """Reset all Turnstile widgets."""
        try:
            result = page.evaluate("""
                () => {
                    if (typeof turnstile === 'undefined') return 'no_api';
                    try { turnstile.reset(); return 'ok'; }
                    catch(e) { return 'err:' + e.message; }
                }
            """)
            if self.debug:
                logger.debug(f"Reset: {result}")
            return result == "ok"
        except Exception:
            return False

    def solve(self, url: str, sitekey: str,
              action: str = None, cdata: str = None) -> TurnstileResult:
        """Solve Turnstile.

        Strategy: Navigate to the REAL page (like RecaptchaSolver demo)
        using patchright (CDP-patched) to bypass automation detection.
        """
        start_time = time.time()
        playwright = None
        browser = None

        try:
            # ── Step 1: Launch patchright browser ──
            playwright = sync_playwright().start()

            args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--window-size=1280,720",
                "--lang=en-US",
            ]

            browser = playwright.chromium.launch(
                headless=self.headless,
                args=args,
            )

            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=self.useragent or (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            page = context.new_page()

            if self.debug:
                logger.debug("Browser launched (patchright stealth)")

            # ── Step 2: Navigate to REAL page ──
            if self.debug:
                logger.debug(f"Navigating to: {url}")

            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for network to settle
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            time.sleep(self.SETTLE_DELAY)

            if self.debug:
                logger.debug(f"Page loaded: {page.title()}")

            # ── Step 3: Human-like interaction ──
            self._simulate_human(page)
            time.sleep(1)

            # ── Step 4: Check if auto-solved ──
            token = self._get_token(page)
            if token:
                elapsed = round(time.time() - start_time, 3)
                logger.success(f"Auto-solved: {token[:45]}... in {elapsed}s")
                return TurnstileResult(
                    turnstile_value=token,
                    elapsed_time_seconds=elapsed,
                    status="success"
                )

            # ── Step 5: Diagnostic ──
            if self.debug:
                diag = self._diagnose(page)
                logger.debug(f"Initial DOM: {diag}")

            # ── Step 6: Wait for CF frames and try clicking ──
            # The CF challenge creates hidden iframes - visible via page.frames
            # Give it more time and try clicking the checkbox
            for wait_attempt in range(5):
                diag = self._diagnose(page)
                cf_frame_count = diag.get("cf_frames", 0)

                if self.debug:
                    logger.debug(f"Wait {wait_attempt+1}/5: {cf_frame_count} CF frames, "
                                 f"token={'<present>' if diag.get('input_val') else 'empty'}")

                if diag.get("input_val") and len(diag.get("input_val", "")) > 10:
                    token = self._get_token(page)
                    if token:
                        elapsed = round(time.time() - start_time, 3)
                        logger.success(f"Solved: {token[:45]}... in {elapsed}s")
                        return TurnstileResult(
                            turnstile_value=token,
                            elapsed_time_seconds=elapsed,
                            status="success"
                        )

                # Try clicking CF iframe checkbox if frames exist
                if cf_frame_count > 0:
                    try:
                        for frame in page.frames:
                            if "challenges.cloudflare.com" in (frame.url or ""):
                                try:
                                    # Try multiple selectors
                                    for sel in [".ctp-checkbox-container",
                                                "label.ctp-checkbox-label",
                                                "input[type='checkbox']",
                                                "#challenge-stage"]:
                                        loc = frame.locator(sel)
                                        if loc.count() > 0:
                                            loc.first.click(timeout=2000)
                                            if self.debug:
                                                logger.debug(f"Clicked CF checkbox: {sel}")
                                            break
                                except Exception:
                                    pass
                    except Exception:
                        pass

                time.sleep(3)

            # Check token after clicking
            token = self._get_token(page)
            if token:
                return TurnstileResult(
                    turnstile_value=token,
                    elapsed_time_seconds=elapsed,
                    status="success"
                )

            # ── Step 7: Poll loop ──
            max_attempts = 25

            for attempt in range(max_attempts):
                if self.debug:
                    logger.debug(f"Attempt {attempt + 1}/{max_attempts}")

                token = self._get_token(page)
                if token:
                    elapsed = round(time.time() - start_time, 3)
                    logger.success(f"Solved: {token[:45]}... in {elapsed}s")
                    return TurnstileResult(
                        turnstile_value=token,
                        elapsed_time_seconds=elapsed,
                        status="success"
                    )

                # Click any visible turnstile iframe checkbox
                if attempt % 2 == 0:
                    try:
                        frames = page.frames
                        for frame in frames:
                            if "challenges.cloudflare.com" in (frame.url or ""):
                                try:
                                    cb = frame.locator(
                                        "input[type='checkbox'], .ctp-checkbox-container, #challenge-stage"
                                    )
                                    if cb.count() > 0:
                                        cb.first.click(timeout=1500)
                                        if self.debug:
                                            logger.debug("Clicked CF iframe checkbox")
                                except Exception:
                                    pass
                    except Exception:
                        pass

                # Periodic reset + re-render
                if attempt > 0 and attempt % 8 == 0:
                    if self.debug:
                        logger.debug("Reset + re-render...")
                    self._try_reset(page)
                    time.sleep(1)
                    self._try_render(page, sitekey)
                    self._simulate_human(page)
                    time.sleep(3)

                # Occasional mouse movement
                if attempt % 3 == 0:
                    try:
                        page.mouse.move(
                            random.randint(100, 600),
                            random.randint(100, 500)
                        )
                    except Exception:
                        pass

                time.sleep(2)

                # Periodic diagnostic
                if self.debug and attempt % 5 == 4:
                    diag = self._diagnose(page)
                    logger.debug(f"DOM: {diag}")

            # ── Failed ──
            elapsed = round(time.time() - start_time, 3)
            logger.error("Failed to retrieve Turnstile value.")
            if self.debug:
                diag = self._diagnose(page)
                logger.debug(f"Final DOM: {diag}")

            return TurnstileResult(
                turnstile_value=None,
                elapsed_time_seconds=elapsed,
                status="failure",
                reason="Max attempts reached"
            )

        except Exception as e:
            elapsed = round(time.time() - start_time, 3)
            logger.error(f"Solver error: {e}")
            return TurnstileResult(
                turnstile_value=None,
                elapsed_time_seconds=elapsed,
                status="failure",
                reason=str(e)
            )

        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass
            if self.debug:
                elapsed = round(time.time() - start_time, 3)
                logger.debug(f"Browser closed. Total: {elapsed}s")


def get_turnstile_token(url: str, sitekey: str,
                        action: str = None, cdata: str = None,
                        debug: bool = False, headless: bool = False,
                        useragent: str = None, **kwargs) -> dict:
    """Solve Turnstile by navigating to the real page.

    Args:
        url:       Target URL that already has a Turnstile widget
        sitekey:   The Turnstile sitekey
        debug:     Enable verbose logging
        headless:  Run browser headless
        useragent: Custom User-Agent string

    Returns:
        dict with keys: turnstile_value, elapsed_time_seconds, status, reason
    """
    solver = TurnstileSolver(
        debug=debug,
        headless=headless,
        useragent=useragent,
    )
    result = solver.solve(url=url, sitekey=sitekey, action=action, cdata=cdata)
    return result.__dict__


if __name__ == "__main__":
    result = get_turnstile_token(
        url="https://erpskrip.id/kontak",
        sitekey="0x4AAAAAABbPyJma04ow13Cc",
        debug=True,
        headless=False,
    )
    print("\n=== RESULT ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
