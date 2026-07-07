"""
File-specific analyzers for Static File Threat Scanner.

Setiap analyzer wajib menyediakan function:

def analyze(file_path, file_bytes, file_info) -> list[Indicator]
"""

__all__ = [
    "generic_analyzer",
    "pdf_analyzer",
    "png_analyzer",
    "jpg_analyzer",
    "svg_analyzer",
]