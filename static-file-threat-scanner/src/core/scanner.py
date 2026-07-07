from pathlib import Path
from time import perf_counter
from importlib import import_module
from collections.abc import Callable

from src.core.file_info import (
    get_file_info,
    is_supported_extension,
    is_extension_match_detected_type,
)
from src.core.hash_utils import calculate_hashes
from src.core.models import Indicator, ScanResult, FileInfo
from src.core.scoring import (
    calculate_risk_score,
    get_risk_status,
    make_indicator,
)


AnalyzerFunction = Callable[..., list[Indicator]]


class StaticFileScanner:
    """
    Core scanner untuk melakukan analisis statis.

    Scanner ini TIDAK menjalankan file.
    Scanner hanya membaca file sebagai bytes dan menjalankan analyzer sesuai tipe file.
    """

    def __init__(self, max_file_size_mb: int = 100):
        self.max_file_size = max_file_size_mb * 1024 * 1024

    def scan(self, file_path: str | Path) -> ScanResult:
        """
        Alur utama:
        1. Validasi file
        2. Ambil file info
        3. Hitung hash
        4. Baca bytes
        5. Cek mismatch ekstensi
        6. Pilih analyzer
        7. Hitung skor
        8. Return ScanResult
        """

        start_time = perf_counter()
        path = Path(file_path)

        self._validate_file(path)

        file_info = get_file_info(path)
        hashes = calculate_hashes(path)

        warnings: list[str] = []
        indicators: list[Indicator] = []

        if file_info.file_size > self.max_file_size:
            warnings.append(
                f"Ukuran file melebihi batas {self.max_file_size} bytes. "
                "Analisis mungkin perlu dibatasi."
            )

        file_bytes = path.read_bytes()

        indicators.extend(self._run_core_checks(file_info))
        indicators.extend(self._run_selected_analyzers(path, file_bytes, file_info))

        risk_score = calculate_risk_score(indicators)
        risk_status = get_risk_status(risk_score)

        duration = round(perf_counter() - start_time, 4)

        return ScanResult(
            file_info=file_info,
            hashes=hashes,
            indicators=indicators,
            risk_score=risk_score,
            risk_status=risk_status,
            duration_seconds=duration,
            warnings=warnings,
        )

    def _validate_file(self, path: Path) -> None:
        """
        Validasi awal.
        """

        if not path.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {path}")

        if not path.is_file():
            raise ValueError(f"Path bukan file: {path}")

    def _run_core_checks(self, file_info: FileInfo) -> list[Indicator]:
        """
        Core check yang tidak bergantung pada analyzer khusus.
        """

        indicators: list[Indicator] = []

        if not is_supported_extension(file_info.claimed_extension):
            indicators.append(
                make_indicator(
                    name="Unsupported Extension",
                    category="file_info",
                    severity="low",
                    score=0,
                    description=(
                        "Ekstensi file tidak termasuk target utama scanner. "
                        "Scanner tetap dapat berjalan, tetapi hasil mungkin terbatas."
                    ),
                    evidence=file_info.claimed_extension,
                    source="core.scanner",
                )
            )

        if file_info.claimed_extension and not is_extension_match_detected_type(
            file_info.claimed_extension,
            file_info.detected_type,
        ):
            indicators.append(
                make_indicator(
                    name="Extension and Magic Bytes Mismatch",
                    category="file_type",
                    severity="high",
                    score=25,
                    description=(
                        "Ekstensi file tidak sesuai dengan tipe asli berdasarkan magic bytes."
                    ),
                    evidence=(
                        f"extension={file_info.claimed_extension}, "
                        f"detected_type={file_info.detected_type}"
                    ),
                    source="core.scanner",
                )
            )

        if file_info.claimed_extension in {".pdf", ".png", ".jpg", ".jpeg", ".svg"}:
            if file_info.detected_type in {"EXE", "ZIP/APK"}:
                indicators.append(
                    make_indicator(
                        name="Dangerous File Masquerading as Document or Image",
                        category="file_type",
                        severity="critical",
                        score=40,
                        description=(
                            "File menggunakan ekstensi dokumen/gambar, tetapi tipe aslinya "
                            "terdeteksi sebagai executable atau archive."
                        ),
                        evidence=(
                            f"extension={file_info.claimed_extension}, "
                            f"detected_type={file_info.detected_type}"
                        ),
                        source="core.scanner",
                    )
                )

        return indicators

    def _run_selected_analyzers(
        self,
        file_path: Path,
        file_bytes: bytes,
        file_info: FileInfo,
    ) -> list[Indicator]:
        """
        Menjalankan analyzer berdasarkan detected_type.

        File analyzer belum wajib ada sekarang.
        Kalau modul analyzer belum dibuat, scanner tetap berjalan.
        """

        indicators: list[Indicator] = []

        analyzer_names = self._get_analyzer_names(file_info)

        for analyzer_name in analyzer_names:
            analyzer = self._load_analyzer(analyzer_name)

            if analyzer is None:
                continue

            try:
                result = analyzer(
                    file_path=file_path,
                    file_bytes=file_bytes,
                    file_info=file_info,
                )

                if result:
                    indicators.extend(result)

            except Exception as error:
                indicators.append(
                    make_indicator(
                        name="Analyzer Error",
                        category="internal",
                        severity="low",
                        score=0,
                        description=(
                            "Analyzer mengalami error saat membaca file. "
                            "File tidak dijalankan, hanya proses analisis yang gagal."
                        ),
                        evidence=f"{analyzer_name}: {error}",
                        source="core.scanner",
                    )
                )

        return indicators

    def _get_analyzer_names(self, file_info: FileInfo) -> list[str]:
        """
        Menentukan analyzer yang perlu dijalankan.

        Catatan:
        - generic_analyzer dapat dijalankan untuk semua file.
        - analyzer khusus dijalankan berdasarkan detected_type.
        """

        analyzers = ["generic_analyzer"]

        detected_type = file_info.detected_type

        if detected_type == "PDF":
            analyzers.append("pdf_analyzer")

        elif detected_type == "PNG":
            analyzers.append("png_analyzer")

        elif detected_type == "JPEG":
            analyzers.append("jpg_analyzer")

        elif detected_type == "SVG":
            analyzers.append("svg_analyzer")

        else:
            # Kalau detected type UNKNOWN tetapi ekstensi dikenal,
            # tetap coba analyzer berdasarkan ekstensi.
            extension_map = {
                ".pdf": "pdf_analyzer",
                ".png": "png_analyzer",
                ".jpg": "jpg_analyzer",
                ".jpeg": "jpg_analyzer",
                ".svg": "svg_analyzer",
            }

            analyzer = extension_map.get(file_info.claimed_extension)

            if analyzer:
                analyzers.append(analyzer)

        return list(dict.fromkeys(analyzers))

    def _load_analyzer(self, analyzer_name: str) -> AnalyzerFunction | None:
        """
        Dynamic import analyzer dari folder src/analyzers/.

        Analyzer diharapkan punya function bernama:
        analyze(file_path, file_bytes, file_info)

        Contoh:
        src/analyzers/pdf_analyzer.py

        def analyze(file_path, file_bytes, file_info):
            return [...]
        """

        module_path = f"src.analyzers.{analyzer_name}"

        try:
            module = import_module(module_path)
        except ModuleNotFoundError:
            return None

        analyze_func = getattr(module, "analyze", None)

        if analyze_func is None:
            return None

        return analyze_func


def scan_file(file_path: str | Path) -> ScanResult:
    """
    Helper function agar bisa dipanggil langsung dari main.py.
    """

    scanner = StaticFileScanner()
    return scanner.scan(file_path)