from pathlib import Path
import math
from collections import Counter


def calculate_entropy(data: bytes) -> float:
    """
    Menghitung Shannon entropy dari bytes.

    Nilai umum:
    - 0.0       : sangat repetitif
    - 4.0 - 6.5 : cukup normal untuk teks/struktur biasa
    - 7.0+      : sangat acak, bisa terkompresi/encrypted/obfuscated

    Catatan:
    Entropy tinggi tidak otomatis berarti malware.
    """

    if not data:
        return 0.0

    byte_counts = Counter(data)
    data_length = len(data)

    entropy = 0.0

    for count in byte_counts.values():
        probability = count / data_length
        entropy -= probability * math.log2(probability)

    return round(entropy, 4)


def calculate_file_entropy(file_path: str | Path) -> float:
    """
    Menghitung entropy keseluruhan file.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    data = path.read_bytes()
    return calculate_entropy(data)


def find_high_entropy_sections(
    data: bytes,
    window_size: int = 4096,
    threshold: float = 7.5,
) -> list[dict]:
    """
    Mencari bagian file yang memiliki entropy tinggi.

    Berguna untuk mendeteksi bagian yang tampak seperti:
    - terenkripsi
    - terkompresi
    - obfuscated
    - payload tersembunyi

    Return:
    [
        {
            "offset": 0,
            "size": 4096,
            "entropy": 7.81
        }
    ]
    """

    if not data:
        return []

    sections = []

    for offset in range(0, len(data), window_size):
        chunk = data[offset : offset + window_size]

        if len(chunk) < 512:
            continue

        entropy = calculate_entropy(chunk)

        if entropy >= threshold:
            sections.append(
                {
                    "offset": offset,
                    "size": len(chunk),
                    "entropy": entropy,
                }
            )

    return sections