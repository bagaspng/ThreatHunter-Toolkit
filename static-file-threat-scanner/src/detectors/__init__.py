"""
Reusable detector modules for Static File Threat Scanner.

Detector adalah modul kecil yang dapat dipakai ulang oleh analyzer.
Setiap detector fokus pada satu jenis indikator, misalnya:

- embedded file signature
- suspicious string
- URL / IP
- base64
- APK indicator

Semua detector harus aman:
- tidak menjalankan file
- tidak mengekstrak payload untuk dijalankan
- hanya membaca bytes/text
"""

from src.detectors.embedded_file_detector import detect_embedded_files
from src.detectors.suspicious_string_detector import detect_suspicious_strings
from src.detectors.url_detector import detect_network_indicators
from src.detectors.base64_detector import detect_base64_strings
from src.detectors.apk_indicator_detector import detect_apk_indicators

__all__ = [
    "detect_embedded_files",
    "detect_suspicious_strings",
    "detect_network_indicators",
    "detect_base64_strings",
    "detect_apk_indicators",
]

