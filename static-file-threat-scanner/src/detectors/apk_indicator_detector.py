from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.core.models import Indicator
from src.core.scoring import make_indicator


@dataclass(frozen=True)
class APKIndicatorRule:
    name: str
    pattern: bytes
    category: str
    severity: str
    score: int
    description: str


APK_STRUCTURE_RULES: list[APKIndicatorRule] = [
    APKIndicatorRule(
        name="Android Manifest Found",
        pattern=b"AndroidManifest.xml",
        category="apk_structure",
        severity="high",
        score=25,
        description=(
            "Ditemukan AndroidManifest.xml yang merupakan komponen penting dalam APK Android."
        ),
    ),
    APKIndicatorRule(
        name="Android Classes DEX Found",
        pattern=b"classes.dex",
        category="apk_structure",
        severity="high",
        score=25,
        description=(
            "Ditemukan classes.dex yang berisi bytecode aplikasi Android."
        ),
    ),
    APKIndicatorRule(
        name="Android Resources Found",
        pattern=b"resources.arsc",
        category="apk_structure",
        severity="medium",
        score=15,
        description=(
            "Ditemukan resources.arsc yang umum terdapat dalam APK Android."
        ),
    ),
    APKIndicatorRule(
        name="APK META-INF Found",
        pattern=b"META-INF/",
        category="apk_structure",
        severity="medium",
        score=15,
        description=(
            "Ditemukan folder META-INF yang umum terdapat dalam APK atau archive Java."
        ),
    ),
    APKIndicatorRule(
        name="APK Native Library Folder Found",
        pattern=b"lib/",
        category="apk_structure",
        severity="low",
        score=5,
        description=(
            "Ditemukan folder lib/ yang dapat muncul pada APK dengan native library."
        ),
    ),
]


