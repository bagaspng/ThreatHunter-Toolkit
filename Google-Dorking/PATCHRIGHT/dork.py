import json
import asyncio
import os
import sys
import io
import random
import re
from pathlib import Path
from datetime import datetime

# Fix encoding console Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

# Import Patchright dengan auto-install
try:
    from patchright.async_api import async_playwright
except ImportError:
    print("Menginstal patchright...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "patchright", "-q"])
    subprocess.check_call([sys.executable, "-m", "patchright", "install", "chromium"])
    from patchright.async_api import async_playwright

# === KONFIGURASI FINGERPRINT ===
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
]

LOCALES = ["en-US", "en-GB", "en-CA", "id-ID"]

# === HELPER FUNCTIONS ===
def get_int_input(prompt, min_val, max_val, default):
    while True:
        try:
            val = input(prompt).strip()
            if not val: return default
            val = int(val)
            if min_val <= val <= max_val: return val
            print(f"  Harus antara {min_val}-{max_val}")
        except ValueError:
            print("  Input tidak valid. Menggunakan default.")
            return default

def get_float_input(prompt, min_val, default):
    while True:
        try:
            val = input(prompt).strip()
            if not val: return default
            val = float(val)
            if val >= min_val: return val
            print(f"  Minimum {min_val}")
        except ValueError:
            print("  Input tidak valid. Menggunakan default.")
            return default

def sanitize_query(query: str) -> str:
    operators = r'(site|filetype|ext|intext|inurl|allintext|allinurl|cache|link|info|related)'
    return re.sub(rf'{operators}:\s*', r'\1:', query, flags=re.IGNORECASE).strip()

