"""Camera URL identity helpers."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class CameraIdentity:
    scheme: str
    hostname: str
    camera_path: str
    camera_key: str


def normalize_camera_path(path: str) -> str | None:
    for part in (path or "").strip("/").split("/"):
        if part.startswith("cctv_"):
            return f"/{part}"
    return None


def extract_camera_identity(url: str) -> CameraIdentity | None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return None
    camera_path = normalize_camera_path(parsed.path)
    if camera_path is None:
        return None
    hostname = parsed.hostname.lower()
    return CameraIdentity(
        scheme=parsed.scheme.lower(),
        hostname=hostname,
        camera_path=camera_path,
        camera_key=f"{hostname}{camera_path}",
    )