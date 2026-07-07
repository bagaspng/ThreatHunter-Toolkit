from pathlib import Path
from typing import Any

from src.core.models import Indicator


DEFAULT_RISK_LEVELS = {
    "clean_max": 29,
    "suspicious_max": 59,
    "malicious_min": 60,
}


def calculate_risk_score(indicators: list[Indicator], max_score: int = 100) -> int:
    """
    Menghitung total skor risiko dari semua indikator.

    Skor akhir dibatasi maksimal 100 agar mudah dibaca.
    """

    total_score = 0

    for indicator in indicators:
        if indicator.score > 0:
            total_score += indicator.score

    return min(total_score, max_score)


def get_risk_status(
    risk_score: int,
    risk_levels: dict[str, int] | None = None,
) -> str:
    """
    Mengubah skor menjadi status risiko.
    """

    levels = risk_levels or DEFAULT_RISK_LEVELS

    if risk_score <= levels["clean_max"]:
        return "Clean"

    if risk_score <= levels["suspicious_max"]:
        return "Suspicious"

    return "Malicious Indicator"


def make_indicator(
    name: str,
    category: str,
    severity: str,
    score: int,
    description: str,
    evidence: str | None = None,
    offset: int | None = None,
    source: str | None = None,
) -> Indicator:
    """
    Helper untuk membuat Indicator agar formatnya konsisten.
    """

    return Indicator(
        name=name,
        category=category,
        severity=severity,
        score=score,
        description=description,
        evidence=evidence,
        offset=offset,
        source=source,
    )


def load_thresholds_from_yaml(config_path: str | Path) -> dict[str, Any]:
    """
    Optional: membaca threshold dari file YAML.

    Jika PyYAML belum terpasang atau file tidak ada,
    scanner tetap bisa berjalan dengan default threshold.
    """

    path = Path(config_path)

    if not path.exists():
        return {}

    try:
        import yaml
    except ImportError:
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    return data