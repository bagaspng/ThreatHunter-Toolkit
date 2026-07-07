from __future__ import annotations

from pathlib import Path
from io import BytesIO

from src.core.models import FileInfo, Indicator
from src.core.scoring import make_indicator


JPEG_SIGNATURE = b"\xff\xd8\xff"
JPEG_EOF = b"\xff\xd9"

EXTRA_DATA_WARNING_THRESHOLD = 32
EXTRA_DATA_SUSPICIOUS_THRESHOLD = 1024


def analyze(
    file_path: str | Path,
    file_bytes: bytes,
    file_info: FileInfo,
) -> list[Indicator]:
    """
    JPG/JPEG analyzer.

    Fokus:
    - validasi signature JPEG
    - validasi EOF marker FF D9
    - deteksi data tambahan setelah EOF
    - validasi ringan dengan Pillow jika tersedia
    """

    indicators: list[Indicator] = []

    indicators.extend(_check_jpeg_signature(file_bytes))
    indicators.extend(_check_jpeg_eof_and_extra_data(file_bytes))
    indicators.extend(_verify_jpeg_with_pillow(file_bytes))

    return indicators


def _check_jpeg_signature(file_bytes: bytes) -> list[Indicator]:
    if file_bytes.startswith(JPEG_SIGNATURE):
        return []

    return [
        make_indicator(
            name="Invalid JPEG Signature",
            category="jpeg_structure",
            severity="high",
            score=20,
            description="File tidak memiliki signature JPEG yang valid.",
            evidence=f"expected={JPEG_SIGNATURE.hex(' ')}, actual={file_bytes[:8].hex(' ')}",
            source="analyzers.jpg",
        )
    ]


def _check_jpeg_eof_and_extra_data(file_bytes: bytes) -> list[Indicator]:
    indicators: list[Indicator] = []

    eof_offset = file_bytes.rfind(JPEG_EOF)

    if eof_offset == -1:
        indicators.append(
            make_indicator(
                name="Missing JPEG EOF Marker",
                category="jpeg_structure",
                severity="high",
                score=20,
                description="JPEG tidak memiliki marker akhir FF D9.",
                evidence="FF D9 not found",
                source="analyzers.jpg",
            )
        )
        return indicators

    expected_end = eof_offset + len(JPEG_EOF)
    extra_data = file_bytes[expected_end:]
    extra_size = len(extra_data)

    if extra_size >= EXTRA_DATA_SUSPICIOUS_THRESHOLD:
        indicators.append(
            make_indicator(
                name="Large Extra Data After JPEG EOF",
                category="jpeg_appended_data",
                severity="high",
                score=25,
                description=(
                    "Ditemukan data besar setelah akhir JPEG. Ini dapat menjadi indikasi "
                    "payload atau file lain ditempelkan setelah gambar."
                ),
                evidence=f"extra_size={extra_size} bytes, eof_offset={eof_offset}",
                offset=expected_end,
                source="analyzers.jpg",
            )
        )

    elif extra_size >= EXTRA_DATA_WARNING_THRESHOLD:
        indicators.append(
            make_indicator(
                name="Extra Data After JPEG EOF",
                category="jpeg_appended_data",
                severity="low",
                score=5,
                description=(
                    "Ditemukan data tambahan setelah akhir JPEG. Ukurannya kecil, "
                    "tetapi tetap dicatat sebagai anomali struktur."
                ),
                evidence=f"extra_size={extra_size} bytes, eof_offset={eof_offset}",
                offset=expected_end,
                source="analyzers.jpg",
            )
        )

    return indicators


def _verify_jpeg_with_pillow(file_bytes: bytes) -> list[Indicator]:
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
                name="JPEG Parser Verification Failed",
                category="jpeg_structure",
                severity="medium",
                score=10,
                description=(
                    "Pillow gagal memverifikasi struktur JPEG. File mungkin corrupt atau malformed."
                ),
                evidence=str(error),
                source="analyzers.jpg",
            )
        ]