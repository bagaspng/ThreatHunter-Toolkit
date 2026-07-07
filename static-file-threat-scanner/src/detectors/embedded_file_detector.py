from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.core.models import FileInfo, Indicator
from src.core.scoring import make_indicator


@dataclass(frozen=True)
class EmbeddedSignatureRule:
    name: str
    pattern: bytes
    category: str
    severity: str
    score: int
    description: str


EMBEDDED_SIGNATURE_RULES: list[EmbeddedSignatureRule] = [
    EmbeddedSignatureRule(
        name="Embedded ZIP/APK Signature",
        pattern=b"PK\x03\x04",
        category="embedded_file",
        severity="high",
        score=35,
        description=(
            "Ditemukan signature ZIP/APK yang valid. APK Android juga berbasis ZIP."
        ),
    ),
    EmbeddedSignatureRule(
        name="Embedded Windows Executable Signature",
        pattern=b"MZ",
        category="embedded_file",
        severity="critical",
        score=40,
        description=(
            "Ditemukan struktur Windows executable PE yang valid."
        ),
    ),
    EmbeddedSignatureRule(
        name="Embedded Android DEX File",
        pattern=b"dex\n035\x00",
        category="embedded_file",
        severity="critical",
        score=35,
        description="Ditemukan file DEX Android.",
    ),
    EmbeddedSignatureRule(
        name="Embedded Android DEX File",
        pattern=b"dex\n036\x00",
        category="embedded_file",
        severity="critical",
        score=35,
        description="Ditemukan file DEX Android.",
    ),
    EmbeddedSignatureRule(
        name="Embedded ELF Executable",
        pattern=b"\x7fELF",
        category="embedded_file",
        severity="high",
        score=35,
        description="Ditemukan signature ELF executable.",
    ),
]


def detect_embedded_files(
    file_bytes: bytes,
    file_info: FileInfo | None = None,
    rules: Iterable[EmbeddedSignatureRule] | None = None,
    max_offsets_per_rule: int = 5,
) -> list[Indicator]:
    indicators: list[Indicator] = []
    active_rules = list(rules or EMBEDDED_SIGNATURE_RULES)

    for rule in active_rules:
        raw_offsets = find_all_offsets(file_bytes, rule.pattern, limit=max_offsets_per_rule * 5)

        if not raw_offsets:
            continue

        valid_offsets: list[int] = []

        for offset in raw_offsets:
            if _should_ignore_primary_signature(offset, rule, file_info):
                continue

            if rule.pattern == b"MZ":
                if not is_valid_pe_at_offset(file_bytes, offset):
                    continue

            if rule.pattern == b"PK\x03\x04":
                if not is_plausible_zip_local_header(file_bytes, offset):
                    continue

            valid_offsets.append(offset)

            if len(valid_offsets) >= max_offsets_per_rule:
                break

        if not valid_offsets:
            continue

        evidence = ", ".join(str(offset) for offset in valid_offsets)

        indicators.append(
            make_indicator(
                name=rule.name,
                category=rule.category,
                severity=rule.severity,
                score=rule.score,
                description=rule.description,
                evidence=f"pattern={safe_pattern(rule.pattern)}, offsets={evidence}",
                offset=valid_offsets[0],
                source="detectors.embedded_file_detector",
            )
        )

    return indicators


def find_all_offsets(data: bytes, pattern: bytes, limit: int = 10) -> list[int]:
    if not data or not pattern:
        return []

    offsets: list[int] = []
    start = 0

    while True:
        offset = data.find(pattern, start)

        if offset == -1:
            break

        offsets.append(offset)

        if len(offsets) >= limit:
            break

        start = offset + 1

    return offsets


def is_valid_pe_at_offset(data: bytes, offset: int) -> bool:
    """
    Validasi Windows PE:
    - harus mulai MZ
    - offset + 0x3C harus ada
    - e_lfanew menunjuk ke PE\\0\\0
    """

    if offset < 0:
        return False

    if offset + 0x40 > len(data):
        return False

    if data[offset : offset + 2] != b"MZ":
        return False

    e_lfanew = int.from_bytes(data[offset + 0x3C : offset + 0x40], "little")

    if e_lfanew <= 0:
        return False

    pe_offset = offset + e_lfanew

    if pe_offset + 4 > len(data):
        return False

    return data[pe_offset : pe_offset + 4] == b"PE\x00\x00"


def is_plausible_zip_local_header(data: bytes, offset: int) -> bool:
    """
    Validasi ringan ZIP local file header.

    Format minimal:
    PK 03 04
    version needed
    flags
    compression method
    """

    if offset + 30 > len(data):
        return False

    if data[offset : offset + 4] != b"PK\x03\x04":
        return False

    version_needed = int.from_bytes(data[offset + 4 : offset + 6], "little")
    compression_method = int.from_bytes(data[offset + 8 : offset + 10], "little")
    file_name_length = int.from_bytes(data[offset + 26 : offset + 28], "little")

    if not (10 <= version_needed <= 63):
        return False

    if compression_method not in {0, 8, 9, 12, 14, 98}:
        return False

    if file_name_length <= 0 or file_name_length > 512:
        return False

    return True


def _should_ignore_primary_signature(
    offset: int,
    rule: EmbeddedSignatureRule,
    file_info: FileInfo | None,
) -> bool:
    if offset != 0:
        return False

    if file_info is None:
        return False

    primary_signature_map = {
        "EXE": "Embedded Windows Executable Signature",
        "ZIP/APK": "Embedded ZIP/APK Signature",
    }

    return primary_signature_map.get(file_info.detected_type) == rule.name


def safe_pattern(pattern: bytes) -> str:
    text = pattern.decode("utf-8", errors="replace")
    hex_value = pattern.hex(" ").upper()

    if text.strip():
        return f"{text} | hex={hex_value}"

    return f"hex={hex_value}"