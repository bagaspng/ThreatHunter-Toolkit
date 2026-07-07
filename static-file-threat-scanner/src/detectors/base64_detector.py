from __future__ import annotations

import base64
import binascii
import re

from src.core.entropy import calculate_entropy
from src.core.models import Indicator
from src.core.scoring import make_indicator


BASE64_REGEX = re.compile(
    rb"(?<![A-Za-z0-9+/])"
    rb"(?:[A-Za-z0-9+/]{80,}={0,2})"
    rb"(?![A-Za-z0-9+/])"
)


def detect_base64_strings(
    file_bytes: bytes,
    min_length: int = 120,
    max_reported: int = 5,
) -> list[Indicator]:
    candidates = extract_base64_candidates(
        file_bytes=file_bytes,
        min_length=min_length,
        limit=max_reported,
    )

    if not candidates:
        return []

    suspicious_candidates = []

    for item in candidates:
        decoded_preview = item.get("decoded_preview", b"")

        if decoded_preview.startswith((b"MZ", b"PK\x03\x04", b"dex\n", b"%PDF")):
            suspicious_candidates.append(item)
            continue

        lower_preview = decoded_preview.lower()

        if any(
            keyword in lower_preview
            for keyword in [
                b"<script",
                b"javascript:",
                b"powershell",
                b"cmd.exe",
                b"androidmanifest.xml",
                b"classes.dex",
            ]
        ):
            suspicious_candidates.append(item)

    if suspicious_candidates:
        strongest = max(suspicious_candidates, key=lambda item: item["length"])

        return [
            make_indicator(
                name="Suspicious Base64 Payload Found",
                category="obfuscation",
                severity="high",
                score=20,
                description=(
                    "Ditemukan base64 panjang yang setelah didecode memiliki indikasi payload "
                    "atau script mencurigakan."
                ),
                evidence=(
                    f"offset={strongest['offset']}, "
                    f"length={strongest['length']}, "
                    f"entropy={strongest['entropy']}"
                ),
                offset=strongest["offset"],
                source="detectors.base64_detector",
            )
        ]

    longest = max(candidates, key=lambda item: item["length"])

    return [
        make_indicator(
            name="Long Base64-Like String Found",
            category="obfuscation",
            severity="low",
            score=0,
            description=(
                "Ditemukan string panjang menyerupai base64, tetapi belum ditemukan "
                "indikasi payload berbahaya dari preview decode. Dicatat sebagai informasi."
            ),
            evidence=(
                f"offset={longest['offset']}, "
                f"length={longest['length']}, "
                f"entropy={longest['entropy']}"
            ),
            offset=longest["offset"],
            source="detectors.base64_detector",
        )
    ]


def extract_base64_candidates(
    file_bytes: bytes,
    min_length: int = 80,
    limit: int = 10,
) -> list[dict]:
    """
    Mengambil kandidat string base64.

    Return:
    [
        {
            "offset": 123,
            "length": 200,
            "entropy": 5.9,
            "sample": "AAAA..."
        }
    ]
    """

    candidates: list[dict] = []

    for match in BASE64_REGEX.finditer(file_bytes):
        raw = match.group(0)

        if len(raw) < min_length:
            continue

        if not looks_like_valid_base64(raw):
            continue

        decoded_preview = try_decode_base64(raw)

        entropy = calculate_entropy(raw)

        candidates.append(
            {
                "offset": match.start(),
                "length": len(raw),
                "entropy": entropy,
                "sample": raw[:80].decode("utf-8", errors="replace"),
                "decoded_preview_size": len(decoded_preview) if decoded_preview else 0,
                "decoded_preview": decoded_preview or b"",
            }
        )

        if len(candidates) >= limit:
            break

    return candidates


def looks_like_valid_base64(value: bytes) -> bool:
    """
    Validasi ringan untuk mengurangi false positive.

    Catatan:
    Banyak data random juga bisa terlihat seperti base64.
    Jadi ini hanya indikator, bukan bukti malware.
    """

    if not value:
        return False

    # Base64 umumnya panjangnya kelipatan 4.
    padding_needed = (-len(value)) % 4
    padded = value + (b"=" * padding_needed)

    try:
        base64.b64decode(padded, validate=True)
        return True
    except (binascii.Error, ValueError):
        return False


def try_decode_base64(value: bytes, max_decode_size: int = 4096) -> bytes | None:
    """
    Decode base64 secara aman untuk preview ukuran kecil.

    Tidak menulis hasil decode ke disk.
    Tidak menjalankan hasil decode.
    """

    padding_needed = (-len(value)) % 4
    padded = value + (b"=" * padding_needed)

    try:
        decoded = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None

    return decoded[:max_decode_size]