from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.core.models import Indicator
from src.core.scoring import make_indicator


@dataclass(frozen=True)
class SuspiciousStringRule:
    name: str
    patterns: tuple[bytes, ...]
    category: str
    severity: str
    score: int
    description: str


SUSPICIOUS_STRING_RULES: list[SuspiciousStringRule] = [
    SuspiciousStringRule(
        name="Windows Command Keyword Found",
        patterns=(
            b"cmd.exe",
            b"powershell",
            b"wscript",
            b"cscript",
            b"rundll32",
            b"regsvr32",
            b"mshta",
            b"certutil",
            b"bitsadmin",
        ),
        category="command_indicator",
        severity="medium",
        score=15,
        description=(
            "Ditemukan keyword command Windows yang sering muncul pada script, downloader, "
            "atau payload mencurigakan."
        ),
    ),
    SuspiciousStringRule(
        name="Unix Shell Keyword Found",
        patterns=(
            b"/bin/sh",
            b"/bin/bash",
            b"chmod +x",
            b"curl ",
            b"wget ",
            b"sh -c",
        ),
        category="command_indicator",
        severity="medium",
        score=15,
        description=(
            "Ditemukan keyword shell Unix/Linux yang dapat berkaitan dengan eksekusi command."
        ),
    ),
    SuspiciousStringRule(
        name="Script Obfuscation Keyword Found",
        patterns=(
            b"eval(",
            b"eval ",
            b"atob(",
            b"fromCharCode",
            b"unescape(",
            b"String.fromCharCode",
            b"base64_decode",
        ),
        category="obfuscation",
        severity="medium",
        score=15,
        description=(
            "Ditemukan keyword yang sering digunakan untuk obfuscation atau decoding script."
        ),
    ),
    SuspiciousStringRule(
        name="PDF JavaScript Function Found",
        patterns=(
            b"app.launchURL",
            b"exportDataObject",
            b"getAnnots",
            b"submitForm",
        ),
        category="pdf_javascript",
        severity="high",
        score=20,
        description=(
            "Ditemukan fungsi JavaScript PDF yang dapat berkaitan dengan URL, form, "
            "atau embedded object."
        ),
    ),
    SuspiciousStringRule(
        name="Suspicious Download Keyword Found",
        patterns=(
            b"download",
            b"payload",
            b"dropper",
            b"execute",
            b"install",
        ),
        category="suspicious_keyword",
        severity="low",
        score=5,
        description=(
            "Ditemukan keyword umum yang dapat berkaitan dengan aktivitas download "
            "atau payload. Indikator ini lemah dan perlu dikombinasikan dengan indikator lain."
        ),
    ),
]


def detect_suspicious_strings(
    file_bytes: bytes,
    rules: Iterable[SuspiciousStringRule] | None = None,
    source: str = "detectors.suspicious_string_detector",
) -> list[Indicator]:
    """
    Mendeteksi string/keyword mencurigakan di dalam file.

    Detector ini menggunakan pencarian case-insensitive.
    Output berupa list Indicator.
    """

    active_rules = list(rules or SUSPICIOUS_STRING_RULES)
    lower_bytes = file_bytes.lower()

    indicators: list[Indicator] = []

    for rule in active_rules:
        found_patterns: list[str] = []

        for pattern in rule.patterns:
            if pattern.lower() in lower_bytes:
                found_patterns.append(pattern.decode("utf-8", errors="replace"))

        if not found_patterns:
            continue

        indicators.append(
            make_indicator(
                name=rule.name,
                category=rule.category,
                severity=rule.severity,
                score=rule.score,
                description=rule.description,
                evidence=", ".join(found_patterns[:10]),
                source=source,
            )
        )

    return indicators


def contains_any_string(file_bytes: bytes, patterns: Iterable[bytes]) -> bool:
    """
    Helper sederhana untuk mengecek apakah salah satu pattern ada di file.
    """

    lower_bytes = file_bytes.lower()

    for pattern in patterns:
        if pattern.lower() in lower_bytes:
            return True

    return False


def find_string_offsets(
    file_bytes: bytes,
    pattern: bytes,
    max_results: int = 10,
) -> list[int]:
    """
    Mencari offset kemunculan string tertentu.
    """

    if not pattern:
        return []

    lower_bytes = file_bytes.lower()
    lower_pattern = pattern.lower()

    offsets: list[int] = []
    start = 0

    while True:
        offset = lower_bytes.find(lower_pattern, start)

        if offset == -1:
            break

        offsets.append(offset)

        if len(offsets) >= max_results:
            break

        start = offset + 1

    return offsets