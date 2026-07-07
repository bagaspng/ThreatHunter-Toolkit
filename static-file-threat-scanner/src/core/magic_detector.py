from pathlib import Path


PDF_SIGNATURE = b"%PDF"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
ZIP_SIGNATURES = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
)
EXE_SIGNATURE = b"MZ"


def detect_file_type_from_bytes(file_bytes: bytes) -> str:
    """
    Mendeteksi tipe file berdasarkan magic bytes / signature awal file.

    Output utama:
    - PDF
    - PNG
    - JPEG
    - SVG
    - ZIP/APK
    - EXE
    - UNKNOWN
    """

    if not file_bytes:
        return "UNKNOWN"

    header = file_bytes[:4096]

    if header.startswith(PDF_SIGNATURE):
        return "PDF"

    if header.startswith(PNG_SIGNATURE):
        return "PNG"

    if header.startswith(JPEG_SIGNATURE):
        return "JPEG"

    if header.startswith(EXE_SIGNATURE):
        return "EXE"

    if any(header.startswith(signature) for signature in ZIP_SIGNATURES):
        return "ZIP/APK"

    if _looks_like_svg(header):
        return "SVG"

    return "UNKNOWN"


def detect_file_type(file_path: str | Path, read_size: int = 4096) -> str:
    """
    Membaca beberapa byte awal file, lalu mendeteksi tipe file.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    with path.open("rb") as file:
        header = file.read(read_size)

    return detect_file_type_from_bytes(header)


def get_magic_hex(file_bytes: bytes, length: int = 16) -> str:
    """
    Mengambil byte awal file dalam bentuk hex agar bisa ditampilkan di report.
    """

    return file_bytes[:length].hex(" ").upper()


def _looks_like_svg(header: bytes) -> bool:
    """
    SVG adalah file XML/text, jadi deteksinya tidak selalu dari magic bytes tetap.

    Contoh awal SVG:
    <svg ...
    <?xml version="1.0"?><svg ...
    """

    try:
        text = header.decode("utf-8", errors="ignore").lower()
    except Exception:
        return False

    text = text.lstrip("\ufeff").strip()

    if text.startswith("<svg"):
        return True

    if text.startswith("<?xml") and "<svg" in text:
        return True

    return False