"""Auto highlight: find the most "interesting" segments of a local video.

Combines two cheap signals (no new deps):
  1. Audio energy — decode to mono PCM via ffmpeg, compute RMS energy envelope
     in numpy. Loud moments (laughter, shouts, applause) score high.
  2. Scene change density — ffmpeg `scdet` filter outputs shot boundaries;
     frequent scene cuts correlate with excitement/edit density.

Both are normalized into a 0-1 score per time bucket, combined, then the top
contiguous windows are extracted as segments (start, duration, score).

Used for the "Auto" clip mode when the video has no (or weak) heatmap data.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np

MAX_DURATION = 60
BUCKET_S = 1.0          # scoring granularity
WINDOW_S = 30           # preferred segment length


def find_interesting(video_path: str, n_clips: int = 6,
                     duration: float | None = None) -> list[dict]:
    """Return [{start, duration, score}, ...] for the top n_clips windows."""
    audio = _audio_energy(video_path, duration)
    scenes = _scene_times(video_path, duration)
    scores = _combine(audio, scenes, duration or _probe_duration(video_path) or 0.0)
    windows = _top_windows(scores, n_clips, duration or len(scores))
    return windows


# ---------------------------------------------------------------- audio energy

def _audio_energy(path: str, duration: float | None) -> np.ndarray | None:
    """Mono 8kHz PCM energy envelope (RMS per second). None on failure."""
    import tempfile as _tf
    with _tf.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav = f.name
    try:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", path, "-ac", "1", "-ar", "8000", "-f", "wav", wav]
        subprocess.run(cmd, capture_output=True, check=True)

        import wave
        with wave.open(wav, "rb") as w:
            n = w.getnframes()
            rate = w.getframerate()
            data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0

        if rate != 8000:
            return None
        # per-second RMS
        per_sec = rate  # samples per second
        n_sec = n // per_sec
        if n_sec < 2:
            return None
        env = data[: n_sec * per_sec].reshape(n_sec, per_sec)
        return np.sqrt(np.mean(env ** 2, axis=1))
    except Exception:
        return None
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass


# ---------------------------------------------------------------- scene changes

def _scene_times(path: str, duration: float | None) -> list[float] | None:
    """Shot boundary timestamps via ffmpeg scdet filter. None on failure."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "info", "-i", path,
             "-filter:v", "scdet=threshold=0.1", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
    except Exception:
        return None
    times = []
    for line in r.stderr.splitlines():
        if "lavfi.scd.score" not in line:
            continue
        # line like: [Parsed_scdet_0 @ ...] lavfi.scd.score: 0.83 lavfi.scd.time: 12.5
        if "lavfi.scd.time:" in line:
            try:
                ts = float(line.split("lavfi.scd.time:")[1].strip())
                times.append(ts)
            except (ValueError, IndexError):
                continue
    return times or None


# ---------------------------------------------------------------- combine

def _combine(audio: np.ndarray | None, scenes: list[float] | None,
             duration: float) -> np.ndarray:
    """Score per BUCKET_S-second bucket in [0,1]. Empty videos score 0."""
    n_buckets = max(1, int(duration / BUCKET_S))
    scores = np.zeros(n_buckets, dtype=float)

    if audio is not None:
        a = np.zeros(n_buckets, dtype=float)
        a[: min(len(audio), n_buckets)] = audio[: min(len(audio), n_buckets)]
        # smooth (moving avg of 3) then normalize to percentiles
        kernel = np.ones(3) / 3
        a = np.convolve(a, kernel, mode="same")
        lo, hi = np.percentile(a, [20, 95])
        # If signal has meaningful variation (dynamic range > 1% of range), use it
        dyn_range = hi - lo
        if dyn_range > 0.001:  # ~0.1% threshold - lower for sensitivity
            norm = np.clip((a - lo) / dyn_range, 0, 1)
            scores += 0.6 * norm

    if scenes:
        scene_arr = np.zeros(n_buckets, dtype=float)
        for ts in scenes:
            idx = int(ts / BUCKET_S)
            if 0 <= idx < n_buckets:
                scene_arr[idx] = 1
        # scenes are sparse; smooth to reward nearby-in-time clusters
        kernel = np.ones(5) / 5
        scene_arr = np.convolve(scene_arr, kernel, mode="same")
        lo, hi = np.percentile(scene_arr, [20, 95])
        dyn_range = hi - lo
        if dyn_range > 1e-6:
            norm = np.clip((scene_arr - lo) / dyn_range, 0, 1)
            scores += 0.4 * norm

    return scores


# ---------------------------------------------------------------- extraction

def _top_windows(scores: np.ndarray, n_clips: int, duration: float) -> list[dict]:
    """Greedy: repeatedly take highest-scoring window, then zero it out ±window."""
    if duration <= 0:
        return []

    segs = []
    work = scores.copy()
    step = max(1, int(WINDOW_S / BUCKET_S))
    for _ in range(n_clips):
        peak = int(np.argmax(work))
        if work[peak] <= 0.05:
            break
        # window around peak
        start_b = max(0, peak - step // 2)
        end_b = min(len(work), peak + step // 2)
        start = start_b * BUCKET_S
        seg_dur = min(MAX_DURATION, max(1.0, (end_b - start_b) * BUCKET_S))
        # nudge to not overflow video
        seg_dur = min(seg_dur, duration - start)
        if seg_dur >= 1.0:
            segs.append({"start": round(start, 1),
                         "duration": round(seg_dur, 1),
                         "score": round(float(work[peak]), 3)})
        # zero out this window so next pick is elsewhere
        work[max(0, start_b - step): end_b + step] = 0.0

    segs.sort(key=lambda s: s["score"], reverse=True)
    return segs


def _probe_duration(path: str) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=15,
        )
        return float(r.stdout.strip())
    except Exception:
        return None