ANDROID_PERMISSION_RULES: list[APKIndicatorRule] = [
    APKIndicatorRule(
        name="Android Permission SEND_SMS Found",
        pattern=b"SEND_SMS",
        category="apk_permission",
        severity="critical",
        score=25,
        description=(
            "Ditemukan permission SEND_SMS. Permission ini sensitif karena dapat digunakan "
            "untuk mengirim SMS."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission READ_SMS Found",
        pattern=b"READ_SMS",
        category="apk_permission",
        severity="high",
        score=20,
        description=(
            "Ditemukan permission READ_SMS. Permission ini sensitif karena dapat membaca SMS."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission RECEIVE_SMS Found",
        pattern=b"RECEIVE_SMS",
        category="apk_permission",
        severity="high",
        score=20,
        description=(
            "Ditemukan permission RECEIVE_SMS. Permission ini berkaitan dengan penerimaan SMS."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission READ_CONTACTS Found",
        pattern=b"READ_CONTACTS",
        category="apk_permission",
        severity="high",
        score=20,
        description=(
            "Ditemukan permission READ_CONTACTS. Permission ini dapat membaca kontak pengguna."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission WRITE_CONTACTS Found",
        pattern=b"WRITE_CONTACTS",
        category="apk_permission",
        severity="medium",
        score=15,
        description=(
            "Ditemukan permission WRITE_CONTACTS. Permission ini dapat mengubah kontak pengguna."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission ACCESS_FINE_LOCATION Found",
        pattern=b"ACCESS_FINE_LOCATION",
        category="apk_permission",
        severity="medium",
        score=15,
        description=(
            "Ditemukan permission ACCESS_FINE_LOCATION. Permission ini berkaitan dengan lokasi presisi."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission ACCESS_COARSE_LOCATION Found",
        pattern=b"ACCESS_COARSE_LOCATION",
        category="apk_permission",
        severity="low",
        score=10,
        description=(
            "Ditemukan permission ACCESS_COARSE_LOCATION. Permission ini berkaitan dengan lokasi kasar."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission READ_PHONE_STATE Found",
        pattern=b"READ_PHONE_STATE",
        category="apk_permission",
        severity="medium",
        score=15,
        description=(
            "Ditemukan permission READ_PHONE_STATE. Permission ini dapat membaca informasi perangkat."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission RECEIVE_BOOT_COMPLETED Found",
        pattern=b"RECEIVE_BOOT_COMPLETED",
        category="apk_permission",
        severity="medium",
        score=15,
        description=(
            "Ditemukan permission RECEIVE_BOOT_COMPLETED. Aplikasi dapat aktif setelah perangkat boot."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission REQUEST_INSTALL_PACKAGES Found",
        pattern=b"REQUEST_INSTALL_PACKAGES",
        category="apk_permission",
        severity="high",
        score=20,
        description=(
            "Ditemukan permission REQUEST_INSTALL_PACKAGES. Permission ini dapat berkaitan "
            "dengan pemasangan aplikasi lain."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission SYSTEM_ALERT_WINDOW Found",
        pattern=b"SYSTEM_ALERT_WINDOW",
        category="apk_permission",
        severity="high",
        score=20,
        description=(
            "Ditemukan permission SYSTEM_ALERT_WINDOW. Permission ini dapat membuat overlay di layar."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission RECORD_AUDIO Found",
        pattern=b"RECORD_AUDIO",
        category="apk_permission",
        severity="medium",
        score=15,
        description=(
            "Ditemukan permission RECORD_AUDIO. Permission ini berkaitan dengan akses mikrofon."
        ),
    ),
    APKIndicatorRule(
        name="Android Permission CAMERA Found",
        pattern=b"CAMERA",
        category="apk_permission",
        severity="medium",
        score=15,
        description=(
            "Ditemukan permission CAMERA. Permission ini berkaitan dengan akses kamera."
        ),
    ),
]


def detect_apk_indicators(
    file_bytes: bytes,
    structure_rules: Iterable[APKIndicatorRule] | None = None,
    permission_rules: Iterable[APKIndicatorRule] | None = None,
) -> list[Indicator]:
    """
    Mendeteksi indikator APK di dalam file.

    Cocok untuk kasus:
    - PDF yang menyisipkan APK
    - PNG/JPG yang ditempeli payload APK
    - SVG yang mengandung string APK
    - file dengan ekstensi palsu
    """

    indicators: list[Indicator] = []

    indicators.extend(
        _detect_rules(
            file_bytes=file_bytes,
            rules=list(structure_rules or APK_STRUCTURE_RULES),
            source="detectors.apk_indicator_detector",
        )
    )

    indicators.extend(
        _detect_rules(
            file_bytes=file_bytes,
            rules=list(permission_rules or ANDROID_PERMISSION_RULES),
            source="detectors.apk_indicator_detector",
        )
    )

    # Indikator gabungan: jika struktur APK dan permission ditemukan,
    # berarti kecurigaan lebih kuat.
    has_structure = any(ind.category == "apk_structure" for ind in indicators)
    has_permission = any(ind.category == "apk_permission" for ind in indicators)

    if has_structure and has_permission:
        indicators.append(
            make_indicator(
                name="Strong APK Payload Indicator",
                category="apk_indicator",
                severity="critical",
                score=25,
                description=(
                    "Ditemukan kombinasi struktur APK dan permission Android sensitif. "
                    "Ini merupakan indikator kuat bahwa file mengandung komponen APK."
                ),
                evidence="APK structure + Android permission",
                source="detectors.apk_indicator_detector",
            )
        )

    return indicators


def _detect_rules(
    file_bytes: bytes,
    rules: list[APKIndicatorRule],
    source: str,
) -> list[Indicator]:
    lower_bytes = file_bytes.lower()
    indicators: list[Indicator] = []

    for rule in rules:
        offset = lower_bytes.find(rule.pattern.lower())

        if offset == -1:
            continue

        indicators.append(
            make_indicator(
                name=rule.name,
                category=rule.category,
                severity=rule.severity,
                score=rule.score,
                description=rule.description,
                evidence=f"pattern={rule.pattern.decode('utf-8', errors='replace')}, offset={offset}",
                offset=offset,
                source=source,
            )
        )

    return indicators


def extract_apk_permissions(file_bytes: bytes) -> list[str]:
    """
    Mengambil daftar permission Android yang ditemukan.

    Fungsi ini berguna kalau nanti kamu ingin menampilkan permission
    secara khusus di report.
    """

    lower_bytes = file_bytes.lower()
    permissions: list[str] = []

    for rule in ANDROID_PERMISSION_RULES:
        if rule.pattern.lower() in lower_bytes:
            permissions.append(rule.pattern.decode("utf-8", errors="replace"))

    return sorted(set(permissions))


def has_apk_structure(file_bytes: bytes) -> bool:
    """
    Mengecek cepat apakah file memiliki struktur APK.
    """

    lower_bytes = file_bytes.lower()

    for rule in APK_STRUCTURE_RULES:
        if rule.pattern.lower() in lower_bytes:
            return True

    return False