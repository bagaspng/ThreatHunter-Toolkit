from pathlib import Path
import hashlib


def calculate_hashes(file_path: str | Path, chunk_size: int = 1024 * 1024) -> dict[str, str]:
    """
    Menghitung MD5, SHA1, dan SHA256 dari file.

    File dibaca per chunk agar aman untuk file berukuran besar.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    if not path.is_file():
        raise ValueError(f"Path bukan file: {path}")

    md5_hash = hashlib.md5()
    sha1_hash = hashlib.sha1()
    sha256_hash = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            md5_hash.update(chunk)
            sha1_hash.update(chunk)
            sha256_hash.update(chunk)

    return {
        "md5": md5_hash.hexdigest(),
        "sha1": sha1_hash.hexdigest(),
        "sha256": sha256_hash.hexdigest(),
    }