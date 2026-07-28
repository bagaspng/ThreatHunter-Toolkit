"""
Solusi Masalah 1: Multi-Source Aggregator

Strategi: jangan bergantung pada satu list.
Ambil dari 6+ sumber berbeda secara paralel, deduplikasi by IP:port,
lalu lempar semua ke ProxyValidator.

Sumber dipilih berdasarkan format JSON (bisa di-parse langsung)
atau plaintext (IP:PORT per baris) — keduanya di-handle di sini.
"""

import asyncio
import logging
import re
from typing import Literal

import aiohttp

logger = logging.getLogger("proxyforge.aggregator")

# ── Katalog sumber ─────────────────────────────────────────────────────────────
# format: "json" → list of dict dengan field proxy/ip/port
#         "text" → plaintext IP:PORT per baris
SOURCES: list[dict] = [
    {
        "name":   "proxifly-all",
        "url":    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json",
        "format": "json",
    },
    {
        "name":   "proxifly-socks5",
        "url":    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.json",
        "format": "json",
    },
    {
        "name":   "proxifly-elite",
        "url":    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/anonymity/elite/data.json",
        "format": "json",
    },
    {
        "name":   "TheSpeedX-socks5",
        "url":    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "format": "text",
        "protocol": "socks5",
    },
    {
        "name":   "TheSpeedX-http",
        "url":    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "format": "text",
        "protocol": "http",
    },
    {
        "name":   "hookzof-socks5",
        "url":    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "format": "text",
        "protocol": "socks5",
    },
    {
        "name":   "monosans-http",
        "url":    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "format": "text",
        "protocol": "http",
    },
    {
        "name":   "monosans-socks5",
        "url":    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "format": "text",
        "protocol": "socks5",
    },
]

# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse_json(raw: list) -> list[dict]:
    """Parse format Proxifly: list of dict dengan field proxy, ip, port, anonymity."""
    result = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        proxy = entry.get("proxy", "")
        ip    = entry.get("ip", "")
        port  = entry.get("port")
        if not (proxy and ip and port):
            continue
        result.append({
            "proxy":     proxy,
            "ip":        ip,
            "port":      int(port),
            "protocol":  entry.get("protocol", "socks5"),
            "anonymity": entry.get("anonymity", "unknown"),
        })
    return result


def _parse_text(text: str, protocol: str) -> list[dict]:
    """
    Parse format plaintext: satu IP:PORT per baris.
    Baris kosong dan komentar (#) diabaikan.
    """
    pattern = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})$")
    result  = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = pattern.match(line)
        if not m:
            continue
        ip, port = m.group(1), int(m.group(2))
        result.append({
            "proxy":     f"{protocol}://{ip}:{port}",
            "ip":        ip,
            "port":      port,
            "protocol":  protocol,
            "anonymity": "unknown",   # plaintext list tidak menyertakan info ini
        })
    return result


# ── Fetcher async ──────────────────────────────────────────────────────────────

async def _fetch_source(
    session: aiohttp.ClientSession,
    source:  dict,
) -> list[dict]:
    """Fetch satu sumber; return list entry yang sudah di-parse."""
    try:
        async with session.get(source["url"], timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.warning("[%s] HTTP %d — skip", source["name"], resp.status)
                return []

            if source["format"] == "json":
                raw    = await resp.json(content_type=None)
                parsed = _parse_json(raw)
            else:
                text   = await resp.text()
                parsed = _parse_text(text, source.get("protocol", "http"))

            logger.info("[%s] %d entries", source["name"], len(parsed))
            return parsed

    except Exception as exc:
        logger.warning("[%s] fetch error: %s", source["name"], exc)
        return []


# ── Deduplicator ───────────────────────────────────────────────────────────────

def deduplicate(entries: list[dict]) -> list[dict]:
    """
    Deduplikasi berdasarkan ip:port.
    Jika IP yang sama muncul dari dua sumber, simpan yang memiliki
    anonymity lebih tinggi (elite > anonymous > unknown > transparent).
    """
    rank = {"elite": 3, "anonymous": 2, "unknown": 1, "transparent": 0}
    best: dict[str, dict] = {}

    for entry in entries:
        key     = f"{entry['ip']}:{entry['port']}"
        current = best.get(key)
        if current is None:
            best[key] = entry
        else:
            if rank.get(entry["anonymity"], 0) > rank.get(current["anonymity"], 0):
                best[key] = entry

    return list(best.values())


# ── Orchestrator ───────────────────────────────────────────────────────────────

async def aggregate(sources: list[dict] | None = None) -> list[dict]:
    """
    Fetch semua sumber secara paralel, parse, deduplikasi.
    Return: list[dict] siap masuk ProxyValidator.validate_all()
    """
    sources = sources or SOURCES
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks   = [_fetch_source(session, src) for src in sources]
        batches = await asyncio.gather(*tasks)

    all_entries = [entry for batch in batches for entry in batch]
    unique      = deduplicate(all_entries)

    logger.info(
        "Aggregated: %d total → %d unique (from %d sources)",
        len(all_entries), len(unique), len(sources),
    )
    return unique