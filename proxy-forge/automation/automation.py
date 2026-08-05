import argparse
import asyncio
import logging
import os
import sys
from typing import Any

# Add project root & src root to sys.path to enable imports from automation and proxyforge
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator
try:
    from automation.config import QNN_CONFIG
    from automation.contracts import ExhaustedProxyError, EmptyProxyPoolError, SubmissionResult
    from automation.probe import probe_page, clear_profile_cache
    from automation.router import route_submission
except ImportError:
    from config import QNN_CONFIG
    from contracts import ExhaustedProxyError, EmptyProxyPoolError, SubmissionResult
    from probe import probe_page, clear_profile_cache
    from router import route_submission

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("XoS-Automation")

async def run_automation_async(iterations: int = 3, url: str | None = None) -> None:
    """
    Phase 3: Orchestrator & Fault Tolerance Loop.
    Coordinates Probe -> Router -> Submission with automatic proxy eviction & retry.
    """
    target_url = url or getattr(QNN_CONFIG, "TARGET_URL", QNN_CONFIG.url)
    logger.info(f"Memulai Orkestrasi Automasi Form & Captcha ke target: {target_url}")

    # Load ProxyPool & Initialize ProxyRotator
    pool_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'working_proxies.json'))
    if not os.path.exists(pool_path):
        raise EmptyProxyPoolError("working_proxies.json tidak ditemukan. Jalankan: python main.py validate")

    pool = ProxyPool.load(pool_path)
    if not pool.proxies:
        raise EmptyProxyPoolError("No proxies available. Run: python main.py validate")

    rotator = ProxyRotator(pool)
    max_retries = getattr(QNN_CONFIG, "MAX_RETRIES", 3)

    for i in range(1, iterations + 1):
        if rotator.pool_size == 0:
            logger.error(f"[x] ExhaustedProxyError: Seluruh proxy dalam pool telah habis/burned untuk {target_url}")
            raise ExhaustedProxyError(f"All proxies failed for {target_url}")

        current_proxy = rotator.current_proxy_uri
        logger.info(f"\n{'='*60}\n[*] Iterasi #{i} dari {iterations} | Active Proxy: {current_proxy}\n{'='*60}")

        retry_count = 0
        success = False

        while retry_count < max_retries:
            retry_count += 1
            if not current_proxy:
                break

            try:
                # Phase 1: Probe (Step 1/5 Ping, Step 2/5 Page Analysis)
                profile = probe_page(target_url, proxy_str=current_proxy, timeout=getattr(QNN_CONFIG, "TIMEOUT", 10))

                # Phase 2: Route & Submit (Step 3/5 Browser & Form, Step 4/5 Captcha, Step 5/5 Submit)
                result: SubmissionResult = await route_submission(profile, proxy_str=current_proxy, config=QNN_CONFIG)

                if result.success:
                    logger.info(f"[+] [✓] Iterasi #{i} BERHASIL DISELESAIKAN.")
                    success = True
                    break
                else:
                    raise result.error or Exception(f"Submission failed with status {result.status_code}")

            except Exception as e:
                short_err = str(e).split("\n")[0]
                logger.warning(f"[!] Retry {retry_count}/{max_retries} — Evicting proxy {current_proxy} — Alasan: {short_err}")
                rotator.evict(current_proxy)
                current_proxy = rotator.current_proxy_uri
                
                if not current_proxy:
                    break

        if not success:
            logger.error(f"[x] ExhaustedProxyError: Seluruh {max_retries} percobaan proxy gagal pada Iterasi #{i}")

def run_automation(iterations: int = 3, url: str | None = None) -> None:
    """Synchronous entrypoint wrapper for CLI compatibility."""
    asyncio.run(run_automation_async(iterations=iterations, url=url))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Native Captcha Automation with Proxy Rotation")
    parser.add_argument(
        "--iterations", 
        type=int, 
        default=3, 
        help="Jumlah maksimal proxy / iterasi yang akan diuji (default: 3)"
    )
    parser.add_argument(
        "--url", 
        type=str, 
        default=None, 
        help="URL target pengujian automasi"
    )
    args = parser.parse_args()
    
    run_automation(iterations=args.iterations, url=args.url)