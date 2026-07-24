"""Segment cache and response helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import time
from pathlib import Path


@dataclass(frozen=True)
class RangeResult:
    start: int
    end: int
    satisfiable: bool = True

    @property
    def length(self) -> int:
        return max(0, self.end - self.start + 1)


def cache_path_for_url(url: str, cache_dir: Path | str = "cache_segments") -> Path:
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return Path(cache_dir) / f"{url_hash}.dat"


def parse_range_request(range_header: str | None, file_len: int) -> RangeResult | None:
    if not range_header:
        return None
    if file_len < 0 or not range_header.startswith("bytes="):
        return RangeResult(0, -1, False)
    spec = range_header[6:].strip()
    if "," in spec or "-" not in spec:
        return RangeResult(0, -1, False)
    start_raw, end_raw = spec.split("-", 1)
    try:
        if start_raw == "":
            suffix_len = int(end_raw)
            if suffix_len <= 0:
                return RangeResult(0, -1, False)
            if file_len == 0:
                return RangeResult(0, -1, False)
            start = max(file_len - suffix_len, 0)
            end = file_len - 1
        else:
            start = int(start_raw)
            end = int(end_raw) if end_raw else file_len - 1
            if start < 0 or end < start:
                return RangeResult(0, -1, False)
            if start >= file_len:
                return RangeResult(0, -1, False)
            end = min(end, file_len - 1)
    except ValueError:
        return RangeResult(0, -1, False)
    return RangeResult(start, end, True)


def parse_range(range_header: str, file_len: int) -> tuple[int, int]:
    parsed = parse_range_request(range_header, file_len)
    if parsed is None or not parsed.satisfiable:
        return 0, max(0, file_len - 1)
    return parsed.start, parsed.end


def detect_content_type(url: str) -> str:
    clean = url.split("?")[0].lower()
    if clean.endswith(".m4s") or clean.endswith(".mp4"):
        return "video/mp4"
    if clean.endswith(".aac") or clean.endswith(".m4a"):
        return "audio/aac"
    if clean.endswith(".vtt"):
        return "text/vtt"
    if clean.endswith(".key") or clean.endswith(".bin"):
        return "application/octet-stream"
    return "video/mp2t"


class SegmentCache:
    def __init__(self, cache_dir: Path | str = "cache_segments", ttl_seconds: int = 300, max_files: int = 500):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.max_files = max_files
        self.cache_dir.mkdir(exist_ok=True)

    def path_for_url(self, url: str) -> Path:
        return cache_path_for_url(url, self.cache_dir)

    def read(self, url: str) -> bytes | None:
        path = self.path_for_url(url)
        if not path.exists() or self.is_expired(path):
            return None
        return path.read_bytes()

    def write(self, url: str, body: bytes) -> Path:
        path = self.path_for_url(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        with open(tmp, "wb") as handle:
            handle.write(body)
        os.replace(tmp, path)
        self.cleanup()
        return path

    def is_expired(self, path: Path) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return time.time() - path.stat().st_mtime > self.ttl_seconds

    def cleanup(self) -> None:
        files = [path for path in self.cache_dir.glob("*.dat") if path.is_file()]
        now = time.time()
        for path in files:
            if self.ttl_seconds > 0 and now - path.stat().st_mtime > self.ttl_seconds:
                path.unlink(missing_ok=True)
        files = [path for path in self.cache_dir.glob("*.dat") if path.is_file()]
        if len(files) <= self.max_files:
            return
        for path in sorted(files, key=lambda item: item.stat().st_mtime)[: len(files) - self.max_files]:
            path.unlink(missing_ok=True)
