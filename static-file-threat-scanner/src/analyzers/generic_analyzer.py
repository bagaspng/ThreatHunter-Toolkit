from __future__ import annotations

from pathlib import Path

from src.core.entropy import calculate_entropy
from src.core.models import FileInfo, Indicator
from src.core.scoring import make_indicator
from src.detectors.embedded_file_detector import detect_embedded_files
from src.detectors.suspicious_string_detector import detect_suspicious_strings
from src.detectors.url_detector import detect_network_indicators
from src.detectors.base64_detector import detect_base64_strings
from src.detectors.apk_indicator_detector import detect_apk_indicators


def analyze(
    file_path: str | Path,
    file_bytes: bytes,
    file_info: FileInfo,
) -> list[Indicator]:
    indicators: list[Indicator] = []

    indicators.extend(detect_embedded_files(file_bytes, file_info=file_info))
    indicators.extend(detect_apk_indicators(file_bytes))
    indicators.extend(detect_network_indicators(file_bytes))
    indicators.extend(detect_base64_strings(file_bytes))
    indicators.extend(detect_suspicious_strings(file_bytes))
    indicators.extend(_detect_high_entropy(file_bytes, file_info))

    return indicators


def _detect_high_entropy(
    file_bytes: bytes,
    file_info: FileInfo,
) -> list[Indicator]:
    """
    Jangan memberi skor entropy tinggi untuk PDF/PNG/JPEG.

    PDF sering berisi compressed stream.
    PNG/JPEG memang file gambar terkompresi.
    Jadi entropy tinggi pada format ini normal dan rawan false positive.
    """

    if file_info.detected_type in {"PDF", "PNG", "JPEG", "ZIP/APK"}:
        return []

    if len(file_bytes) < 1024:
        return []

    entropy = calculate_entropy(file_bytes)

    if entropy < 7.7:
        return []

    return [
        make_indicator(
            name="High File Entropy",
            category="obfuscation",
            severity="low",
            score=10,
            description=(
                "Entropy file cukup tinggi. Ini dapat menunjukkan kompresi, enkripsi, "
                "packing, atau obfuscation. Tidak otomatis berarti malware."
            ),
            evidence=f"entropy={entropy}",
            source="analyzers.generic",
        )
    ]
