from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.core.scanner import StaticFileScanner
from src.reports.console_report import print_scan_result
from src.reports.report_builder import (
    build_json_report,
    save_json_report,
    save_text_report,
)


APP_NAME = "Static File Threat Scanner"
APP_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description=(
            "Static malware indicator scanner untuk file PDF dan gambar "
            "(PNG, JPG/JPEG, SVG). Scanner ini tidak menjalankan file."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan satu file",
        description="Scan file PDF, PNG, JPG/JPEG, atau SVG secara statis.",
    )

    scan_parser.add_argument(
        "file",
        help="Path file yang ingin discan",
    )

    scan_parser.add_argument(
        "--json",
        action="store_true",
        help="Tampilkan hasil dalam format JSON (default)",
    )

    scan_parser.add_argument(
        "--text",
        action="store_true",
        help="Tampilkan hasil dalam format teks (console)",
    )

    scan_parser.add_argument(
        "--save",
        action="store_true",
        help="Simpan report dalam format JSON dan TXT",
    )

    scan_parser.add_argument(
        "--save-json",
        action="store_true",
        help="Simpan report dalam format JSON",
    )

    scan_parser.add_argument(
        "--save-txt",
        action="store_true",
        help="Simpan report dalam format TXT",
    )

    scan_parser.add_argument(
        "--output-dir",
        default="output/reports",
        help="Folder output report. Default: output/reports",
    )

    scan_parser.add_argument(
        "--max-size-mb",
        type=int,
        default=100,
        help="Batas ukuran file dalam MB. Default: 100",
    )

    scan_parser.add_argument(
        "--fail-on-risk",
        action="store_true",
        help=(
            "Return exit code 2 jika hasil Suspicious atau Malicious Indicator. "
            "Berguna untuk automation."
        ),
    )

    return parser


def run_scan(args: argparse.Namespace) -> int:
    file_path = Path(args.file)

    scanner = StaticFileScanner(max_file_size_mb=args.max_size_mb)

    try:
        scan_result = scanner.scan(file_path)
    except FileNotFoundError as error:
        print_error(str(error))
        return 1
    except PermissionError:
        print_error(f"Tidak punya izin membaca file: {file_path}")
        return 1
    except IsADirectoryError:
        print_error(f"Path adalah folder, bukan file: {file_path}")
        return 1
    except Exception as error:
        print_error(f"Terjadi error saat scanning: {error}")
        return 1

    if args.text:
        print_scan_result(scan_result)
    else:
        print(build_json_report(scan_result))

    saved_paths: list[Path] = []

    should_save_json = args.save or args.save_json
    should_save_txt = args.save or args.save_txt

    if should_save_json:
        try:
            json_path = save_json_report(
                scan_result=scan_result,
                output_dir=args.output_dir,
            )
            saved_paths.append(json_path)
        except Exception as error:
            print_error(f"Gagal menyimpan JSON report: {error}")
            return 1

    if should_save_txt:
        try:
            txt_path = save_text_report(
                scan_result=scan_result,
                output_dir=args.output_dir,
            )
            saved_paths.append(txt_path)
        except Exception as error:
            print_error(f"Gagal menyimpan TXT report: {error}")
            return 1

    if saved_paths:
        for path in saved_paths:
            print_info(f"Report saved: {path}")

    if args.fail_on_risk and scan_result.risk_status.lower() != "clean":
        return 2

    return 0


def print_error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


def print_info(message: str) -> None:
    print(f"[INFO] {message}", file=sys.stderr)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        return run_scan(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())