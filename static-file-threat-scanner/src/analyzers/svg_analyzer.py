from __future__ import annotations

from pathlib import Path
import re

from src.core.models import FileInfo, Indicator
from src.core.scoring import make_indicator


SCRIPT_TAG_REGEX = re.compile(r"<\s*script\b", re.IGNORECASE)
EVENT_HANDLER_REGEX = re.compile(r"\son[a-zA-Z]+\s*=", re.IGNORECASE)
JAVASCRIPT_URI_REGEX = re.compile(r"javascript\s*:", re.IGNORECASE)
DATA_URI_REGEX = re.compile(r"data\s*:[^\"']+", re.IGNORECASE)
BASE64_TEXT_REGEX = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")
EXTERNAL_REF_REGEX = re.compile(
    r"(?:href|xlink:href|src)\s*=\s*['\"]\s*https?://",
    re.IGNORECASE,
)

SVG_RISKY_TAGS = [
    "foreignObject",
    "iframe",
    "object",
    "embed",
]


def analyze(
    file_path: str | Path,
    file_bytes: bytes,
    file_info: FileInfo,
) -> list[Indicator]:
    """
    SVG analyzer.

    SVG berbeda dari PNG/JPEG karena SVG adalah XML/text.
    Ia bisa mengandung script, event handler, external reference, dan data URI.

    File tidak dijalankan.
    File hanya dibaca sebagai teks dan diparse secara aman jika defusedxml tersedia.
    """

    indicators: list[Indicator] = []

    text = _decode_svg_text(file_bytes)

    indicators.extend(_check_svg_basic_structure(text, file_info))
    indicators.extend(_safe_xml_parse_check(text))
    indicators.extend(_detect_script_tag(text))
    indicators.extend(_detect_event_handlers(text))
    indicators.extend(_detect_javascript_uri(text))
    indicators.extend(_detect_external_references(text))
    indicators.extend(_detect_risky_tags(text))
    indicators.extend(_detect_data_uri_and_base64(text))

    return indicators


def _decode_svg_text(file_bytes: bytes) -> str:
    """
    Decode SVG sebagai text.

    errors='replace' dipakai agar scanner tidak gagal saat menemukan karakter rusak.
    """

    if file_bytes.startswith(b"\xef\xbb\xbf"):
        file_bytes = file_bytes[3:]

    return file_bytes.decode("utf-8", errors="replace")


def _check_svg_basic_structure(
    text: str,
    file_info: FileInfo,
) -> list[Indicator]:
    stripped = text.lstrip("\ufeff").strip().lower()

    if stripped.startswith("<svg") or (stripped.startswith("<?xml") and "<svg" in stripped):
        return []

    return [
        make_indicator(
            name="Invalid SVG Structure",
            category="svg_structure",
            severity="medium",
            score=10,
            description=(
                "File diduga SVG, tetapi struktur awalnya tidak terlihat seperti SVG/XML valid."
            ),
            evidence=f"extension={file_info.claimed_extension}, detected_type={file_info.detected_type}",
            source="analyzers.svg",
        )
    ]


def _safe_xml_parse_check(text: str) -> list[Indicator]:
    """
    Parse XML memakai defusedxml agar lebih aman terhadap XML attack.

    Jika defusedxml tidak terpasang, check ini dilewati.
    """

    if len(text) > 5 * 1024 * 1024:
        return [
            make_indicator(
                name="Large SVG Skipped XML Parse",
                category="svg_structure",
                severity="low",
                score=0,
                description=(
                    "SVG terlalu besar untuk diparse pada tahap ringan. "
                    "Analisis string tetap dilakukan."
                ),
                evidence=f"size={len(text)} chars",
                source="analyzers.svg",
            )
        ]

    try:
        from defusedxml import ElementTree as SafeElementTree
    except ImportError:
        return []

    try:
        SafeElementTree.fromstring(text)
        return []

    except Exception as error:
        return [
            make_indicator(
                name="SVG XML Parse Failed",
                category="svg_structure",
                severity="low",
                score=5,
                description=(
                    "SVG gagal diparse sebagai XML. File mungkin corrupt, malformed, "
                    "atau sengaja dibuat tidak normal."
                ),
                evidence=str(error),
                source="analyzers.svg",
            )
        ]


