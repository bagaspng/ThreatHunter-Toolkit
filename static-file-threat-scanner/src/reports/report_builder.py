from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime

from src.core.models import ScanResult, Indicator


def build_report_dict(scan_result: ScanResult) -> dict:
    """
    Mengubah ScanResult menjadi dictionary yang siap disimpan sebagai JSON.

    Fungsi ini menggunakan ScanResult.to_dict(), lalu menambahkan metadata report.
    """

    report = scan_result.to_dict()

    report["report_metadata"] = {
        "tool_name": "Static File Threat Scanner",
        "analysis_type": "Static Analysis",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": (
            "This tool uses static analysis only. "
            "The result is an indicator-based risk assessment, "
            "not an absolute malware verdict."
        ),
    }

    report["summary"] = build_summary(scan_result)

    return report


def build_summary(scan_result: ScanResult) -> dict:
    """
    Membuat ringkasan hasil scan.
    """

    total_indicators = len(scan_result.indicators)

    severity_count = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "unknown": 0,
    }

    category_count: dict[str, int] = {}

    for indicator in scan_result.indicators:
        severity = indicator.severity.lower() if indicator.severity else "unknown"

        if severity not in severity_count:
            severity = "unknown"

        severity_count[severity] += 1

        category = indicator.category or "unknown"
        category_count[category] = category_count.get(category, 0) + 1

    return {
        "risk_score": scan_result.risk_score,
        "risk_status": scan_result.risk_status,
        "total_indicators": total_indicators,
        "severity_count": severity_count,
        "category_count": category_count,
        "recommendation": build_recommendation(scan_result),
    }


def build_recommendation(scan_result: ScanResult) -> str:
    """
    Membuat rekomendasi berdasarkan status risiko.
    """

    status = scan_result.risk_status.lower()

    if status == "clean":
        return (
            "Tidak ditemukan indikator mencurigakan yang kuat. "
            "Namun, hasil ini bukan jaminan bahwa file pasti aman."
        )

    if status == "suspicious":
        return (
            "File memiliki beberapa indikator mencurigakan. "
            "Sebaiknya jangan membuka file ini di perangkat utama sebelum dianalisis lebih lanjut."
        )

    return (
        "File memiliki indikator kuat yang mengarah pada konten berbahaya atau payload tersembunyi. "
        "Jangan buka file ini di perangkat utama. Jika perlu analisis lanjutan, gunakan environment terisolasi."
    )


def build_text_report(scan_result: ScanResult) -> str:
    """
    Membuat report dalam format teks biasa.
    """

    file_info = scan_result.file_info
    hashes = scan_result.hashes

    lines: list[str] = []

    lines.append("=" * 72)
    lines.append("STATIC FILE THREAT SCANNER REPORT")
    lines.append("=" * 72)
    lines.append("")
    lines.append("Report Metadata")
    lines.append("-" * 72)
    lines.append(f"Generated At    : {datetime.now().isoformat(timespec='seconds')}")
    lines.append("Analysis Type   : Static Analysis")
    lines.append("Verdict Type    : Indicator-based risk assessment")
    lines.append("")
    lines.append("File Information")
    lines.append("-" * 72)
    lines.append(f"File Name       : {file_info.file_name}")
    lines.append(f"File Path       : {file_info.file_path}")
    lines.append(f"File Size       : {format_file_size(file_info.file_size)}")
    lines.append(f"Claimed Ext     : {file_info.claimed_extension}")
    lines.append(f"Detected Type   : {file_info.detected_type}")
    lines.append(f"MIME Hint       : {file_info.mime_hint or '-'}")
    lines.append(f"Magic Hex       : {file_info.magic_hex or '-'}")
    lines.append("")
    lines.append("Hashes")
    lines.append("-" * 72)
    lines.append(f"MD5             : {hashes.get('md5', '-')}")
    lines.append(f"SHA1            : {hashes.get('sha1', '-')}")
    lines.append(f"SHA256          : {hashes.get('sha256', '-')}")
    lines.append("")
    lines.append("Risk Result")
    lines.append("-" * 72)
    lines.append(f"Risk Score      : {scan_result.risk_score}/100")
    lines.append(f"Risk Status     : {scan_result.risk_status}")
    lines.append(f"Duration        : {scan_result.duration_seconds} seconds")
    lines.append("")

    if scan_result.warnings:
        lines.append("Warnings")
        lines.append("-" * 72)

        for warning in scan_result.warnings:
            lines.append(f"[!] {warning}")

        lines.append("")

    lines.append("Indicators")
    lines.append("-" * 72)

    if not scan_result.indicators:
        lines.append("No suspicious indicators found.")
    else:
        for index, indicator in enumerate(scan_result.indicators, start=1):
            lines.extend(format_indicator_text(index, indicator))

    lines.append("")
    lines.append("Recommendation")
    lines.append("-" * 72)
    lines.append(build_recommendation(scan_result))
    lines.append("")
    lines.append("Disclaimer")
    lines.append("-" * 72)
    lines.append(
        "This tool uses static analysis only. It does not execute the scanned file. "
        "False positives and false negatives are possible."
    )
    lines.append("=" * 72)

    return "\n".join(lines)


