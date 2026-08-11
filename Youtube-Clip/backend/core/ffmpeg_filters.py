"""FFmpeg filter builders + ffmpeg discovery.

Ported from the original run.py (build_cover_scale_crop_vf / build_cover_scale_vf /
get_split_heights) with the split_left / split_right duplication collapsed into one
parametrized builder.
"""
import os
import shutil

# Bottom strip height (facecam) for split modes, in output pixels.
BOTTOM_HEIGHT = 320


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))


def ensure_ffmpeg_on_path() -> bool:
    """On Windows, try to locate a WinGet-installed ffmpeg and add it to PATH."""
    if ffmpeg_available():
        return True

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return False

    gyan_root = os.path.join(
        local_app_data, "Microsoft", "WinGet", "Packages",
        "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
    )
    if not os.path.isdir(gyan_root):
        return False

    for root, _dirs, files in os.walk(gyan_root):
        if "ffmpeg.exe" in files and os.path.basename(root).lower() == "bin":
            os.environ["PATH"] = f"{root}{os.pathsep}{os.environ.get('PATH', '')}"
            return ffmpeg_available()
    return False


def cover_scale_crop_vf(out_w: int, out_h: int, crop_cx: float = 0.5) -> str:
    """Scale to cover the target box then crop to exact out_w x out_h.

    crop_cx: normalized horizontal center [0.0–1.0]. 0.5 = dead center.
    Translates to ffmpeg crop x offset: clamp so crop stays in-bounds.
    """
    ar = f"{out_w}/{out_h}"
    scale = (
        f"scale='if(gte(iw/ih,{ar}),-2,{out_w})':"
        f"'if(gte(iw/ih,{ar}),{out_h},-2)'"
    )
    # crop_cx → pixel offset after scale. Use ffmpeg expressions referencing iw/ih post-scale.
    # x = clamp(cx*iw - out_w/2, 0, iw-out_w)
    # NOTE: commas inside min/max MUST be escaped (\,) — in a filtergraph, an
    # unescaped comma is a filter separator, so this breaks the whole -vf chain.
    cx_expr = (
        f"min(max(({crop_cx:.4f})*iw-{out_w}/2\\,0)\\,iw-{out_w})"
        if crop_cx != 0.5
        else f"(iw-{out_w})/2"
    )
    crop = f"crop={out_w}:{out_h}:{cx_expr}:(ih-{out_h})/2"
    return f"{scale},{crop}"


def cover_scale_crop_track_vf(out_w: int, out_h: int,
                              keyframes: list[tuple[float, float]]) -> str:
    """Scale-to-cover + crop whose x follows the face over time.

    keyframes: list of (t_seconds, cx_normalized) sorted by t. The crop x is a
    piecewise-linear expression over the clip timeline, so the subject stays in
    frame even while moving left/right — no frozen center that chops faces.

    Implementation: build nested if(lte(t,T),seg) expressions. Inside a -vf
    chain every comma inside the expression MUST be escaped (\\,).
    """
    if not keyframes:
        return cover_scale_crop_vf(out_w, out_h, 0.5)
    if len(keyframes) == 1:
        return cover_scale_crop_vf(out_w, out_h, keyframes[0][1])

    # piecewise-constant: cx(t) jumps to the latest keyframe's center, then
    # holds until the next one. Snap between faces, no slow linear pan.
    cx_expr = _step_expr(keyframes)
    # x = clamp(cx(t)*iw - out_w/2, 0, iw-out_w)
    x_expr = f"min(max({cx_expr}*iw-{out_w}/2\\,0)\\,iw-{out_w})"

    ar = f"{out_w}/{out_h}"
    scale = (
        f"scale='if(gte(iw/ih,{ar}),-2,{out_w})':"
        f"'if(gte(iw/ih,{ar}),{out_h},-2)'"
    )
    crop = f"crop={out_w}:{out_h}:{x_expr}:(ih-{out_h})/2"
    return f"{scale},{crop}"


