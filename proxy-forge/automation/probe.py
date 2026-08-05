import logging
import urllib.parse
from curl_cffi import requests as curl_requests
from selectolax.parser import HTMLParser

try:
    from automation.contracts import PageProfile
except ImportError:
    from contracts import PageProfile

logger = logging.getLogger("XoS-Automation")

# In-memory cache for PageProfile keyed by URL
_PROFILE_CACHE: dict[str, PageProfile] = {}

def clear_profile_cache() -> None:
    """Utility to clear the PageProfile in-memory cache if needed."""
    _PROFILE_CACHE.clear()

def ping_proxy(url: str, proxy_str: str | None = None, timeout: int = 10) -> bool:
    """
    Step 1/5: Lightweight HTTP ping check using curl_cffi (~0.5 - 1s).
    Ensures proxy connectivity before passing cached PageProfile to Router.
    """
    logger.info(f"  [1/5] Uji Koneksi Proxy ({proxy_str or 'direct'})...")
    proxies = None
    if proxy_str:
        proxies = {
            "http": proxy_str,
            "https": proxy_str,
        }

    try:
        resp = curl_requests.get(
            url,
            impersonate="chrome124",
            proxies=proxies,
            timeout=timeout
        )
        if resp.status_code >= 400:
            raise Exception(f"HTTP Status {resp.status_code}")
        logger.info("  -> [OK] Koneksi proxy responsif.")
        return True
    except Exception as e:
        short_err = str(e).split("\n")[0]
        logger.warning(f"  [x] GAGAL pada [1/5 - Uji Koneksi Proxy]: {short_err}")
        raise

def probe_page(url: str, proxy_str: str | None = None, timeout: int = 10, use_cache: bool = True) -> PageProfile:
    """
    Phase 1: Lightweight HTTP probe using curl_cffi + selectolax.
    Step 1: Proxy Ping Check
    Step 2: Page Analysis (SPA Score & Honeypot Detection)
    """
    # Use cached PageProfile if available
    if use_cache and url in _PROFILE_CACHE:
        # Step 1/5: Ping Check
        ping_proxy(url, proxy_str=proxy_str, timeout=timeout)
        cached_profile = _PROFILE_CACHE[url]
        logger.info(f"  [2/5] Analisis Halaman (SPA: {cached_profile.is_spa}, Honeypot: {len(cached_profile.honeypot_candidates)})... [OK] (Cached)")
        return cached_profile

    # Step 1/5: Ping/Fetch Check for uncached
    logger.info(f"  [1/5] Uji Koneksi Proxy & Mengambil HTML Target...")
    proxies = None
    if proxy_str:
        proxies = {
            "http": proxy_str,
            "https": proxy_str,
        }

    try:
        response = curl_requests.get(
            url,
            impersonate="chrome124",
            proxies=proxies,
            timeout=timeout
        )
        logger.info("  -> [OK] Koneksi proxy & fetch HTML berhasil.")
    except Exception as e:
        short_err = str(e).split("\n")[0]
        logger.warning(f"  [x] GAGAL pada [1/5 - Uji Koneksi Proxy]: {short_err}")
        raise

    logger.info("  [2/5] Menganalisis Struktur Halaman (SPA Score & Honeypot)...")
    html = response.text
    tree = HTMLParser(html)
    
    # 1. SPA Detection - Score-Based Calculation
    spa_score = 0
    for root_id in ["root", "app", "_next", "_nuxt"]:
        if tree.css_first(f"#{root_id}") is not None:
            spa_score += 2
            
    form_node = tree.css_first("form")
    if form_node is None:
        spa_score += 2
        
    body_node = tree.css_first("body")
    body_text = body_node.text(deep=True).strip() if body_node else ""
    if len(body_text) < 100:
        spa_score += 1
        
    if tree.css_first("noscript") is not None:
        spa_score += 1

    is_spa = spa_score >= 3
    
    # 2. Extract Action URL and Method
    action_url = url
    method = "POST"
    if form_node:
        raw_action = form_node.attributes.get("action", "")
        if raw_action:
            action_url = urllib.parse.urljoin(url, raw_action)
        method = form_node.attributes.get("method", "POST").upper()

    # 3. Extract Input Fields & Hidden Inputs & Honeypots
    fields: list[str] = []
    hidden_inputs: dict[str, str] = {}
    honeypot_candidates: list[str] = []

    for input_node in tree.css("input, textarea, select"):
        name = input_node.attributes.get("name", "")
        if not name:
            continue
            
        fields.append(name)
        input_type = input_node.attributes.get("type", "").lower()
        
        if input_type == "hidden":
            value = input_node.attributes.get("value", "")
            hidden_inputs[name] = value

        style = input_node.attributes.get("style", "").replace(" ", "").lower()
        aria_hidden = input_node.attributes.get("aria-hidden", "").lower()
        tabindex = input_node.attributes.get("tabindex", "")

        is_honeypot = False
        if "display:none" in style or "visibility:hidden" in style or "opacity:0" in style:
            is_honeypot = True
        elif "position:absolute" in style and ("left:-999" in style or "top:-999" in style):
            is_honeypot = True
        elif aria_hidden == "true":
            is_honeypot = True
        elif tabindex == "-1":
            is_honeypot = True
        elif "honeypot" in name.lower():
            is_honeypot = True

        if is_honeypot:
            honeypot_candidates.append(name)

    logger.info(f"  -> [OK] SPA Score: {spa_score} (is_spa={is_spa}), Honeypots Terdeteksi: {len(honeypot_candidates)}")

    profile = PageProfile(
        is_spa=is_spa,
        action_url=action_url,
        method=method,
        fields=fields,
        hidden_inputs=hidden_inputs,
        honeypot_candidates=honeypot_candidates,
        raw_html=html
    )

    _PROFILE_CACHE[url] = profile
    return profile
