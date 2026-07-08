import json
import asyncio
import os
import sys
import io
from pathlib import Path

# tanpa ini emoji/karakter aneh bikin error di console windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Installing playwright...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    from playwright.async_api import async_playwright


class GoogleDorkerInteractive:

    def __init__(self, headless: bool = True, delay: float = 2.0):
        self.headless = headless
        self.delay = delay
        self.results = []
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def build_query(self, site: str = None, keywords: list = None, filetype: str = None) -> str:
        parts = []
        if site:
            parts.append(f"site:{site}")
        if keywords:
            parts.append(" ".join(keywords))
        if filetype:
            parts.append(f"filetype:{filetype}")
        return " ".join(parts)

    async def init_browser(self):
        # browser mode stealth biar ga langsung dicap bot sama google
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        self.page = await self.context.new_page()

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def search_page(self, query: str, page_num: int) -> list:
        # google pakai param start buat pagination, tiap halaman lompat 10
        start = (page_num - 1) * 10
        url = f"https://www.google.com/search?q={query}&start={start}"

        print(f"  Fetching page {page_num}...", end=" ", flush=True)

        try:
            await self.page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(self.delay)

            # kalau google curiga, dia lempar captcha. berhenti aja
            if await self.page.query_selector('#recaptcha, form[action*="captcha"]'):
                print("BLOCKED!")
                return []

            await self.page.wait_for_selector('div#search, div[data-hveid]', timeout=5000)
            results = await self._extract_results()
            print(f"OK ({len(results)} results)")
            return results

        except Exception as e:
            print(f"ERROR: {e}")
            return []

    async def _extract_results(self) -> list:
        results = []
        result_elements = await self.page.query_selector_all('div.g, div[data-hveid]')

        for elem in result_elements:
            try:
                title_elem = await elem.query_selector('h3')
                if not title_elem:
                    continue
                title = await title_elem.inner_text()

                link_elem = await elem.query_selector('a')
                if not link_elem:
                    continue
                link = await link_elem.get_attribute('href')
                if not link or 'google.com' in link or link.startswith('/'):
                    continue

                snippet_elem = await elem.query_selector('div.VwiC3b, span.aCOpRe')
                snippet = await snippet_elem.inner_text() if snippet_elem else ""

                results.append({
                    "judul": title.strip(),
                    "url": link,
                    "deskripsi": snippet.strip()[:500]
                })
            except Exception:
                continue

        return results

    def save_json(self, filepath: str = None, all_results: bool = False, page_results: list = None):
        if all_results:
            data = self.results
        else:
            data = page_results if page_results else self.results

        if not filepath:
            filepath = "dorking_results.json"

        output_path = Path(filepath).resolve()
        safe_dir = Path.cwd().resolve()
        if not str(output_path).startswith(str(safe_dir)):
            raise ValueError('Output path outside safe directory')

        fd = os.open(str(output_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return str(output_path.absolute())


async def interactive_search():
    dorker = GoogleDorkerInteractive()

    print("=" * 60)
    print("  GOOGLE DORKING TOOL - Interactive CLI")
    print("=" * 60)

    # tanya-tanya ke user dulu
    print("\n[1] Site Filter (e.g., go.id, or press Enter for all):")
    site = input("  > ").strip() or None

    print("\n[2] Keywords (e.g., NAMA NIK, separate with space):")
    keywords_input = input("  > ").strip()
    keywords = keywords_input.split() if keywords_input else None

    print("\n[3] File Type (pdf, xlsx, doc, etc, or press Enter for all):")
    filetype = input("  > ").strip() or None

    print("\n[4] Minimum Page:")
    while True:
        try:
            min_page = int(input("  > (1-10): ").strip() or "1")
            if 1 <= min_page <= 10:
                break
            print("  Must be between 1-10")
        except ValueError:
            min_page = 1
            break

    print("\n[5] Maximum Page:")
    while True:
        try:
            max_page = int(input(f"  > ({min_page}-10): ").strip() or str(min_page))
            if min_page <= max_page <= 10:
                break
            print(f"  Must be between {min_page}-10")
        except ValueError:
            max_page = min_page
            break

    print("\n[6] Visible Browser? (y/N):")
    visible = input("  > ").strip().lower() == 'y'
    dorker.headless = not visible

    print("\n[7] Delay between pages (seconds):")
    while True:
        try:
            delay = float(input("  > (default 2.0): ").strip() or "2.0")
            if delay >= 0.5:
                break
            print("  Minimum 0.5 seconds")
        except ValueError:
            delay = 2.0
            break
    dorker.delay = delay

    print("\n[8] Output file (default: dorking_results.json):")
    output_file = input("  > ").strip() or "dorking_results.json"

    query = dorker.build_query(site=site, keywords=keywords, filetype=filetype)

    print("\n" + "=" * 60)
    print("  SEARCH CONFIGURATION")
    print("=" * 60)
    print(f"  Query    : {query}")
    print(f"  Pages    : {min_page} - {max_page}")
    print(f"  Results  : ~{(max_page - min_page + 1) * 10} max")
    print("=" * 60)

    print("\nInitializing browser...")
    await dorker.init_browser()

    try:
        # gilir tiap halaman dari min sampai max
        all_results = []
        for page_num in range(min_page, max_page + 1):
            results = await dorker.search_page(query, page_num)
            all_results.extend(results)
            await asyncio.sleep(dorker.delay)

        dorker.results = all_results

        print("\n" + "=" * 60)
        print(f"  FOUND {len(all_results)} TOTAL RESULTS")
        print("=" * 60)

        if all_results:
            for i, r in enumerate(all_results, 1):
                try:
                    print(f"\n{i}. {r['judul'][:70]}...")
                    print(f"   URL: {r['url']}")
                    if r['deskripsi']:
                        snippet = r['deskripsi'][:100].encode('utf-8', errors='replace').decode('utf-8')
                        print(f"   {snippet}...")
                except Exception:
                    pass

        save_path = dorker.save_json(output_file, all_results=True)
        print(f"\n[Saved] {save_path}")

    finally:
        await dorker.close_browser()


if __name__ == "__main__":
    asyncio.run(interactive_search())
