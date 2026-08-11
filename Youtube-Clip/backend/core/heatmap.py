"""YouTube video id parsing + Most Replayed heatmap extraction.

Prefers yt-dlp's native `heatmap` field (robust) over scraping the watch page HTML
with a regex (the old approach, kept only as a fallback).
"""
import json
import re
from urllib.parse import parse_qs, urlparse

import requests

MIN_SCORE = 0.40      # only keep markers at/above this normalized intensity
MAX_DURATION = 60     # cap each segment's duration (seconds)


def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host in ("youtu.be", "www.youtu.be"):
        return parsed.path[1:] or None
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None
        if parsed.path.startswith("/embed/"):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None
    return None


def _segments_from_native(heatmap: list, duration: float | None) -> list[dict]:
    results = []
    for m in heatmap or []:
        try:
            start = float(m["start_time"])
            end = float(m["end_time"])
            score = float(m.get("value", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if duration and start >= duration:
            continue
        dur = min(max(0.0, end - start), MAX_DURATION)
        if score >= MIN_SCORE and dur > 0:
            results.append({"start": start, "duration": dur, "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _segments_from_html(video_id: str) -> list[dict]:
    """Fallback: scrape the watch page for the markers JSON blob."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
    except Exception:
        return []

    match = re.search(r'"markers":\s*(\[.*?\])\s*,\s*"?markersMetadata"?', html, re.DOTALL)
    if not match:
        return []
    try:
        markers = json.loads(match.group(1).replace('\\"', '"'))
    except Exception:
        return []

    results = []
    for marker in markers:
        if "heatMarkerRenderer" in marker:
            marker = marker["heatMarkerRenderer"]
        try:
            score = float(marker.get("intensityScoreNormalized", 0))
            if score >= MIN_SCORE:
                results.append({
                    "start": float(marker["startMillis"]) / 1000,
                    "duration": min(float(marker["durationMillis"]) / 1000, MAX_DURATION),
                    "score": score,
                })
        except Exception:
            continue
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def fetch_info(video_id: str) -> dict:
    """Extract info dict via yt-dlp (no download). Raises on failure."""
    from yt_dlp import YoutubeDL

    opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,  # ponytail: caps per-request wait; increase if timeouts on slow connections
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(f"https://youtu.be/{video_id}", download=False)


def get_segments_and_duration(video_id: str) -> tuple[list[dict], float | None]:
    """Return (segments, duration_seconds). Native first, HTML fallback."""
    try:
        info = fetch_info(video_id)
        duration = info.get("duration")
        segments = _segments_from_native(info.get("heatmap"), duration)
        if segments:
            return segments, duration
        return _segments_from_html(video_id), duration
    except Exception:
        return _segments_from_html(video_id), None