def format_indicator_text(index: int, indicator: Indicator) -> list[str]:
    """
    Format satu indicator menjadi beberapa baris teks.
    """

    lines: list[str] = []

    lines.append(f"{index}. {indicator.name}")
    lines.append(f"   Category     : {indicator.category}")
    lines.append(f"   Severity     : {indicator.severity}")
    lines.append(f"   Score        : +{indicator.score}")
    lines.append(f"   Description  : {indicator.description}")

    if indicator.evidence:
        lines.append(f"   Evidence     : {indicator.evidence}")

    if indicator.offset is not None:
        lines.append(f"   Offset       : {indicator.offset}")

    if indicator.source:
        lines.append(f"   Source       : {indicator.source}")

    lines.append("")

    return lines


def build_json_report(scan_result: ScanResult, indent: int = 2) -> str:
    """
    Membuat report dalam bentuk JSON string.
    """

    report_dict = build_report_dict(scan_result)

    return json.dumps(
        report_dict,
        indent=indent,
        ensure_ascii=False,
    )


def save_json_report(
    scan_result: ScanResult,
    output_dir: str | Path = "output/reports",
) -> Path:
    """
    Menyimpan report JSON ke folder output.
    """

    output_path = prepare_output_path(
        scan_result=scan_result,
        output_dir=output_dir,
        extension=".json",
    )

    json_report = build_json_report(scan_result)

    output_path.write_text(json_report, encoding="utf-8")

    return output_path


def save_text_report(
    scan_result: ScanResult,
    output_dir: str | Path = "output/reports",
) -> Path:
    """
    Menyimpan report TXT ke folder output.
    """

    output_path = prepare_output_path(
        scan_result=scan_result,
        output_dir=output_dir,
        extension=".txt",
    )

    text_report = build_text_report(scan_result)

    output_path.write_text(text_report, encoding="utf-8")

    return output_path


def prepare_output_path(
    scan_result: ScanResult,
    output_dir: str | Path,
    extension: str,
) -> Path:
    """
    Membuat path output report.

    Contoh:
    output/reports/undangan_pdf_20260630_130000.json
    """

    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)

    file_name = scan_result.file_info.file_name
    safe_name = make_safe_filename(file_name)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file_name = f"{safe_name}_{timestamp}{extension}"

    return output_directory / output_file_name


def make_safe_filename(file_name: str) -> str:
    """
    Mengubah nama file agar aman untuk nama report.
    """

    safe_chars = []

    for char in file_name:
        if char.isalnum():
            safe_chars.append(char)
        elif char in {".", "-", "_"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")

    safe_name = "".join(safe_chars).strip("._")

    if not safe_name:
        safe_name = "scan_report"

    return safe_name[:80]


def format_file_size(size_bytes: int) -> str:
    """
    Format ukuran file agar mudah dibaca.
    """

    if size_bytes < 1024:
        return f"{size_bytes} B"

    size_kb = size_bytes / 1024

    if size_kb < 1024:
        return f"{size_kb:.2f} KB"

    size_mb = size_kb / 1024

    if size_mb < 1024:
        return f"{size_mb:.2f} MB"

    size_gb = size_mb / 1024

    return f"{size_gb:.2f} GB"