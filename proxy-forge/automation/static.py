import logging
import re
from curl_cffi import requests as curl_requests

try:
    from automation.contracts import PageProfile, SubmissionResult
    from automation.solver import solve_puzzle
except ImportError:
    from contracts import PageProfile, SubmissionResult
    from solver import solve_puzzle

logger = logging.getLogger("XoS-Automation")

async def submit_static(
    profile: PageProfile,
    proxy_str: str | None = None,
    config: any = None
) -> SubmissionResult:
    """
    Route: Static (curl_cffi POST handler).
    Submits forms using HTTP requests without launching any browser.
    """
    logger.info(f"[PHASE2][STATIC] Submitting form to {profile.action_url}")
    
    try:
        # Merge hidden_inputs + FORM_DATA from config
        form_payload: dict[str, str] = {}
        
        # Copy hidden inputs
        for k, v in profile.hidden_inputs.items():
            if k not in profile.honeypot_candidates:
                form_payload[k] = v

        # Copy form data from config
        config_form_data = getattr(config, "FORM_DATA", {})
        for k, v in config_form_data.items():
            if k not in profile.honeypot_candidates:
                form_payload[k] = v

        # Check for captcha prompt in raw_html if needed
        match = re.search(r"Pertanyaan:\s*(.*?)\s*(?:Ganti Pertanyaan|Submit)", profile.raw_html, re.DOTALL)
        if match:
            question_text = match.group(1).strip()
            answer = solve_puzzle(question_text)
            form_payload["captcha_answer"] = str(answer)

        proxies = None
        if proxy_str:
            proxies = {
                "http": proxy_str,
                "https": proxy_str,
            }

        timeout = getattr(config, "TIMEOUT", 10)
        
        resp = curl_requests.request(
            method=profile.method or "POST",
            url=profile.action_url,
            data=form_payload,
            impersonate="chrome124",
            proxies=proxies,
            timeout=timeout
        )

        return SubmissionResult(
            success=resp.status_code == 200,
            status_code=resp.status_code,
            response_text=resp.text
        )
    except Exception as e:
        logger.error(f"[PHASE2][STATIC] Static submission failed: {e}")
        return SubmissionResult(
            success=False,
            status_code=None,
            response_text=None,
            error=e
        )
