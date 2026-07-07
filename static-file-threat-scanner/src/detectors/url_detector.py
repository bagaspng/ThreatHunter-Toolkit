from __future__ import annotations

import re

from src.core.models import Indicator
from src.core.scoring import make_indicator


URL_REGEX = re.compile(
    rb"https?://[^\s'\"<>)}\]]{4,}",
    re.IGNORECASE,
)

IP_REGEX = re.compile(
    rb"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
    rb"(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)

DOMAIN_REGEX = re.compile(
    rb"\b(?:[a-zA-Z0-9-]{1,63}\.)+"
    rb"(?:com|net|org|id|co|io|xyz|top|site|online|info|biz|ru|cn)\b",
    re.IGNORECASE,
)

SHORTENER_KEYWORDS = (
    b"bit.ly",
    b"tinyurl.com",
    b"t.co",
    b"goo.gl",
    b"cutt.ly",
    b"shorturl.at",
    b"s.id",
)


def detect_network_indicators(
    file_bytes: bytes,
    max_items: int = 10,
) -> list[Indicator]:
    """
    Mendeteksi indikator jaringan:
    - URL
    - IP address
    - domain
    - URL shortener

    URL/domain tidak otomatis berarti malware.
    Namun pada PDF/SVG/gambar, ini bisa menjadi indikator phishing,
    tracking, downloader, atau komunikasi keluar.
    """

    indicators: list[Indicator] = []

    urls = extract_urls(file_bytes, limit=max_items)
    ips = extract_ip_addresses(file_bytes, limit=max_items)
    domains = extract_domains(file_bytes, limit=max_items)
    shorteners = detect_url_shorteners(file_bytes)

    if urls:
        indicators.append(
            make_indicator(
                name="URL Found",
                category="network_indicator",
                severity="medium",
                score=10,
                description=(
                    "Ditemukan URL di dalam file. URL dapat menjadi indikator hyperlink, "
                    "phishing, downloader, atau komunikasi keluar."
                ),
                evidence=" | ".join(urls[:max_items]),
                source="detectors.url_detector",
            )
        )

    if ips:
        indicators.append(
            make_indicator(
                name="IP Address Found",
                category="network_indicator",
                severity="low",
                score=5,
                description=(
                    "Ditemukan alamat IP di dalam file. Ini dapat berkaitan dengan koneksi jaringan."
                ),
                evidence=", ".join(ips[:max_items]),
                source="detectors.url_detector",
            )
        )

    if domains:
        indicators.append(
            make_indicator(
                name="Domain Found",
                category="network_indicator",
                severity="low",
                score=5,
                description=(
                    "Ditemukan domain di dalam file. Domain tidak selalu berbahaya, "
                    "tetapi tetap berguna sebagai indikator analisis."
                ),
                evidence=", ".join(domains[:max_items]),
                source="detectors.url_detector",
            )
        )

    if shorteners:
        indicators.append(
            make_indicator(
                name="URL Shortener Found",
                category="network_indicator",
                severity="medium",
                score=10,
                description=(
                    "Ditemukan layanan pemendek URL. Ini sering dipakai untuk menyamarkan "
                    "tujuan link, walaupun tidak selalu berbahaya."
                ),
                evidence=", ".join(shorteners),
                source="detectors.url_detector",
            )
        )

    return indicators


def extract_urls(file_bytes: bytes, limit: int = 20) -> list[str]:
    matches = URL_REGEX.findall(file_bytes)
    return _unique_decoded(matches, limit=limit)


def extract_ip_addresses(file_bytes: bytes, limit: int = 20) -> list[str]:
    matches = IP_REGEX.findall(file_bytes)
    return _unique_decoded(matches, limit=limit)


def extract_domains(file_bytes: bytes, limit: int = 20) -> list[str]:
    matches = DOMAIN_REGEX.findall(file_bytes)

    # Hindari domain yang sudah muncul sebagai bagian URL.
    return _unique_decoded(matches, limit=limit)


def detect_url_shorteners(file_bytes: bytes) -> list[str]:
    lower_bytes = file_bytes.lower()

    found: list[str] = []

    for keyword in SHORTENER_KEYWORDS:
        if keyword in lower_bytes:
            found.append(keyword.decode("utf-8", errors="replace"))

    return sorted(set(found))


def _unique_decoded(values: list[bytes], limit: int = 20) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()

    for value in values:
        decoded = value.decode("utf-8", errors="replace").strip()

        decoded = decoded.rstrip(".,;:!?)\"]}'")

        if not decoded:
            continue

        if decoded in seen:
            continue

        seen.add(decoded)
        results.append(decoded)

        if len(results) >= limit:
            break

    return results