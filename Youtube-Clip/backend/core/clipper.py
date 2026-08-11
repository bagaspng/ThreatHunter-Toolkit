"""Download -> trim -> crop/scale -> (optional) subtitle -> export.

Architecture:
  - download_video(): download full video ONCE per job via yt-dlp native downloader.
    Native downloader avoids the bot-detection issue that hits ffmpeg-as-downloader.
  - process_clip(): trim from local file (ffmpeg -ss/-to -c copy, fast),
    then crop/scale/subtitle encode. No repeated network calls per clip.

Progress hooks:
  - download: yt-dlp progress_hook -> emit pct + speed_kb
  - ffmpeg encode: Popen + -progress pipe:2 -> parse out_time_ms -> emit pct
  - whisper: no hook; emits stage transitions only
"""
import os
import subprocess
import sys
import tempfile
from typing import Callable

from .config import ClipConfig
from .ffmpeg_filters import (
    cover_scale_crop_vf, cover_scale_crop_track_vf, split_filter_complex,
    cut_select_af, cut_select_vf,
)
from .subtitle import generate_srt, pick_hook_text
from .smart_crop import detect_crop_cx, detect_crop_track
from .auto_highlight import find_interesting

_ENC = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-c:a", "aac", "-b:a", "128k"]

Emitter = Callable[[str, dict], None]


def _escape_filter_path(path: str) -> str:
    """Convert a filesystem path to ffmpeg filter-safe form (ffmpeg 8.x Windows).

    ffmpeg 8.x subtitles filter on Windows requires:
      - forward slashes
      - drive-letter colon escaped as \\: (only the first colon)
      - wrapped in single quotes at call site
    """
    path = os.path.abspath(path).replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = path[0] + "\\:" + path[2:]
    return path