def log_event(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

# === STEALTH & ANTI-DETECTION ===
class StealthManager:
    def get_random_fingerprint(self):
        return {
            "user_agent": random.choice(USER_AGENTS),
            "viewport": random.choice(VIEWPORTS),
            "locale": random.choice(LOCALES),
            "timezone_id": random.choice(["America/New_York", "Europe/London", "Asia/Singapore", "Asia/Jakarta"]),
        }

# === MAIN DORKER CLASS ===
class GoogleDorker:
    def __init__(self, headless: bool = True, delay: float = 2.0):
        self.headless = headless
        self.delay = delay
        self.results = []
        self.seen_urls = set()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.stealth = StealthManager()
        self.cookies_file = Path.home() / ".google_dork_cookies.json"
        
        self.stats = {
            "total_requests": 0, 
            "successful_requests": 0,
            "captcha_encounters": 0,
            "urls_validated": 0,
            "urls_alive": 0,
            "urls_dead": 0
        }

    def build_query(self, site: str = None, keywords: list = None, filetype: str = None) -> str:
        parts = []
        if site: parts.append(f"site:{site}")
        if keywords: parts.append(" ".join(keywords))
        if filetype: parts.append(f"filetype:{filetype}")
        return " ".join(parts)

    async def init_browser(self, fresh_session: bool = False):
        log_event("Inisialisasi browser...", "INFO")
        self.playwright = await async_playwright().start()

        launch_args = [
            '--disable-blink-features=AutomationControlled', 
            '--disable-dev-shm-usage',
            '--no-sandbox', 
            '--disable-setuid-sandbox', 
            '--disable-gpu', 
            '--disable-infobars',
            '--disable-extensions', 
            '--mute-audio', 
            '--no-first-run',
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless, 
            args=launch_args
        )

        context_options = self.stealth.get_random_fingerprint()
        self.context = await self.browser.new_context(
            **context_options,
            accept_downloads=True  # Enable download handling
        )

        if not fresh_session and self.cookies_file.exists():
            try:
                with open(self.cookies_file, 'r') as f:
                    await self.context.add_cookies(json.load(f))
                log_event("Cookie sesi lama dimuat", "INFO")
            except Exception as e:
                log_event(f"Gagal memuat cookie: {e}", "WARNING")

        self.page = await self.context.new_page()

        async def block_assets(route):
            if route.request.resource_type in ["image", "stylesheet", "font", "media"]: 
                await route.abort()
            else: 
                await route.continue_()
                
        await self.page.route("**/*", block_assets)
        self.page.set_default_timeout(60000)
        log_event("Browser berhasil diinisialisasi", "SUCCESS")

    async def save_cookies(self):
        try:
            cookies = await self.context.cookies()
            with open(self.cookies_file, 'w') as f: 
                json.dump(cookies, f)
        except Exception as e:
            log_event(f"Gagal menyimpan cookie: {e}", "WARNING")

    async def close_browser(self):
        if self.context: await self.save_cookies()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
        log_event("Browser ditutup", "INFO")

    async def detect_captcha(self) -> bool:
        captcha_selectors = [
            '#recaptcha', 'form[action*="captcha"]', '#captcha-form', 
            'div[aria-label*="reCAPTCHA"]', '.g-recaptcha', 'iframe[src*="recaptcha"]'
        ]
        for sel in captcha_selectors:
            if await self.page.query_selector(sel):
                return True
        return False

    async def human_mouse_movement(self, element=None):
        try:
            start_x, start_y = random.randint(100, 500), random.randint(100, 400)
            await self.page.mouse.move(start_x, start_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            if element:
                box = await element.bounding_box()
                if box:
                    target_x, target_y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
                    for _ in range(random.randint(3, 6)):
                        way_x = start_x + (target_x - start_x) * random.uniform(0.1, 0.9) + random.randint(-30, 30)
                        way_y = start_y + (target_y - start_y) * random.uniform(0.1, 0.9) + random.randint(-30, 30)
                        await self.page.mouse.move(way_x, way_y)
                        await asyncio.sleep(random.uniform(0.05, 0.15))
        except Exception as e:
            log_event(f"Error simulasi mouse: {e}", "WARNING")

    async def human_scroll(self):
        try:
            for _ in range(random.randint(2, 4)):
                await self.page.evaluate(f"window.scrollBy(0, {random.randint(200, 500)})")
                await asyncio.sleep(random.uniform(0.3, 0.7))
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.2, 0.5))
        except Exception as e:
            log_event(f"Error simulasi scroll: {e}", "WARNING")

    async def handle_captcha(self) -> bool:
        print("\n" + "!"*60)
        print("  [!] CAPTCHA / BOT DETECTION TERDETEKSI!")
        print("!"*60)
        if self.headless:
            print("  [-] Tidak bisa solve CAPTCHA di mode headless. Gunakan visible browser.")
            return False
        print("  [+] Browser terlihat. Silakan selesaikan CAPTCHA secara manual.")
        input("\n  [>] TEKAN ENTER SETELAH CAPTCHA SELESAI...")
        await asyncio.sleep(1)
        
        if await self.detect_captcha():
            print("  [-] CAPTCHA masih ada.")
            return False
        print("  [+] CAPTCHA berhasil dilewati!")
        return True

    # === SISTEM VALIDASI URL YANG ROBUST ===
    async def validate_urls(self, results: list) -> list:
        if not results:
            return results
            
        total = len(results)
        print(f"    Memvalidasi {total} URL...")
        
        # Semaphore untuk kontrol concurrency (5 concurrent untuk page navigation)
        semaphore = asyncio.Semaphore(5)
        
        async def check_with_progress(result, index):
            async with semaphore:
                status = await self._validate_single_url(result['url'])
                result['status'] = status
                
                # Update stats
                self.stats["urls_validated"] += 1
                if status in [200, 201, 202, 204, 206, 301, 302, 307, 308]:
                    self.stats["urls_alive"] += 1
                else:
                    self.stats["urls_dead"] += 1
                
                # Progress indicator
                if (index + 1) % 3 == 0 or index == total - 1:
                    print(f"      Progress: {index + 1}/{total} URL divalidasi")
                
                return result
        
        tasks = [check_with_progress(res, i) for i, res in enumerate(results)]
        validated = await asyncio.gather(*tasks)
        
        print(f"    ✓ Validasi selesai | Alive: {self.stats['urls_alive']} | Dead: {self.stats['urls_dead']}")
        return list(validated)
    
    async def _validate_single_url(self, url: str) -> int:
        """
        Validasi URL menggunakan actual page navigation dengan download handling
        """
        # Layer 1: Coba dengan HTTP request cepat
        status = await self._try_http_request(url, timeout=10000)
        
        # Jika status OK atau redirect, return langsung
        if status in [200, 201, 202, 204, 206, 301, 302, 307, 308]:
            return status
        
        # Layer 2: Jika 403/401/0, coba dengan actual page navigation
        # Ini akan handle kasus di mana server menolak HTTP request tapi browser bisa akses
        status = await self._try_page_navigation(url, timeout=15000)
        
        return status
    
    async def _try_http_request(self, url: str, timeout: int = 10000) -> int:
        """
        HTTP request cepat menggunakan context.request
        """
        try:
            response = await self.context.request.get(
                url,
                max_redirects=10,
                timeout=timeout,
                ignore_https_errors=True
            )
            return response.status
        except Exception:
            return 0
    
    async def _try_page_navigation(self, url: str, timeout: int = 15000) -> int:
        """
        Validasi menggunakan actual page navigation dengan download handling
        Ini akan menangkap kasus di mana 403 di HTTP tapi file bisa didownload via browser
        """
        temp_page = None
        try:
            # Buka page baru untuk validasi
            temp_page = await self.context.new_page()
            
            # Listen untuk download event
            download_triggered = False
            download_path = None
            
            async def handle_download(download):
                nonlocal download_triggered, download_path
                download_triggered = True
                # Save download ke temporary file
                download_path = await download.path()
            
            temp_page.on("download", handle_download)
            
            # Navigate ke URL
            response = await temp_page.goto(
                url,
                wait_until='commit',  # Jangan tunggu full load, cukup commit
                timeout=timeout
            )
            
            # Tunggu sebentar untuk melihat apakah ada download
            await asyncio.sleep(2)
            
            # Jika ada download, berarti file berhasil diakses
            if download_triggered:
                return 200
            
            # Jika tidak ada download, cek response status
            if response:
                status = response.status
                
                # Jika status 403 tapi page berhasil load (tidak ada error), 
                # kemungkinan file bisa diakses
                if status == 403:
                    # Cek apakah page menampilkan error atau konten valid
                    try:
                        content = await temp_page.content()
                        # Jika konten sangat kecil (< 1KB), kemungkinan error page
                        if len(content) < 1000:
                            return 403
                        # Jika konten besar, kemungkinan file berhasil diakses
                        else:
                            return 200
                    except:
                        return 403
                
                return status
            
            return 0
            
        except Exception as e:
            # Timeout atau error lain
            return 0
        finally:
            # Tutup temp page
            if temp_page:
                try:
                    await temp_page.close()
                except:
                    pass

    async def extract_results(self) -> list:
        results = []
        for elem in await self.page.query_selector_all('div.g, div[data-hveid]'):
            try:
                title_elem = await elem.query_selector('h3')
                if not title_elem: continue
                title = (await title_elem.inner_text()).strip()
                
                link_elem = await elem.query_selector('a')
                if not link_elem: continue
                link = (await link_elem.get_attribute('href') or "").strip()
                
                if not link or 'google.com' in link or link.startswith('/'): continue
                if link in self.seen_urls: continue
                
                self.seen_urls.add(link)
                snippet_elem = await elem.query_selector('div.VwiC3b, span.aCOpRe')
                snippet = (await snippet_elem.inner_text()).strip()[:500] if snippet_elem else ""
                
                results.append({"judul": title, "url": link, "deskripsi": snippet, "status": 0})
            except Exception as e:
                log_event(f"Error ekstraksi elemen: {e}", "WARNING")
                continue
        return results

    async def search_page(self, query: str, page_num: int) -> list:
        url = f"https://www.google.com/search?q={query}&start={(page_num - 1) * 10}&hl=en"
        print(f"  Mengambil halaman {page_num}...", end=" ", flush=True)
        self.stats["total_requests"] += 1

        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(self.delay + random.uniform(0.5, 1.5))
            
            await self.human_scroll()
            
            if await self.detect_captcha():
                print("BLOCKED!")
                self.stats["captcha_encounters"] += 1
                if not await self.handle_captcha(): return []
                await self.page.reload(wait_until='domcontentloaded')
                await asyncio.sleep(2)

            await self.page.wait_for_selector('div#search, div[data-hveid]', timeout=10000)
            results = await self.extract_results()
            
            # Validasi URL
            if results:
                results = await self.validate_urls(results)
                
            self.stats["successful_requests"] += 1
            print(f"OK ({len(results)} hasil baru)")
            return results
        except Exception as e:
            print(f"ERROR: {e}")
            return []

    async def execute_query(self, query: str, min_page: int, max_page: int) -> list:
        all_results = []
        for page_num in range(min_page, max_page + 1):
            all_results.extend(await self.search_page(query, page_num))
            if page_num < max_page: 
                await asyncio.sleep(self.delay + random.uniform(0.5, 1.5))
        return all_results

    def save_json(self, filepath: str, data: list):
        if not filepath.endswith('.json'): filepath += '.json'
        output_path = Path(filepath).resolve()
        with open(output_path, 'w', encoding='utf-8') as f: 
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(output_path.absolute())

    def print_stats(self):
        print("\n" + "="*60)
        print("  STATISTIK SESI")
        print("="*60)
        for k, v in self.stats.items(): 
            print(f"  {k.replace('_', ' ').title()}: {v}")
        print("="*60)

