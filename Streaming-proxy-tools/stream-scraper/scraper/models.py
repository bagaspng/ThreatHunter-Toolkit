"""
Data models used across the scraper package.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RawStreamData:
    """Raw values pulled straight out of the HTML, before URL construction."""
    uuid: str
    server: str


@dataclass
class StreamInfo:
    """Final, ready-to-export stream information."""
    uuid: str
    server: str
    channel: int
    websocket: str


@dataclass
class VerificationResult:
    """Result of Milestone 2 — checking whether a stream is live and readable."""
    is_active: bool
    bytes_received: int
    boxes_found: list[str]
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    error: Optional[str] = None