def _backend_root() -> str:
    """Absolute path of the project root (parent of backend/)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _resolve_fonts_dir(fdir: str | None) -> str | None:
    """Resolve a (possibly CWD-relative) fonts dir to absolute backend-root path."""
    if not fdir:
        return None
    if not os.path.isabs(fdir):
        fdir = os.path.join(_backend_root(), fdir)
    return fdir if os.path.isdir(fdir) else None


# Hook overlay font. The web-font path (fonts/PlusJakartaSans.ttf) does NOT exist
# on disk — the real files live under fonts/<Family>/**. Resolve an absolute path.
_HOOK_FONT = os.path.join(
    _backend_root(), "fonts", "Plus_Jakarta_Sans", "PlusJakartaSans-VariableFont_wght.ttf")
if not os.path.isfile(_HOOK_FONT):
    _HOOK_FONT = None  # fall back to ffmpeg's default font if ours is missing


# ---------------------------------------------------------------- download (1x per job)

def download_video(video_id: str, out_path: str, emit: Emitter) -> None:
    """Download full video via yt-dlp Python API (native downloader, no ffmpeg).

    out_path should end with .%(ext)s — yt-dlp fills in the extension.
    Caller must glob/find the actual file after this returns.
    """
    from yt_dlp import YoutubeDL

    def _hook(d: dict) -> None:
        if d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded = d.get("downloaded_bytes") or 0
        pct = int(downloaded / total * 100) if total > 0 else None
        speed = d.get("speed")
        emit("download", {
            "pct": pct,
            "speed_kb": int(speed / 1024) if speed else None,
        })

    fmt = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": fmt,
        "outtmpl": out_path,
        "merge_output_format": "mkv",
        "progress_hooks": [_hook],
        "socket_timeout": 30,
    }
    with YoutubeDL(opts) as ydl:
        ret = ydl.download([f"https://youtu.be/{video_id}"])
    if ret != 0:
        raise RuntimeError(f"yt-dlp download failed (exit {ret})")


def find_downloaded(directory: str) -> str | None:
    """Find the video file yt-dlp wrote into directory."""
    for ext in ("mkv", "mp4", "webm"):
        for name in os.listdir(directory):
            if name.endswith(f".{ext}"):
                return os.path.join(directory, name)
    return None


# ---------------------------------------------------------------- ffmpeg helpers

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


def _run_ffmpeg(cmd: list[str], duration_s: float | None, stage: str, emit: Emitter) -> None:
    """Run ffmpeg with -progress pipe:2, emit pct updates."""
    prog_cmd = cmd[:-1] + ["-progress", "pipe:2", "-nostats", cmd[-1]]
    try:
        idx = prog_cmd.index("-loglevel")
        prog_cmd[idx + 1] = "quiet"
    except ValueError:
        pass

    proc = subprocess.Popen(
        prog_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    last_pct: int | None = None
    for line in proc.stderr:  # type: ignore[union-attr]
        if line.startswith("out_time_ms=") and duration_s:
            try:
                ms = int(line.split("=", 1)[1])
                pct = min(99, int(ms / 1_000_000 / duration_s * 100))
                if pct != last_pct:
                    last_pct = pct
                    emit(stage, {"pct": pct})
            except (ValueError, ZeroDivisionError):
                pass

    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, prog_cmd)
    emit(stage, {"pct": 100})


def _trim_cmd(src: str, start: float, end: float, out: str) -> list[str]:
    """Stream-copy trim — fast, no re-encode.
    -avoid_negative_ts make_zero resets PTS so downstream ffmpeg sees correct timestamps.
    """
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(start), "-to", str(end),
        "-i", src,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        out,
    ]


def _build_export_cmd(src: str, out: str, config: ClipConfig,
                      srt_path: str | None = None,
                      crop_cx: float = 0.5,
                      crop_keyframes: list[tuple[float, float]] | None = None,
                      cuts: list[tuple[float, float]] | None = None) -> list[str]:
    out_w, out_h = config.out_size
    base = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    is_split = config.crop_mode in ("split_left", "split_right") and out_h and out_w and out_h >= out_w

    if is_split:
        side = "left" if config.crop_mode == "split_left" else "right"
        vf = split_filter_complex(out_w, out_h, side)
        if cuts:
            # unlabeled scale consumes the labeled [cut] output above it
            vf = f"[0:v]{cut_select_vf(cuts)}[cut];{vf}"
            return [*base, "-filter_complex", vf, "-map", "[out]", "-map", "0:a?",
                    "-af", cut_select_af(cuts), *_ENC, out]
        return [*base, "-filter_complex", vf, "-map", "[out]", "-map", "0:a?", *_ENC, out]

    crop_vf = None if config.ratio == "original" else (
        cover_scale_crop_track_vf(out_w, out_h, crop_keyframes)
        if crop_keyframes else cover_scale_crop_vf(out_w, out_h, crop_cx)
    )
    if cuts:
        prefix = cut_select_vf(cuts)
        crop_vf = f"{prefix},{crop_vf}" if crop_vf else prefix

    if srt_path:
        if cuts:
            # subtitle timestamps must follow the cut output; burn on a first pass
            vf = crop_vf or cut_select_vf(cuts)
            return [*base, "-vf", vf, "-af", cut_select_af(cuts), *_ENC, out]
        sub = _escape_filter_path(srt_path)
        fdir = _resolve_fonts_dir(config.subtitle_style.fonts_dir)
        fontsdir_arg = f":fontsdir='{_escape_filter_path(fdir)}'" if fdir else ""
        force_style = config.subtitle_style.to_force_style()
        # ffmpeg 8.x: must use filename= prefix; path wrapped in single quotes
        sub_filter = f"subtitles=filename='{sub}'{fontsdir_arg}:force_style='{force_style}'"
        vf = f"{crop_vf},{sub_filter}" if crop_vf else sub_filter
        return [*base, "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k", out]

    if crop_vf:
        cmd = [*base, "-vf", crop_vf, *_ENC, out]
        if cuts:
            cmd[cmd.index("-vf") + 2:cmd.index("-vf") + 2] = ["-af", cut_select_af(cuts)]
        return cmd
    return [*base, *_ENC, out]


# ---------------------------------------------------------------- hook text overlay

def _resolve_hook_text(config: ClipConfig, srt_file: str, trimmed: str,
                       tmp_dir: str, _emit) -> str:
    """Resolve hook text. "auto" picks from transcript; transcribes if needed.

    Hook "auto" used to require subtitle on (SRT existed only then). Now it
    transcribes the trimmed clip on demand so the hook works without subtitles.
    """
    hook = config.hook_text.strip()
    if hook.lower() != "auto":
        return hook

    if os.path.exists(srt_file):
        return pick_hook_text(srt_file)

    hook_srt = os.path.join(tmp_dir, "hook.srt")
    try:
        if generate_srt(trimmed, hook_srt, config, emit=lambda s, d: _emit(s, d)):
            return pick_hook_text(hook_srt)
    except Exception:
        pass
    return ""


def _subtitle_burn_cmd(src: str, out: str, config: ClipConfig, srt_file: str) -> list[str]:
    """ffmpeg command to burn an SRT onto an already cropped video."""
    sub_path = _escape_filter_path(srt_file)
    fdir = _resolve_fonts_dir(config.subtitle_style.fonts_dir)
    fontsdir_arg = f":fontsdir='{_escape_filter_path(fdir)}'" if fdir else ""
    force_style = config.subtitle_style.to_force_style()
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
        "-vf", f"subtitles=filename='{sub_path}'{fontsdir_arg}:force_style='{force_style}'",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-c:a", "copy",
        out,
    ]


def _add_hook_text(video_path: str, text: str, total_dur: float) -> None:
    """Burn a big text overlay for the first 3s (or 30% of clip, whichever shorter).
    Replaces video_path in-place via temp file.
    ponytail: single drawtext pass, no extra dep
    """
    import shutil
    show_dur = min(3.0, total_dur * 0.3)
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    tmp_out = video_path + ".hook.mp4"
    font_arg = f":fontfile='{_escape_filter_path(_HOOK_FONT)}'" if _HOOK_FONT else ""
    drawtext = (
        f"drawtext=text='{safe_text}'"
        f"{font_arg}"
        f":fontsize=52:fontcolor=white"
        f":x=(w-text_w)/2:y=h*0.12"
        f":box=1:boxcolor=black@0.55:boxborderw=14"
        f":enable='between(t,0,{show_dur:.1f})'"
    )
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", video_path, "-vf", drawtext,
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-c:a", "copy",
         tmp_out],
        capture_output=True,
    )
    if r.returncode == 0 and os.path.exists(tmp_out):
        os.replace(tmp_out, video_path)
    else:
        # fallback: keep original without hook
        if os.path.exists(tmp_out):
            os.remove(tmp_out)


def process_clip(source_file: str, item: dict, index: int,
                 total_duration: float | None, config: ClipConfig,
                 emit: Emitter | None = None) -> bool:
    """Trim + crop + optional subtitle for one segment. source_file = local downloaded video."""
    def _emit(stage: str, extra: dict | None = None) -> None:
        if emit:
            emit(stage, {"clip_index": index, **(extra or {})})

    start = max(0.0, item["start"] - config.padding)
    end = min(item["start"] + item["duration"] + config.padding, total_duration or 1e9)
    if end - start < 3:
        return False

    clip_dur = end - start
    tmp = tempfile.mkdtemp(prefix=f"clip{index}_")
    trimmed = os.path.join(tmp, "trimmed.mkv")
    srt_file = os.path.join(tmp, "sub.srt")
    output_file = os.path.join(config.output_dir, f"clip_{index}.mp4")
    os.makedirs(config.output_dir, exist_ok=True)
    is_split = config.crop_mode in ("split_left", "split_right")

    try:
        # --- trim (stream copy, fast) ---
        _emit("trim", {"pct": 0})
        subprocess.run(
            _trim_cmd(source_file, start, end, trimmed),
            check=True, capture_output=True,
        )
        if not os.path.exists(trimmed):
            return False

        actual_dur = clip_dur

        # --- smart crop: detect face trajectory from trimmed clip ---
        crop_cx = 0.5
        crop_keyframes = None
        if config.smart_crop and not is_split:
            _emit("crop", {"pct": 0, "label": "detecting"})
            crop_keyframes = detect_crop_track(trimmed)
            if crop_keyframes:
                crop_cx = crop_keyframes[0][1]
            else:
                crop_cx = detect_crop_cx(trimmed)

        # --- encode ---
        if config.subtitle:
            _emit("subtitle")
            if is_split:
                cropped = os.path.join(tmp, "cropped.mp4")
                _emit("crop", {"pct": 0})
                _run_ffmpeg(_build_export_cmd(trimmed, cropped, config, crop_cx=crop_cx),
                            actual_dur, "crop", _emit)
                if generate_srt(cropped, srt_file, config, emit=lambda s, d: _emit(s, d)):
                    _emit("burn_subtitle", {"pct": 0})
                    _run_ffmpeg(_subtitle_burn_cmd(cropped, output_file, config, srt_file),
                                actual_dur, "burn_subtitle", _emit)
                else:
                    _emit("finalize")
                    os.replace(cropped, output_file)
            else:
                # 1-pass: whisper on trimmed, then crop+burn together
                if generate_srt(trimmed, srt_file, config, emit=lambda s, d: _emit(s, d)):
                    _emit("crop", {"pct": 0})
                    _run_ffmpeg(_build_export_cmd(trimmed, output_file, config,
                                                  srt_path=srt_file, crop_cx=crop_cx,
                                                  crop_keyframes=crop_keyframes),
                                actual_dur, "crop", _emit)
                else:
                    _emit("crop", {"pct": 0})
                    _run_ffmpeg(_build_export_cmd(trimmed, output_file, config, crop_cx=crop_cx,
                                                  crop_keyframes=crop_keyframes),
                                actual_dur, "crop", _emit)
        else:
            _emit("crop", {"pct": 0})
            _run_ffmpeg(_build_export_cmd(trimmed, output_file, config, crop_cx=crop_cx,
                                          crop_keyframes=crop_keyframes),
                        actual_dur, "crop", _emit)

        # --- hook text overlay (post-process, fast) ---
        hook_text = _resolve_hook_text(config, srt_file, trimmed, tmp, _emit)
        if hook_text and os.path.exists(output_file):
            _add_hook_text(output_file, hook_text, actual_dur)

        _emit("done_clip")
        return True
    except Exception as e:
        _emit("error", {"message": str(e)})
        return False
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- re-render for editor

def rerender_clip(source_file: str, original_item: dict, index: int,
                  total_duration: float | None, config: ClipConfig,
                  edit: dict, emit: Emitter | None = None) -> bool:
    """Re-render a clip with custom edit parameters.

    edit dict can contain:
      - trim_start_offset: additional seconds to add to start
      - trim_end_offset: additional seconds to add to end
      - crop_cx: override crop center (0.0-1.0), None = auto smart crop
      - crop_keyframes: list of (t_sec, cx) keyframes — overrides static crop
      - cuts: list of (start, end) clip-relative ranges to remove
      - hook_text: override hook text ("" = none, "auto" = from transcript)
      - subtitle: bool override
      - ratio: str override
      - crop: str override
    """
    def _emit(stage: str, extra: dict | None = None) -> None:
        if emit:
            emit(stage, {"clip_index": index, **(extra or {})})

    # Apply trim offsets to original segment
    start = max(0.0, original_item["start"] - config.padding + edit.get("trim_start_offset", 0.0))
    end = min(
        original_item["start"] + original_item["duration"] + config.padding + edit.get("trim_end_offset", 0.0),
        total_duration or 1e9
    )
    if end - start < 3:
        return False

    clip_dur = end - start
    tmp = tempfile.mkdtemp(prefix=f"clip{index}_edit_")
    trimmed = os.path.join(tmp, "trimmed.mkv")
    srt_file = os.path.join(tmp, "sub.srt")
    output_file = os.path.join(config.output_dir, f"clip_{index}_edited.mp4")
    os.makedirs(config.output_dir, exist_ok=True)
    is_split = config.crop_mode in ("split_left", "split_right")

    # Create a modified config with overrides
    from dataclasses import replace
    mod_config = replace(config)
    if edit.get("subtitle") is not None:
        mod_config.subtitle = edit["subtitle"]
    if edit.get("ratio"):
        mod_config.ratio = edit["ratio"]
    if edit.get("crop"):
        mod_config.crop_mode = edit["crop"]
    if edit.get("hook_text") is not None:
        mod_config.hook_text = edit["hook_text"]

    # Override smart_crop if crop_cx explicitly provided
    force_crop_cx = edit.get("crop_cx")
    edit_crop_kf = edit.get("crop_keyframes") or None
    cuts = edit.get("cuts") or []
    use_smart_crop = mod_config.smart_crop and force_crop_cx is None and not edit_crop_kf

    try:
        _emit("trim", {"pct": 0})
        subprocess.run(
            _trim_cmd(source_file, start, end, trimmed),
            check=True, capture_output=True,
        )
        if not os.path.exists(trimmed):
            return False

        actual_dur = clip_dur

        # --- crop: forced keyframes > forced cx > auto-detect (tracking) ---
        crop_cx = force_crop_cx if force_crop_cx is not None else 0.5
        crop_keyframes = edit_crop_kf
        if use_smart_crop and not is_split:
            _emit("crop", {"pct": 0, "label": "detecting"})
            crop_keyframes = detect_crop_track(trimmed)
            if crop_keyframes:
                crop_cx = crop_keyframes[0][1]
            else:
                crop_cx = detect_crop_cx(trimmed)

        _emit("crop", {"pct": 0})
        if mod_config.subtitle:
            _emit("subtitle")
            if is_split or cuts:
                # 2-pass: cut+crop first, then burn subtitle on the cut output so
                # subtitle timing follows the removed ranges.
                _run_ffmpeg(_build_export_cmd(trimmed, output_file, mod_config, crop_cx=crop_cx,
                                              crop_keyframes=crop_keyframes, cuts=cuts),
                            actual_dur, "crop", _emit)
                if generate_srt(output_file, srt_file, mod_config, emit=lambda s, d: _emit(s, d)):
                    _emit("burn_subtitle", {"pct": 0})
                    _run_ffmpeg(_subtitle_burn_cmd(output_file, output_file + ".sub.mp4", mod_config, srt_file),
                                actual_dur, "burn_subtitle", _emit)
                    os.replace(output_file + ".sub.mp4", output_file)
            else:
                if generate_srt(trimmed, srt_file, mod_config, emit=lambda s, d: _emit(s, d)):
                    _run_ffmpeg(_build_export_cmd(trimmed, output_file, mod_config,
                                                  srt_path=srt_file, crop_cx=crop_cx,
                                                  crop_keyframes=crop_keyframes),
                                actual_dur, "crop", _emit)
                else:
                    _run_ffmpeg(_build_export_cmd(trimmed, output_file, mod_config, crop_cx=crop_cx,
                                                  crop_keyframes=crop_keyframes),
                                actual_dur, "crop", _emit)
        else:
            _run_ffmpeg(_build_export_cmd(trimmed, output_file, mod_config, crop_cx=crop_cx,
                                          crop_keyframes=crop_keyframes, cuts=cuts),
                        actual_dur, "crop", _emit)

        # --- hook text overlay ---
        hook_text = _resolve_hook_text(mod_config, srt_file, trimmed, tmp, _emit)
        if hook_text and os.path.exists(output_file):
            _add_hook_text(output_file, hook_text, actual_dur)

        _emit("done_clip")
        return True
    except Exception as e:
        _emit("error", {"message": str(e)})
        return False
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