# === MODE HANDLERS ===
async def interactive_mode():
    print("\n" + "=" * 60)
    print("  MODE INTERAKTIF - Single Query")
    print("=" * 60)
    site = input("\n[1] Site Filter (contoh: go.id): ").strip() or None
    keywords = input("[2] Keywords (pisah dengan spasi): ").strip().split() or None
    filetype = input("[3] File Type (pdf, xlsx, dll): ").strip() or None
    min_page = get_int_input("[4] Halaman Awal (1-10) [1]: ", 1, 10, 1)
    max_page = get_int_input(f"[5] Halaman Akhir ({min_page}-10) [{min_page}]: ", min_page, 10, min_page)
    visible = input("[6] Tampilkan Browser? (y/N): ").strip().lower() == 'y'
    delay = get_float_input("[7] Delay antar halaman (detik) [2.0]: ", 0.5, 2.0)
    output_file = input("[8] Nama file output [hasil_dorking.json]: ").strip() or "hasil_dorking.json"

    query = sanitize_query(GoogleDorker().build_query(site=site, keywords=keywords, filetype=filetype))
    print(f"\n  Query: {query} | Halaman: {min_page}-{max_page}")
    
    dorker = GoogleDorker(headless=not visible, delay=delay)
    await dorker.init_browser()
    try:
        all_results = await dorker.execute_query(query, min_page, max_page)
        print(f"\n  DITEMUKAN {len(all_results)} HASIL UNIK")
        save_path = dorker.save_json(output_file, [{"query": query, "total_results": len(all_results), "data": all_results}])
        print(f"\n[Tersimpan] {save_path}")
        dorker.print_stats()
    finally:
        await dorker.close_browser()


