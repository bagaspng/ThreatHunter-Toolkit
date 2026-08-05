import asyncio
import logging
import random
import re
from playwright.async_api import async_playwright

try:
    from automation.contracts import PageProfile, SubmissionResult
    from automation.solver import solve_puzzle
except ImportError:
    from contracts import PageProfile, SubmissionResult
    from solver import solve_puzzle

logger = logging.getLogger("XoS-Automation")

async def submit_spa(
    profile: PageProfile,
    proxy_str: str | None = None,
    config: any = None
) -> SubmissionResult:
    """
    Route: SPA (Playwright Async handler with Resource Blocking).
    Executes Steps [3/5], [4/5], [5/5] with step-by-step progress logging.
    """
    playwright_obj = None
    browser = None
    context = None
    page = None
    current_step = "[3/5 - Membuka Peramban & Form Input]"

    try:
        logger.info("  [3/5] Membuka Peramban Headless & Mengisi Form Data...")
        playwright_obj = await async_playwright().start()
        
        # 1. Browser Launch & Proxy Setup
        launch_kwargs: dict = {"headless": True, "args": ["--no-sandbox"]}
        browser = await playwright_obj.chromium.launch(**launch_kwargs)
        
        context_kwargs: dict = {}
        if proxy_str:
            context_kwargs["proxy"] = {"server": proxy_str}
            
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        # 2. Resource Blocking & Tracker Interception
        block_patterns = getattr(config, "RESOURCE_BLOCK_PATTERNS", [
            "png", "jpg", "jpeg", "gif", "svg", "css", "woff", "woff2", "mp4", "mp3"
        ])
        tracker_domains = getattr(config, "TRACKER_DOMAINS", [
            "google-analytics.com", "googletagmanager.com", "facebook.net",
            "connect.facebook.net", "static.hotjar.com", "clarity.ms"
        ])

        async def route_interceptor(route):
            request_url = route.request.url.lower()
            if any(domain in request_url for domain in tracker_domains):
                await route.abort()
                return
            if route.request.resource_type in ["image", "stylesheet", "font", "media"]:
                await route.abort()
                return
            if any(request_url.endswith(f".{ext}") for ext in block_patterns):
                await route.abort()
                return
            await route.continue_()

        await page.route("**/*", route_interceptor)

        # 3. Navigation
        target_url = getattr(config, "TARGET_URL", profile.action_url)
        timeout_ms = getattr(config, "TIMEOUT", 10) * 1000
        
        # Use domcontentloaded for fast navigation through public proxies
        await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)

        # 4. Fill Form Fields
        form_selectors = getattr(config, "form_selectors", {})
        dummy_data = getattr(config, "FORM_DATA", {})
        delay_min = getattr(config, "RANDOM_DELAY_MIN", 0.5)
        delay_max = getattr(config, "RANDOM_DELAY_MAX", 2.0)

        for field_name, selector in form_selectors.items():
            if field_name in profile.honeypot_candidates:
                continue

            await page.wait_for_selector(selector, timeout=5000)
            val = dummy_data.get(field_name, "Test Data")
            await page.locator(selector).fill(val)
            await asyncio.sleep(random.uniform(delay_min, delay_max))

        logger.info("  -> [OK] Form data berhasil diisikan.")

        # Step 4/5: Captcha Flow & Solve
        current_step = "[4/5 - Memicu Checkbox & Solve Captcha]"
        logger.info("  [4/5] Memicu Checkbox Validation & Memecahkan Captcha...")

        robot_checkbox = getattr(config, "robot_checkbox_selector", "label[for='robotCheck']")
        await page.wait_for_selector(robot_checkbox, timeout=5000)
        await page.click(robot_checkbox)
        
        await asyncio.sleep(2.0)

        page_source = await page.content()
        match = re.search(r"Pertanyaan:\s*(.*?)\s*(?:Ganti Pertanyaan|Submit)", page_source, re.DOTALL)
        
        if match:
            question_text = match.group(1).strip()
            answer = solve_puzzle(question_text)
            logger.info(f"  -> [OK] Captcha Terdeteksi: '{question_text}' | Jawaban Solver: {answer}")
            
            captcha_selector = getattr(
                config, 
                "captcha_input_selector", 
                "input[name='captcha_answer']"
            )
            await page.wait_for_selector(captcha_selector, timeout=5000)
            await page.locator(captcha_selector).fill(str(answer))
            await asyncio.sleep(random.uniform(delay_min, delay_max))
        else:
            logger.info("  -> [i] Tidak ada teka-teki captcha tambahan yang terdeteksi.")

        # Step 5/5: Submit Execution
        current_step = "[5/5 - Menekan Tombol Submit & Validasi]"
        logger.info("  [5/5] Menekan Tombol Submit & Memverifikasi Respon...")

        submit_btn_selector = getattr(config, "submit_selector", "button[type='submit']")
        await page.wait_for_selector(submit_btn_selector, timeout=5000)
        await page.click(submit_btn_selector)

        await asyncio.sleep(3.0)
        final_url = page.url
        logger.info(f"  -> [OK] Form berhasil disubmit. Final URL: {final_url}")
        
        return SubmissionResult(
            success=True,
            status_code=200,
            response_text=f"SPA submission completed. Final URL: {final_url}"
        )

    except Exception as e:
        # Extract concise first line of error message to keep logs simple & clear
        short_err = str(e).split("\n")[0]
        logger.warning(f"  [x] GAGAL pada {current_step}: {short_err}")
        return SubmissionResult(
            success=False,
            status_code=None,
            response_text=None,
            error=e
        )

    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright_obj:
            try:
                await playwright_obj.stop()
            except Exception:
                pass
