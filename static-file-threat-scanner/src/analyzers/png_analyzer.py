from __future__ import annotations

from pathlib import Path
from io import BytesIO

from src.core.models import FileInfo, Indicator
from src.core.scoring import make_indicator


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_IEND = b"IEND"

EXTRA_DATA_WARNING_THRESHOLD = 32
EXTRA_DATA_SUSPICIOUS_THRESHOLD = 1024


def analyze(
    file_path: str | Path,
    file_bytes: bytes,
    file_info: FileInfo,
) -> list[Indicator]:
    """
    PNG analyzer.

    Fokus:
    - validasi signature PNG
    - validasi IEND
    - deteksi data tambahan setelah IEND
    - validasi ringan dengan Pillow jika tersedia
    """

    indicators: list[Indicator] = []

    indicators.extend(_check_png_signature(file_bytes))
    indicators.extend(_check_png_iend_and_extra_data(file_bytes))
    indicators.extend(_verify_png_with_pillow(file_bytes))

    return indicators


def _check_png_signature(file_bytes: bytes) -> list[Indicator]:
    if file_bytes.startswith(PNG_SIGNATURE):
        return []

    return [
        make_indicator(
            name="Invalid PNG Signature",
            category="png_structure",
            severity="high",
            score=20,
            description="File tidak memiliki signature PNG yang valid.",
            evidence=f"expected={PNG_SIGNATURE.hex(' ')}, actual={file_bytes[:8].hex(' ')}",
            source="analyzers.png",
        )
    ]


def _check_png_iend_and_extra_data(file_bytes: bytes) -> list[Indicator]:
    indicators: list[Indicator] = []

    iend_offset = file_bytes.rfind(PNG_IEND)

    if iend_offset == -1:
        indicators.append(
            make_indicator(
                name="Missing PNG IEND Chunk",
                category="png_structure",
                severity="high",
                score=20,
                description="PNG tidak memiliki chunk IEND sebagai penanda akhir file.",
                evidence="IEND not found",
                source="analyzers.png",
            )
        )
        return indicators

    # Posisi IEND menunjuk ke nama chunk.
    # Setelah 'IEND' masih ada CRC 4 byte.
    expected_end = iend_offset + len(PNG_IEND) + 4

    if expected_end > len(file_bytes):
        indicators.append(
            make_indicator(
                name="Truncated PNG IEND Chunk",
                category="png_structure",
                severity="medium",
                score=15,
                description="Chunk IEND tidak lengkap atau struktur PNG terpotong.",
                evidence=f"iend_offset={iend_offset}, file_size={len(file_bytes)}",
                source="analyzers.png",
            )
        )
        return indicators

    extra_data = file_bytes[expected_end:]
    extra_size = len(extra_data)

    if extra_size >= EXTRA_DATA_SUSPICIOUS_THRESHOLD:
        indicators.append(
            make_indicator(
                name="Large Extra Data After PNG IEND",
                category="png_appended_data",
                severity="high",
                score=25,
                description=(
                    "Ditemukan data besar setelah akhir PNG. Ini dapat menjadi indikasi "
                    "payload atau file lain ditempelkan setelah gambar."
                ),
                evidence=f"extra_size={extra_size} bytes, iend_offset={iend_offset}",
                offset=expected_end,
                source="analyzers.png",
            )
        )

    elif extra_size >= EXTRA_DATA_WARNING_THRESHOLD:
        indicators.append(
            make_indicator(
                name="Extra Data After PNG IEND",
                category="png_appended_data",
                severity="low",
                score=5,
                description=(
                    "Ditemukan data tambahan setelah akhir PNG. Ukurannya kecil, "
                    "tetapi tetap dicatat sebagai anomali struktur."
                ),
                evidence=f"extra_size={extra_size} bytes, iend_offset={iend_offset}",
                offset=expected_end,
                source="analyzers.png",
            )
        )

    return indicators


def _verify_png_with_pillow(file_bytes: bytes) -> list[Indicator]:
    """
    Verifikasi ringan memakai Pillow.

    Ini tidak menjalankan file sebagai program.
    Pillow hanya membaca struktur gambar.
    Jika Pillow tidak terpasang, check ini dilewati.
    """

    try:
        from PIL import Image
    except ImportError:
        return []

    try:
        image = Image.open(BytesIO(file_bytes))
        image.verify()
        return []

    except Exception as error:
        return [
            make_indicator(
                name="PNG Parser Verification Failed",
                category="png_structure",
                severity="medium",
                score=10,
                description=(
                    "Pillow gagal memverifikasi struktur PNG. File mungkin corrupt atau malformed."
                ),
                evidence=str(error),
                source="analyzers.png",
            )
        ]