def _piecewise_expr(kf: list[tuple[float, float]]) -> str:
    """Nested if(lte(t,T),seg_i, ... last) expression for piecewise-linear cx(t)."""
    # last segment is constant past the final keyframe
    expr = f"({kf[-1][1]:.4f})"
    for i in range(len(kf) - 2, -1, -1):
        t0, c0 = kf[i]
        t1, c1 = kf[i + 1]
        dur = max(t1 - t0, 0.001)
        seg = f"({c0:.4f}+({c1:.4f}-{c0:.4f})*(t-{t0:.4f})/{dur:.4f})"
        expr = f"if(lte(t\\,{t1:.4f})\\,{seg}\\,{expr})"
    return expr


def _step_expr(kf: list[tuple[float, float]]) -> str:
    """Nested if(lte(t,T),ci, ...) constant-hold expression: cx jumps between keyframes."""
    expr = f"({kf[-1][1]:.4f})"
    for i in range(len(kf) - 2, -1, -1):
        t1 = kf[i + 1][0]
        c0 = kf[i][1]
        expr = f"if(lte(t\\,{t1:.4f})\\,({c0:.4f})\\,{expr})"
    return expr


def _cut_cond(cuts: list[tuple[float, float]]) -> str:
    """Single select condition: keep every frame NOT inside a cut range.

    Commas are safe because the caller wraps the whole expression in single
    quotes — quoted sections are not parsed as filter separators.
    """
    return "*".join(f"not(between(t,{s:.3f},{e:.3f}))" for s, e in cuts)


def cut_select_vf(cuts: list[tuple[float, float]]) -> str:
    """Video filter prefix that drops cut ranges and renumbers PTS."""
    return f"select='{_cut_cond(cuts)}',setpts=N/FRAME_RATE/TB"


def cut_select_af(cuts: list[tuple[float, float]]) -> str:
    """Audio filter that drops the same cut ranges (sample-accurate renumber)."""
    return f"aselect='{_cut_cond(cuts)}',asetpts=N/SR/TB"


def cover_scale_vf(out_w: int, out_h: int) -> str:
    ar = f"{out_w}/{out_h}"
    return (
        f"scale='if(gte(iw/ih,{ar}),-2,{out_w})':"
        f"'if(gte(iw/ih,{ar}),{out_h},-2)'"
    )


def split_heights(out_h: int):
    if not out_h:
        return None, None
    bottom = min(BOTTOM_HEIGHT, max(1, out_h - 1))
    top = max(1, out_h - bottom)
    return top, bottom


def split_filter_complex(out_w: int, out_h: int, side: str) -> str:
    """Build the split filtergraph: top = center gameplay, bottom = corner facecam.

    side: "left" -> facecam bottom-left, "right" -> facecam bottom-right.
    Collapses the old split_left / split_right duplicated blocks.
    """
    top_h, bottom_h = split_heights(out_h)
    scaled = cover_scale_vf(out_w, out_h)
    bottom_x = "0" if side == "left" else f"iw-{out_w}"
    return (
        f"{scaled}[scaled];"
        f"[scaled]split=2[s1][s2];"
        f"[s1]crop={out_w}:{top_h}:(iw-{out_w})/2:(ih-{out_h})/2[top];"
        f"[s2]crop={out_w}:{bottom_h}:{bottom_x}:ih-{bottom_h}[bottom];"
        f"[top][bottom]vstack[out]"
    )


# Output ratio presets -> (width, height). None,None means keep original.
RATIO_PRESETS = {
    "9:16": (720, 1280),
    "1:1": (720, 720),
    "16:9": (1280, 720),
    "original": (None, None),
}


def ratio_to_size(preset: str):
    if preset not in RATIO_PRESETS:
        raise ValueError(f"Invalid ratio preset: {preset}")
    return RATIO_PRESETS[preset]
