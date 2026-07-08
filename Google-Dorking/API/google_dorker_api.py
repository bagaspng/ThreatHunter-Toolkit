"""
Google Dorking Tool - SearchAPI.io Version
Uses Google Search API via SearchAPI.io (no blocking)
"""

import json
import sys
import argparse
import os
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


class GoogleDorkerSearchAPI:
    """Google Dorking using SearchAPI.io"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("SEARCHAPI_KEY")
        if not self.api_key:
            raise ValueError("SearchAPI.io key required. Set SEARCHAPI_KEY env var or use -a argument")
        self.results = []

    def build_query(self, site: str = None, keywords: list = None, filetype: str = "pdf") -> str:
        parts = []
        if site:
            parts.append(f"site:{site}")
        if keywords:
            parts.append(", ".join(keywords))
        if filetype:
            parts.append(f"filetype:{filetype}")
        return " ".join(parts)

    def search(self, query: str, max_results: int = 100) -> list:
        """Search using SearchAPI.io Google Search"""
        self.results = []
        num_results = min(max_results, 100)

        url = "https://www.searchapi.io/api/v1/search"
        params = {
            "api_key": self.api_key,
            "engine": "google",
            "q": query,
            "num": num_results
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse organic results
            organic_results = data.get("organic_results", [])

            for result in organic_results:
                self.results.append({
                    "judul": result.get("title", ""),
                    "url": result.get("link", ""),
                    "deskripsi": result.get("snippet", "")[:500] if result.get("snippet") else ""
                })

        except requests.RequestException as e:
            print(f"Error: {e}")
            print("Check your SearchAPI.io key and quota.")
        except json.JSONDecodeError:
            print("Error parsing response.")

        return self.results

    def save_json(self, filepath: str = None):
        if not filepath:
            filepath = "dorking_results.json"
        output_path = Path(filepath).resolve()
        safe_dir = Path.cwd().resolve()
        if not str(output_path).startswith(str(safe_dir)):
            raise ValueError('Output path outside safe directory')
        fd = os.open(str(output_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"Results saved to: {output_path.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="Google Dorking via SearchAPI.io (No blocking, requires API key)"
    )
    parser.add_argument("-s", "--site", default="go.id", help="Site to search")
    parser.add_argument("-k", "--keywords", nargs="+", default=["NAMA", "NIK"], help="Keywords")
    parser.add_argument("-t", "--filetype", default="pdf", help="File type")
    parser.add_argument("-m", "--max", type=int, default=10, help="Max results")
    parser.add_argument("-o", "--output", default="dorking_results.json", help="Output file")
    parser.add_argument("-a", "--api-key", default=None, help="SearchAPI.io key (or set SEARCHAPI_KEY env)")

    args = parser.parse_args()

    try:
        dorker = GoogleDorkerSearchAPI(api_key=args.api_key)
    except ValueError as e:
        print(f"Error: {e}")
        print("\nGet your SearchAPI.io key at: https://www.searchapi.io/")
        print("Then either:")
        print("  1. Set environment: set SEARCHAPI_KEY=your_key")
        print("  2. Use argument:   python google_dorker_api.py -a your_key")
        sys.exit(1)

    query = dorker.build_query(site=args.site, keywords=args.keywords, filetype=args.filetype)

    print("=" * 60)
    print("Google Dorking Tool (SearchAPI.io Version)")
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
            if r['deskripsi']:
                print(f"   Snippet: {r['deskripsi'][:100]}...")
            print()
        dorker.save_json(args.output)
    else:
        print("No results found.")


if __name__ == "__main__":
    main()
