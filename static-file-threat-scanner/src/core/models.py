from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Indicator:
    """
    Satu temuan/indikator mencurigakan dari hasil analisis file.
    """

    name: str
    category: str
    severity: str
    score: int
    description: str
    evidence: str | None = None
    offset: int | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileInfo:
    """
    Informasi dasar file yang sedang dipindai.
    """

    file_name: str
    file_path: str
    file_size: int
    claimed_extension: str
    detected_type: str
    mime_hint: str | None = None
    magic_hex: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    """
    Hasil akhir proses scanning.
    """

    file_info: FileInfo
    hashes: dict[str, str]
    indicators: list[Indicator] = field(default_factory=list)
    risk_score: int = 0
    risk_status: str = "Clean"
    duration_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_info": self.file_info.to_dict(),
            "hashes": self.hashes,
            "indicators": [indicator.to_dict() for indicator in self.indicators],
            "risk_score": self.risk_score,
            "risk_status": self.risk_status,
            "duration_seconds": self.duration_seconds,
            "warnings": self.warnings,
        }