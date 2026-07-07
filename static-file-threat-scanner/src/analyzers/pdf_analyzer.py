from __future__ import annotations

from pathlib import Path
import re

from src.core.models import FileInfo, Indicator
from src.core.scoring import make_indicator


PDF_SUSPICIOUS_PATTERNS = [
    {
        "pattern": b"/JavaScript",
        "name": "PDF JavaScript Found",
        "severity": "high",
        "score": 15,
        "description": "PDF mengandung JavaScript. Ini dapat digunakan untuk aksi otomatis atau eksploitasi.",
    },
    {
        "pattern": b"/JS",
        "name": "PDF JS Action Found",
        "severity": "medium",
        "score": 10,
        "description": "PDF mengandung /JS action. Ini dapat berkaitan dengan JavaScript dalam PDF.",
    },
    {
        "pattern": b"/OpenAction",
        "name": "PDF OpenAction Found",
        "severity": "high",
        "score": 20,
        "description": "PDF memiliki OpenAction, yaitu aksi yang dapat berjalan saat PDF dibuka.",
    },
    {
        "pattern": b"/AA",
        "name": "PDF Additional Action Found",
        "severity": "medium",
        "score": 15,
        "description": "PDF memiliki Additional Action yang dapat memicu aksi tertentu.",
    },
    {
        "pattern": b"/Launch",
        "name": "PDF Launch Action Found",
        "severity": "critical",
        "score": 25,
        "description": "PDF memiliki Launch action yang dapat digunakan untuk menjalankan file atau perintah.",
    },
    {
        "pattern": b"/EmbeddedFile",
        "name": "PDF Embedded File Found",
        "severity": "high",
        "score": 25,
        "description": "PDF mengandung embedded file atau attachment.",
    },
    {
        "pattern": b"/Filespec",
        "name": "PDF File Specification Found",
        "severity": "medium",
        "score": 15,
        "description": "PDF mengandung Filespec yang sering berkaitan dengan file attachment.",
    },
    {
        "pattern": b"/SubmitForm",
        "name": "PDF Submit Form Found",
        "severity": "medium",
        "score": 10,
        "description": "PDF memiliki SubmitForm yang dapat mengirim data ke lokasi tertentu.",
    },
    {
        "pattern": b"/AcroForm",
        "name": "PDF AcroForm Found",
        "severity": "low",
        "score": 5,
        "description": "PDF mengandung AcroForm. Ini bisa normal, tetapi perlu diperhatikan.",
    },
    {
        "pattern": b"/XFA",
        "name": "PDF XFA Form Found",
        "severity": "medium",
        "score": 10,
        "description": "PDF mengandung XFA form. Format ini kompleks dan sering dipantau dalam analisis PDF.",
    },
    {
        "pattern": b"/RichMedia",
        "name": "PDF RichMedia Found",
        "severity": "medium",
        "score": 15,
        "description": "PDF mengandung RichMedia yang dapat menyisipkan konten aktif.",
    },
]


PDF_URI_REGEX = re.compile(rb"/URI\s*\((.*?)\)", re.IGNORECASE | re.DOTALL)


def analyze(
    file_path: str | Path,
    file_bytes: bytes,
    file_info: FileInfo,
) -> list[Indicator]:
    """
    PDF analyzer.

    Fokus:
    - validasi header PDF
    - keyword PDF berisiko
    - OpenAction / JavaScript / EmbeddedFile
    - URI mencurigakan
    - EOF marker
    - encrypted/object stream sebagai indikator keterbatasan analisis
    """

    indicators: list[Indicator] = []

    indicators.extend(_check_pdf_header(file_bytes, file_info))
    indicators.extend(_detect_pdf_suspicious_patterns(file_bytes))
    indicators.extend(_detect_pdf_uri(file_bytes))
    indicators.extend(_detect_pdf_structure_anomalies(file_bytes))

    return indicators


def _check_pdf_header(file_bytes: bytes, file_info: FileInfo) -> list[Indicator]:
    if file_bytes.startswith(b"%PDF"):
        return []

    return [
        make_indicator(
            name="Invalid PDF Header",
            category="pdf_structure",
            severity="high",
            score=20,
            description=(
                "File memiliki ekstensi atau dugaan tipe PDF, tetapi header tidak dimulai dengan %PDF."
            ),
            evidence=f"extension={file_info.claimed_extension}, detected_type={file_info.detected_type}",
            source="analyzers.pdf",
        )
    ]


