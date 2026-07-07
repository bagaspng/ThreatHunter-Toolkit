from __future__ import annotations

from src.core.models import ScanResult, Indicator
from src.reports.report_builder import format_file_size, build_recommendation


def print_scan_result(scan_result: ScanResult) -> None:
    """
    Menampilkan hasil scan ke terminal.

    Jika library rich tersedia, output akan lebih rapi.
    Jika rich tidak tersedia, fallback ke print biasa.
    """

    try:
        _print_with_rich(scan_result)
    except ImportError:
        _print_plain(scan_result)


def _print_with_rich(scan_result: ScanResult) -> None:
    """
    Print report memakai rich.
    """

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()

    file_info = scan_result.file_info
    hashes = scan_result.hashes

    title = Text("Static File Threat Scanner", style="bold")
    console.print(Panel(title, subtitle="Static Analysis Report", expand=False))

    file_table = Table(title="File Information", show_header=True, header_style="bold")
    file_table.add_column("Field", style="bold")
    file_table.add_column("Value")

    file_table.add_row("File Name", file_info.file_name)
    file_table.add_row("File Size", format_file_size(file_info.file_size))
    file_table.add_row("Claimed Extension", file_info.claimed_extension or "-")
    file_table.add_row("Detected Type", file_info.detected_type)
    file_table.add_row("MIME Hint", file_info.mime_hint or "-")
    file_table.add_row("Magic Hex", file_info.magic_hex or "-")

    console.print(file_table)

    hash_table = Table(title="Hashes", show_header=True, header_style="bold")
    hash_table.add_column("Algorithm", style="bold")
    hash_table.add_column("Value")

    hash_table.add_row("MD5", hashes.get("md5", "-"))
    hash_table.add_row("SHA1", hashes.get("sha1", "-"))
    hash_table.add_row("SHA256", hashes.get("sha256", "-"))

    console.print(hash_table)

    risk_style = _get_risk_style(scan_result.risk_status)

    risk_text = (
        f"Risk Score  : {scan_result.risk_score}/100\n"
        f"Risk Status : {scan_result.risk_status}\n"
        f"Duration    : {scan_result.duration_seconds} seconds"
    )

    console.print(
        Panel(
            risk_text,
            title="Risk Result",
            border_style=risk_style,
        )
    )

    if scan_result.warnings:
        warning_text = "\n".join(f"[!] {warning}" for warning in scan_result.warnings)

        console.print(
            Panel(
                warning_text,
                title="Warnings",
                border_style="yellow",
            )
        )

    indicator_table = Table(title="Indicators Found", show_header=True, header_style="bold")
    indicator_table.add_column("#", justify="right")
    indicator_table.add_column("Name")
    indicator_table.add_column("Severity")
    indicator_table.add_column("Score", justify="right")
    indicator_table.add_column("Evidence")

    if not scan_result.indicators:
        indicator_table.add_row("-", "No suspicious indicators found", "-", "-", "-")
    else:
        for index, indicator in enumerate(scan_result.indicators, start=1):
            indicator_table.add_row(
                str(index),
                indicator.name,
                indicator.severity,
                f"+{indicator.score}",
                _shorten(indicator.evidence or "-", 80),
            )

    console.print(indicator_table)

    if scan_result.indicators:
        detail_text = _build_indicator_details(scan_result.indicators)

        console.print(
            Panel(
                detail_text,
                title="Indicator Details",
                border_style="cyan",
            )
        )

    recommendation = build_recommendation(scan_result)

    console.print(
        Panel(
            recommendation,
            title="Recommendation",
            border_style=risk_style,
        )
    )

    disclaimer = (
        "This tool uses static analysis only. "
        "It does not execute the scanned file. "
        "False positives and false negatives are possible."
    )

    console.print(
        Panel(
            disclaimer,
            title="Disclaimer",
            border_style="dim",
        )
    )


def _print_plain(scan_result: ScanResult) -> None:
    """
    Fallback print tanpa rich.
    """

    file_info = scan_result.file_info
    hashes = scan_result.hashes

    print("=" * 72)
    print("STATIC FILE THREAT SCANNER REPORT")
    print("=" * 72)
    print("")
    print("File Information")
    print("-" * 72)
    print(f"File Name       : {file_info.file_name}")
    print(f"File Path       : {file_info.file_path}")
    print(f"File Size       : {format_file_size(file_info.file_size)}")
    print(f"Claimed Ext     : {file_info.claimed_extension}")
    print(f"Detected Type   : {file_info.detected_type}")
    print(f"MIME Hint       : {file_info.mime_hint or '-'}")
    print(f"Magic Hex       : {file_info.magic_hex or '-'}")
    print("")
    print("Hashes")
    print("-" * 72)
    print(f"MD5             : {hashes.get('md5', '-')}")
    print(f"SHA1            : {hashes.get('sha1', '-')}")
    print(f"SHA256          : {hashes.get('sha256', '-')}")
    print("")
    print("Risk Result")
    print("-" * 72)
    print(f"Risk Score      : {scan_result.risk_score}/100")
    print(f"Risk Status     : {scan_result.risk_status}")
    print(f"Duration        : {scan_result.duration_seconds} seconds")
    print("")

    if scan_result.warnings:
        print("Warnings")
        print("-" * 72)

        for warning in scan_result.warnings:
            print(f"[!] {warning}")

        print("")

    print("Indicators")
    print("-" * 72)

    if not scan_result.indicators:
        print("No suspicious indicators found.")
    else:
        for index, indicator in enumerate(scan_result.indicators, start=1):
            print(f"{index}. {indicator.name}")
            print(f"   Category     : {indicator.category}")
            print(f"   Severity     : {indicator.severity}")
            print(f"   Score        : +{indicator.score}")
            print(f"   Description  : {indicator.description}")

            if indicator.evidence:
                print(f"   Evidence     : {indicator.evidence}")

            if indicator.offset is not None:
                print(f"   Offset       : {indicator.offset}")

            if indicator.source:
                print(f"   Source       : {indicator.source}")

            print("")

    print("Recommendation")
    print("-" * 72)
    print(build_recommendation(scan_result))
    print("")
    print("Disclaimer")
    print("-" * 72)
    print(
        "This tool uses static analysis only. "
        "It does not execute the scanned file. "
        "False positives and false negatives are possible."
    )
    print("=" * 72)


def _get_risk_style(risk_status: str) -> str:
    """
    Menentukan style warna berdasarkan status risiko.
    """

    status = risk_status.lower()

    if status == "clean":
        return "green"

    if status == "suspicious":
        return "yellow"

    return "red"


def _build_indicator_details(indicators: list[Indicator]) -> str:
    """
    Membuat detail indikator dalam bentuk teks.
    """

    lines: list[str] = []

    for index, indicator in enumerate(indicators, start=1):
        lines.append(f"{index}. {indicator.name}")
        lines.append(f"   Category    : {indicator.category}")
        lines.append(f"   Severity    : {indicator.severity}")
        lines.append(f"   Score       : +{indicator.score}")
        lines.append(f"   Description : {indicator.description}")

        if indicator.evidence:
            lines.append(f"   Evidence    : {_shorten(indicator.evidence, 140)}")

        if indicator.offset is not None:
            lines.append(f"   Offset      : {indicator.offset}")

        if indicator.source:
            lines.append(f"   Source      : {indicator.source}")

        lines.append("")

    return "\n".join(lines).strip()


def _shorten(text: str, max_length: int = 80) -> str:
    """
    Memotong teks panjang agar tampilan terminal tetap rapi.
    """

    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."