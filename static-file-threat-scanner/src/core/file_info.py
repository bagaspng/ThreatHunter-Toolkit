from pathlib import Path
import mimetypes

from src.core.magic_detector import detect_file_type_from_bytes, get_magic_hex
from src.core.models import FileInfo


def get_file_info(file_path: str | Path) -> FileInfo:
    """
    Mengambil informasi dasar file:
    - nama file
    - path
    - ukuran
    - ekstensi yang diklaim
    - tipe asli berdasarkan magic bytes
    - mime hint dari ekstensi
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    if not path.is_file():
        raise ValueError(f"Path bukan file: {path}")

    file_size = path.stat().st_size
    claimed_extension = path.suffix.lower()

    with path.open("rb") as file:
        header = file.read(4096)

    detected_type = detect_file_type_from_bytes(header)
    magic_hex = get_magic_hex(header)

    mime_hint, _ = mimetypes.guess_type(str(path))

    return FileInfo(
        file_name=path.name,
        file_path=str(path.resolve()),
        file_size=file_size,
        claimed_extension=claimed_extension,
        detected_type=detected_type,
        mime_hint=mime_hint,
        magic_hex=magic_hex,
    )


def is_supported_extension(extension: str) -> bool:
    """
    Mengecek apakah ekstensi termasuk target scanner.
    """

    supported_extensions = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
    }

    return extension.lower() in supported_extensions


def is_extension_match_detected_type(extension: str, detected_type: str) -> bool:
    """
    Mengecek apakah ekstensi sesuai dengan tipe asli file.
    """

    extension = extension.lower()

    expected_map = {
        ".pdf": "PDF",
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".svg": "SVG",
    }

    expected_type = expected_map.get(extension)

    if expected_type is None:
        return False

    return expected_type == detected_type