def _detect_script_tag(text: str) -> list[Indicator]:
    match = SCRIPT_TAG_REGEX.search(text)

    if not match:
        return []

    return [
        make_indicator(
            name="SVG Script Tag Found",
            category="svg_script",
            severity="critical",
            score=25,
            description=(
                "SVG mengandung tag <script>. SVG dengan script dapat menjalankan kode "
                "saat dibuka pada konteks tertentu."
            ),
            evidence=_sample(text, match.start()),
            offset=match.start(),
            source="analyzers.svg",
        )
    ]


def _detect_event_handlers(text: str) -> list[Indicator]:
    matches = EVENT_HANDLER_REGEX.findall(text)

    if not matches:
        return []

    unique_events = sorted(set(event.strip() for event in matches))

    return [
        make_indicator(
            name="SVG Event Handler Found",
            category="svg_script",
            severity="high",
            score=20,
            description=(
                "SVG mengandung event handler seperti onload, onclick, atau onerror. "
                "Ini dapat memicu script secara otomatis atau saat interaksi user."
            ),
            evidence=", ".join(unique_events[:10]),
            source="analyzers.svg",
        )
    ]


def _detect_javascript_uri(text: str) -> list[Indicator]:
    match = JAVASCRIPT_URI_REGEX.search(text)

    if not match:
        return []

    return [
        make_indicator(
            name="SVG JavaScript URI Found",
            category="svg_script",
            severity="critical",
            score=25,
            description=(
                "SVG mengandung javascript: URI yang dapat digunakan untuk menjalankan script."
            ),
            evidence=_sample(text, match.start()),
            offset=match.start(),
            source="analyzers.svg",
        )
    ]


def _detect_external_references(text: str) -> list[Indicator]:
    matches = list(EXTERNAL_REF_REGEX.finditer(text))

    if not matches:
        return []

    evidence = " | ".join(_sample(text, match.start(), length=120) for match in matches[:3])

    return [
        make_indicator(
            name="SVG External Reference Found",
            category="svg_network",
            severity="medium",
            score=15,
            description=(
                "SVG mengandung referensi eksternal melalui href/src. "
                "Ini dapat digunakan untuk memuat konten dari internet."
            ),
            evidence=evidence,
            source="analyzers.svg",
        )
    ]


def _detect_risky_tags(text: str) -> list[Indicator]:
    lower_text = text.lower()
    found_tags: list[str] = []

    for tag in SVG_RISKY_TAGS:
        if f"<{tag.lower()}" in lower_text:
            found_tags.append(tag)

    if not found_tags:
        return []

    return [
        make_indicator(
            name="SVG Risky Embedded Content Tag Found",
            category="svg_embedded_content",
            severity="medium",
            score=15,
            description=(
                "SVG mengandung tag yang dapat menyisipkan konten aktif atau eksternal."
            ),
            evidence=", ".join(found_tags),
            source="analyzers.svg",
        )
    ]


def _detect_data_uri_and_base64(text: str) -> list[Indicator]:
    indicators: list[Indicator] = []

    data_match = DATA_URI_REGEX.search(text)

    if data_match:
        indicators.append(
            make_indicator(
                name="SVG Data URI Found",
                category="svg_embedded_content",
                severity="medium",
                score=10,
                description=(
                    "SVG mengandung data URI. Ini bisa normal untuk embedded image, "
                    "tetapi juga bisa dipakai menyisipkan konten tersembunyi."
                ),
                evidence=_sample(text, data_match.start(), length=120),
                offset=data_match.start(),
                source="analyzers.svg",
            )
        )

    base64_match = BASE64_TEXT_REGEX.search(text)

    if base64_match:
        indicators.append(
            make_indicator(
                name="Long Base64 String in SVG",
                category="svg_obfuscation",
                severity="medium",
                score=10,
                description=(
                    "SVG mengandung string base64 panjang. Ini dapat menyimpan gambar, "
                    "script, atau payload tersembunyi."
                ),
                evidence=f"length={len(base64_match.group(0))}, sample={base64_match.group(0)[:80]}",
                offset=base64_match.start(),
                source="analyzers.svg",
            )
        )

    return indicators


def _sample(text: str, offset: int, length: int = 100) -> str:
    start = max(offset - 30, 0)
    end = min(offset + length, len(text))

    sample = text[start:end]
    sample = sample.replace("\n", " ").replace("\r", " ")

    return sample