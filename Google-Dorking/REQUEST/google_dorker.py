import json
import time
import sys
import os
import argparse
from urllib.parse import quote_plus
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


class GoogleDorker:

    def __init__(self, delay: float = 2.0):
        self.delay = delay
        self.results = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def build_query(self, site: str = None, keywords: list = None, filetype: str = "pdf") -> str:
        parts = []

        if site:
            parts.append(f"site:{site}")

        if keywords:
            parts.append(", ".join(keywords))

        if filetype:
            parts.append(f"filetype:{filetype}")

        return " ".join(parts)

    def search(self, query: str, max_results: int = 20) -> list:
        self.results = []
        start = 0

        while len(self.results) < max_results:
            url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}"

            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
            except requests.RequestException as e:
                print(f"Error fetching: {e}")
                break

            results = self._parse_html(response.text)
            if not results:
                break

            self.results.extend(results)

            if len(results) < 10:  # hasil kurang dari 10 berarti udah halaman terakhir
                break

            start += 10
            time.sleep(self.delay)  # jeda biar ga langsung diblok google

        return self.results[:max_results]

    def _parse_html(self, html: str) -> list:
        results = []
        import re

        # class google (BNE6kD/MjjYud) suka ganti-ganti, jadi regex-nya longgar
        result_blocks = re.findall(
            r'<div class="[^"]*BNE6kD[^"]*|'
            r'<div class="[^"]*MjjYud[^"]*'
            r'.*?<a href="(https?://[^"]+)"[^>]*>.*?'
            r'<h3[^>]*>([^<]+)</h3>'
            r'.*?<span[^>]*>([^<]{20,500}?)(?=</span>|</div>)',
            html,
            re.DOTALL
        )

        for url, judul, deskripsi in result_blocks:
            judul = self._clean_text(judul)
            deskripsi = self._clean_text(deskripsi)
            url = url.split('&')[0].split('?')[0]  # buang tracking param dari url

            if url and judul:
                results.append({
                    "judul": judul,
                    "url": url,
                    "deskripsi": deskripsi[:500] if deskripsi else ""
                })

        return results

    def _clean_text(self, text: str) -> str:
        import re
        text = re.sub(r'<[^>]+>', '', text)  # buang tag html
        text = ' '.join(text.split())  # rapiin spasi berlebih
        # balikin entity html ke karakter aslinya
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&#39;', "'").replace('&quot;', '"')
        return text.strip()

    def save_json(self, filepath: str = None):
        if not filepath:
            filepath = "dorking_results.json"

        # pastiin nulis di dalam folder kerja, jangan sampai kena path traversal
        output_path = Path(filepath).resolve()
        safe_dir = Path.cwd().resolve()

        if not str(output_path).startswith(str(safe_dir)):
            raise ValueError('Output path outside safe directory')

        # 0o600 = cuma owner yang bisa baca/tulis
        fd = os.open(str(output_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"Results saved to: {output_path.absolute()}")
        print(f"Total results: {len(self.results)}")


def main():
    parser = argparse.ArgumentParser(
        description="Google Dorking Tool - Find exposed documents"
    )
    parser.add_argument(
        "-s", "--site",
        default="go.id",
        help="Site to search (default: go.id)"
    )
    parser.add_argument(
        "-k", "--keywords",
        nargs="+",
        default=["NAMA", "NIK"],
        help="Keywords to search (default: NAMA NIK)"
    )
    parser.add_argument(
        "-t", "--filetype",
        default="pdf",
        help="File type filter (default: pdf)"
    )
    parser.add_argument(
        "-m", "--max",
        type=int,
        default=20,
        help="Max results to fetch (default: 20)"
    )
    parser.add_argument(
        "-o", "--output",
        default="dorking_results.json",
        help="Output JSON file (default: dorking_results.json)"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=2.0,
        help="Delay between requests in seconds (default: 2.0)"
    )

    args = parser.parse_args()

    dorker = GoogleDorker(delay=args.delay)
    query = dorker.build_query(site=args.site, keywords=args.keywords, filetype=args.filetype)

    print("=" * 60)
    print("Google Dorking Tool")
    print("=" * 60)
    print(f"Query: {query}")
    print(f"Max results: {args.max}")
    print("-" * 60)

    results = dorker.search(query, max_results=args.max)

    if results:
        print(f"\nFound {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['judul'][:60]}...")
            print(f"   URL: {r['url']}")
            print()

        dorker.save_json(args.output)
    else:
        print("No results found. Google may be blocking automated requests.")
        print("Consider using a proxy or SerpAPI for production use.")


if __name__ == "__main__":
    main()