async def bulk_mode():
    print("\n" + "=" * 60)
    print("  MODE BULK - Multiple Payloads dari .txt")
    print("=" * 60)
    
    print("\n[1] Path ke file .txt (satu query per baris, pakai # untuk komentar):")
    file_path = input("  > ").strip()
    
    if not os.path.exists(file_path):
        print(f"  ERROR: File tidak ditemukan -> {file_path}")
        return
        
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_queries = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        
    if not raw_queries:
        print("  ERROR: Tidak ada query valid di file.")
        return
        
    queries = [sanitize_query(q) for q in raw_queries]
    print(f"\n  Loaded {len(queries)} payload (Syntax auto-sanitized).")
    
    print("\n[2] Halaman Awal (1-10) [default 1]:")
    min_page = get_int_input("  > ", 1, 10, 1)

    print(f"\n[3] Halaman Akhir ({min_page}-10) [default {min_page}]:")
    max_page = get_int_input("  > ", min_page, 10, min_page)

    print("\n[4] Tampilkan Browser? (y/N) [default N]:")
    print("  (Pilih 'y' kalau mau solve CAPTCHA manual)")
    visible = input("  > ").strip().lower() == 'y'

    print("\n[5] Delay antar halaman (detik) [default 2.0]:")
    delay = get_float_input("  > ", 0.5, 2.0)

    print("\n[6] Nama file output [default hasil_bulk.json]:")
    output_file = input("  > ").strip() or "hasil_bulk.json"

    print("\nInisialisasi browser...")
    dorker = GoogleDorker(headless=not visible, delay=delay)
    await dorker.init_browser()
    
    bulk_data = []
    total_found = 0
    
    try:
        for i, query in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"  [{i}/{len(queries)}] Eksekusi: {query}")
            print(f"{'='*60}")
            
            results = await dorker.execute_query(query, min_page, max_page)
            total_found += len(results)
            
            bulk_data.append({
                "query": query,
                "total_results": len(results),
                "data": results
            })
            
            if i < len(queries):
                wait_time = delay * 2 + random.uniform(2.0, 5.0)
                print(f"  Cooldown {wait_time:.1f}s sebelum payload berikutnya...")
                await asyncio.sleep(wait_time)
                
        print("\n" + "=" * 60)
        print(f"  BULK SELESAI | TOTAL HASIL UNIK: {total_found}")
        print("=" * 60)
        
        save_path = dorker.save_json(output_file, bulk_data)
        print(f"\n[Tersimpan] {save_path}")
        dorker.print_stats()
    finally:
        await dorker.close_browser()


async def main_menu():
    print("=" * 60)
    print("  GOOGLE DORKING CLI")
    print("=" * 60)
    print("\nPilih Mode:")
    print("[1] Mode Interaktif (Single Query)")
    print("[2] Mode Bulk (Multiple Queries dari .txt)")
    print("[3] Keluar")
    
    choice = input("\nMasukkan pilihan (1/2/3): ").strip()
    
    if choice == '2':
        await bulk_mode()
    elif choice == '1':
        await interactive_mode()
    else:
        print("Keluar...")

if __name__ == "__main__":
    asyncio.run(main_menu())