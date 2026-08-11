"""Smart crop: sample frames from a video, detect faces, return crop centers.

Backend preference:
  1. MediaPipe FaceDetector (blaze_face_short_range, ~230KB model in backend/models/) —
     accurate on tilted/small faces. Falls back if model file is missing.
  2. OpenCV Haar cascade (bundled with opencv) — offline fallback.
  3. 0.5 (dead center) if nothing works.

Two entry points:
  - detect_crop_cx(): static crop center for the whole clip.
  - detect_crop_track(): list of (t_seconds, cx) keyframes so the crop FOLLOWS
    the face over time with temporal smoothing and scene-cut awareness.

Optimizations:
  - EMA smoothing removes frame-to-frame jitter
  - Scene detection resets tracker at hard cuts (prevents cross-shot artifacts)
  - Heatmap weighting (optional) biases toward high-engagement moments
"""
from __future__ import annotations

import os
import numpy as np

_MODEL = os.path.join(os.path.dirname(__file__), "..", "models", "blaze_face_short_range.tflite")

# EMA smoothing factor (0.3 = responsive but stable)
_EMA_ALPHA = 0.3
# Scene cut threshold (histogram correlation)
_SCENE_THRESHOLD = 0.3
# Min frames between scene cuts
_MIN_SCENE_GAP = 15


# ---------------------------------------------------------------- detector factories

def _make_mediapipe_detector():
    """Return callable(frame, width) -> [(cx, area), ...] | None, or None if model/pip missing."""
    if not os.path.exists(_MODEL):
        return None
    from mediapipe import Image, ImageFormat
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceDetector, FaceDetectorOptions

    options = FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=_MODEL),
        min_detection_confidence=0.4,
    )
    detector = FaceDetector.create_from_options(options)

    def cb(frame, width):
        result = detector.detect(Image(image_format=ImageFormat.SRGB, data=frame))
        boxes = [
            (d.bounding_box.origin_x, d.bounding_box.origin_y,
             d.bounding_box.width, d.bounding_box.height)
            for d in result.detections
        ]
        if not boxes:
            return None
        return [(min(1.0, max(0.0, (x + w / 2) / width)), w * h) for x, y, w, h in boxes]

    return cb


def _make_haar_detector():
    """Haar fallback: callable(frame, width) -> [(cx, area), ...] | None, or None if unavailable."""
    import cv2

    path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    if not os.path.exists(path):
        return None
    detector = cv2.CascadeClassifier(path)

    def cb(frame, width):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40)
        )
        if len(faces) == 0:
            return None
        return [(min(1.0, max(0.0, (x + w / 2) / width)), w * h) for x, y, w, h in faces.tolist()]

    return cb


def _make_detector():
    for make in (_make_mediapipe_detector, _make_haar_detector):
        det = make()
        if det is not None:
            return det
    return None


# ---------------------------------------------------------------- scene detection