def _detect_pdf_suspicious_patterns(file_bytes: bytes) -> list[Indicator]:
    indicators: list[Indicator] = []
    lower_bytes = file_bytes.lower()

    for item in PDF_SUSPICIOUS_PATTERNS:
        pattern = item["pattern"]
        offset = lower_bytes.find(pattern.lower())

        if offset == -1:
            continue

        indicators.append(
            make_indicator(
                name=item["name"],
                category="pdf_keyword",
                severity=item["severity"],
                score=item["score"],
                description=item["description"],
                evidence=f"keyword={pattern.decode('utf-8', errors='replace')}, offset={offset}",
                offset=offset,
                source="analyzers.pdf",
            )
        )

    return indicators


def _detect_pdf_uri(file_bytes: bytes) -> list[Indicator]:
    matches = PDF_URI_REGEX.findall(file_bytes)

    if not matches:
        return []

    sample_values = []

    for match in matches[:5]:
        sample_values.append(match[:100].decode("utf-8", errors="replace"))

    return [
        make_indicator(
            name="PDF URI Action Found",
            category="pdf_network",
            severity="medium",
            score=10,
            description=(
                "PDF mengandung URI action. Ini bisa normal untuk hyperlink, "
                "tetapi dapat juga digunakan untuk phishing atau mengarahkan user ke payload."
            ),
            evidence=" | ".join(sample_values),
            source="analyzers.pdf",
        )
    ]


def _detect_pdf_structure_anomalies(file_bytes: bytes) -> list[Indicator]:
    indicators: list[Indicator] = []
    lower_bytes = file_bytes.lower()

    eof_count = file_bytes.count(b"%%EOF")

    if eof_count == 0:
        indicators.append(
            make_indicator(
                name="Missing PDF EOF Marker",
                category="pdf_structure",
                severity="medium",
                score=10,
                description="PDF tidak memiliki marker %%EOF. Struktur file mungkin tidak normal.",
                evidence="%%EOF not found",
                source="analyzers.pdf",
            )
        )

    elif eof_count > 5:
        indicators.append(
            make_indicator(
                name="Multiple PDF EOF Markers",
                category="pdf_structure",
                severity="low",
                score=5,
                description=(
                    "PDF memiliki banyak marker %%EOF. Ini bisa terjadi pada PDF normal "
                    "karena incremental update, tetapi tetap layak dicatat."
                ),
                evidence=f"eof_count={eof_count}",
                source="analyzers.pdf",
            )
        )

    if b"/encrypt" in lower_bytes:
        indicators.append(
            make_indicator(
                name="Encrypted PDF",
                category="pdf_structure",
                severity="low",
                score=5,
                description=(
                    "PDF menggunakan enkripsi. Ini tidak otomatis berbahaya, "
                    "tetapi dapat membatasi proses analisis statis."
                ),
                evidence="/Encrypt",
                source="analyzers.pdf",
            )
        )

    if b"/objstm" in lower_bytes:
        indicators.append(
            make_indicator(
                name="PDF Object Stream Found",
                category="pdf_structure",
                severity="low",
                score=0,
                description=(
                    "PDF menggunakan object stream. Ini normal pada banyak PDF, "
                    "tetapi dapat menyembunyikan object dari pencarian sederhana."
                ),
                evidence="/ObjStm",
                source="analyzers.pdf",
            )
        )

    if b"app.launchurl" in lower_bytes:
        indicators.append(
            make_indicator(
                name="PDF app.launchURL Found",
                category="pdf_javascript",
                severity="high",
                score=20,
                description=(
                    "PDF mengandung app.launchURL, fungsi JavaScript yang dapat membuka URL."
                ),
                evidence="app.launchURL",
                source="analyzers.pdf",
            )
        )

    if b"exportdataobject" in lower_bytes:
        indicators.append(
            make_indicator(
                name="PDF exportDataObject Found",
                category="pdf_javascript",
                severity="high",
                score=20,
                description=(
                    "PDF mengandung exportDataObject, fungsi yang dapat berkaitan dengan embedded file."
                ),
                evidence="exportDataObject",
                source="analyzers.pdf",
            )
        )

    return indicators