"""
Report modules for Static File Threat Scanner.

Folder ini bertugas membuat output hasil scan dalam bentuk:
- console output
- dictionary
- JSON
- TXT report
"""

from src.reports.report_builder import (
    build_report_dict,
    build_text_report,
    build_json_report,
    save_json_report,
    save_text_report,
)

from src.reports.console_report import print_scan_result

__all__ = [
    "build_report_dict",
    "build_text_report",
    "build_json_report",
    "save_json_report",
    "save_text_report",
    "print_scan_result",
]