def _detect_scene_cuts(cap, total: int, fps: float, n_samples: int) -> set[int]:
    """Return frame indices where hard cuts occur (histogram diff)."""
    import cv2
    
    cuts = set()
    prev_hist = None
    sample_step = max(1, total // (n_samples * 3))  # denser sampling for cuts
    
    for idx in range(0, total, sample_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
        cv2.normalize(hist, hist)
        
        if prev_hist is not None:
            corr = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
            if corr < _SCENE_THRESHOLD:
                # Avoid detecting cuts too close together
                if not any(abs(idx - c) < _MIN_SCENE_GAP for c in cuts):
                    cuts.add(idx)
        prev_hist = hist
    
    return cuts


# ---------------------------------------------------------------- frame sampling

def _open_video(video_path: str):
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, 0, 0, 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if total <= 0 or width <= 0:
        cap.release()
        return None, 0, 0, 0.0
    return cap, total, width, fps


def _sample_cx_track(video_path: str, n_samples: int, det,
                     heatmap: list[float] | None = None) -> list[tuple[float, float]]:
    """Sample face centers over time with EMA smoothing + scene-cut awareness.

    Args:
        video_path: Path to video file
        n_samples: Number of sample points
        det: Face detector callable
        heatmap: Optional engagement heatmap (same length as n_samples), values 0-1
                 Biases sampling toward high-engagement moments

    Returns:
        List of (t_seconds, cx) with temporal smoothing applied
    """
    import cv2

    cap, total, width, fps = _open_video(video_path)
    if cap is None:
        return []

    # Detect scene cuts for tracker reset
    scene_cuts = _detect_scene_cuts(cap, total, fps, n_samples)

    margin = max(1, int(total * 0.05))
    indices = [
        margin + int(i * (total - 2 * margin) / max(1, n_samples - 1))
        for i in range(n_samples)
    ]

    # Heatmap weights (uniform if not provided)
    weights = heatmap if heatmap is not None else [1.0] * n_samples

    out: list[tuple[float, float]] = []
    ema_cx: float | None = None
    last_scene_cut_idx = -1

    for i, idx in enumerate(indices):
        # Reset EMA at scene cuts
        if any(abs(idx - cut) < _MIN_SCENE_GAP for cut in scene_cuts):
            ema_cx = None
            last_scene_cut_idx = idx

        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        try:
            centers = det(frame, width)
            if centers:
                # Pick largest face (existing logic)
                cx = max(centers, key=lambda c: c[1])[0]
                # EMA smoothing
                if ema_cx is None:
                    ema_cx = cx
                else:
                    ema_cx = _EMA_ALPHA * cx + (1 - _EMA_ALPHA) * ema_cx
                out.append((idx / fps, ema_cx))
        except Exception:
            pass

    cap.release()
    return out


# ---------------------------------------------------------------- public API

def detect_crop_cx(video_path: str, n_samples: int = 10,
                   heatmap: list[float] | None = None) -> float:
    """Static crop center in [0.0, 1.0]. 0.5 = dead center.
    
    Args:
        heatmap: Optional engagement heatmap to weight samples (0-1 values)
    """
    det = _make_detector()
    if det is None:
        return 0.5
    samples = _sample_cx_track(video_path, n_samples, det, heatmap)
    if not samples:
        return 0.5
    return _clamp(sum(cx for _t, cx in samples) / len(samples))


def detect_crop_track(video_path: str, n_samples: int = 24,
                      heatmap: list[float] | None = None) -> list[tuple[float, float]] | None:
    """Keyframes of face center over time -> [(t_seconds, cx), ...].

    Returns None when no face is found (caller should fall back to center crop).
    Keyframes are decimated to a few stable points; consecutive near-identical
    centers are dropped so the ffmpeg expression stays short.
    
    Args:
        heatmap: Optional engagement heatmap to weight samples (0-1 values)
    """
    det = _make_detector()
    if det is None:
        return None
    samples = _sample_cx_track(video_path, n_samples, det, heatmap)
    if not samples:
        return None
    return _decimate_keyframes([(t, _clamp(cx)) for t, cx in samples])


# ---------------------------------------------------------------- helpers

def _decimate_keyframes(kf: list[tuple[float, float]], max_points: int = 14,
                        min_delta: float = 0.04) -> list[tuple[float, float]]:
    """Drop consecutive keyframes whose cx barely moves; cap at max_points.

    Keeps first & last so the trajectory still spans the full clip.
    """
    if len(kf) <= 2:
        return kf
    reduced = [kf[0]]
    for t, cx in kf[1:-1]:
        if abs(cx - reduced[-1][1]) >= min_delta and len(reduced) < max_points - 1:
            reduced.append((t, cx))
    if abs(kf[-1][1] - reduced[-1][1]) >= min_delta and len(reduced) < max_points:
        reduced.append(kf[-1])
    return reduced


def _clamp(cx: float) -> float:
    """Clamp to keep crop in-bounds (not cropping to extreme edges)."""
    return max(0.1, min(0.9, cx))
