"""Assert-based self-checks for core logic. Run: python -m backend.core.test_core"""
import os

from .config import ClipConfig, SubtitleStyle, _hex_to_ass
from .ffmpeg_filters import (
    cover_scale_crop_vf, cover_scale_crop_track_vf, _piecewise_expr,
    ratio_to_size, split_filter_complex, split_heights,
    cut_select_af, cut_select_vf,
)
from .heatmap import _segments_from_native, extract_video_id
from .smart_crop import _decimate_keyframes, detect_crop_cx
from .subtitle import format_timestamp


def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=abc123DEF45") == "abc123DEF45"
    assert extract_video_id("https://youtu.be/abc123DEF45") == "abc123DEF45"
    assert extract_video_id("https://www.youtube.com/shorts/abc123DEF45") == "abc123DEF45"
    assert extract_video_id("https://youtube.com/embed/abc123DEF45") == "abc123DEF45"
    assert extract_video_id("https://example.com/watch?v=x") is None


def test_ratio():
    assert ratio_to_size("9:16") == (720, 1280)
    assert ratio_to_size("original") == (None, None)


def test_split_heights():
    top, bottom = split_heights(1280)
    assert bottom == 320 and top == 960 and top + bottom == 1280


def test_filters_are_strings():
    assert "vstack" in split_filter_complex(720, 1280, "left")
    # left facecam anchored at x=0, right anchored at iw-out_w
    assert "crop=720:320:0:" in split_filter_complex(720, 1280, "left")
    assert "crop=720:320:iw-720:" in split_filter_complex(720, 1280, "right")
    assert "crop=720:1280" in cover_scale_crop_vf(720, 1280)


def test_hex_to_ass():
    assert _hex_to_ass("#FFFFFF") == "&HFFFFFF"
    assert _hex_to_ass("#FF0000") == "&H0000FF"   # red -> BGR


def test_force_style():
    fs = SubtitleStyle(location="center", size=20).to_force_style()
    assert "Alignment=5" in fs and "FontSize=20" in fs


def test_native_segments_filter_and_sort():
    heatmap = [
        {"start_time": 0, "end_time": 5, "value": 0.9},
        {"start_time": 5, "end_time": 10, "value": 0.1},   # below MIN_SCORE
        {"start_time": 10, "end_time": 15, "value": 0.5},
    ]
    segs = _segments_from_native(heatmap, duration=100)
    assert len(segs) == 2
    assert segs[0]["score"] == 0.9   # sorted desc
    assert segs[0]["duration"] == 5


def test_format_timestamp():
    assert format_timestamp(3661.5) == "01:01:01,500"


def test_config_out_size():
    assert ClipConfig(ratio="1:1").out_size == (720, 720)


def test_track_vf_builds_nested_expr():
    kf = [(0.0, 0.3), (5.0, 0.6), (10.0, 0.3)]
    vf = cover_scale_crop_track_vf(720, 1280, kf)
    # scale + crop, with an if(lte(t, ...)) driving the x position
    assert "scale=" in vf and "crop=720:1280" in vf
    assert "if(lte(t" in vf
    # commas inside the expression escaped so the -vf chain stays valid
    assert "\\," in vf


def test_track_vf_single_keyframe_falls_back_to_static():
    vf = cover_scale_crop_track_vf(720, 1280, [(0.0, 0.5)])
    assert "lte(t" not in vf
    assert "crop=720:1280:(iw-720)/2" in vf


def test_track_vf_empty_falls_back_to_center():
    assert cover_scale_crop_track_vf(720, 1280, []) == cover_scale_crop_vf(720, 1280)


def test_piecewise_expr_first_and_last_kept():
    kf = [(0.0, 0.2), (1.0, 0.2), (2.0, 0.8), (3.0, 0.8)]
    expr = _piecewise_expr(kf)
    assert "0.8000" in expr            # last constant tail
    assert "0.2000" in expr            # first segment value
    assert "lte(t" in expr


def test_decimate_keyframes_drops_redundant_points():
    kf = [(0.0, 0.2), (1.0, 0.2), (2.0, 0.2), (3.0, 0.8), (4.0, 0.8), (5.0, 0.8)]
    out = _decimate_keyframes(kf)
    assert out[0] == kf[0]
    assert out[-1][1] == kf[-1][1]     # last distinct center kept
    assert len(out) < len(kf)
    # consecutive near-identical cx collapsed
    assert all(abs(out[i][1] - out[i + 1][1]) >= 0.04 for i in range(len(out) - 1))


def test_detect_crop_cx_missing_file_falls_back_to_center():
    # no detector on a nonexistent path -> 0.5 (safe default)
    assert detect_crop_cx("definitely_missing.mp4") == 0.5


def test_cut_select_filters():
    cuts = [(3.0, 5.0), (8.0, 9.0)]
    vf = cut_select_vf(cuts)
    assert vf.startswith("select='")
    assert "not(between(t,3.000,5.000))" in vf
    assert "not(between(t,8.000,9.000))" in vf
    assert "setpts=N/FRAME_RATE/TB" in vf
    assert cut_select_af(cuts).startswith("aselect='") and "asetpts=N/SR/TB" in cut_select_af(cuts)


def test_export_cmd_with_cuts_gets_vf_and_af():
    from .clipper import _build_export_cmd
    config = ClipConfig(ratio="9:16")
    cmd = _build_export_cmd("in.mkv", "out.mp4", config, cuts=[(1.0, 2.0)])
    assert "-vf" in cmd and "select='" in cmd[cmd.index("-vf") + 1]
    assert "-af" in cmd and "aselect='" in cmd[cmd.index("-af") + 1]


def test_subtitle_burn_cmd_escapes_paths():
    from .clipper import _subtitle_burn_cmd, _HOOK_FONT
    config = ClipConfig(subtitle=True)
    cmd = _subtitle_burn_cmd("in.mp4", "out.mp4", config, "C:\\x\\sub.srt")
    vf = cmd[cmd.index("-vf") + 1]
    assert "subtitles=filename='C\\:/x/sub.srt'" in vf
    # fontsdir resolved to an absolute path off the backend root, not CWD-relative
    assert "fontsdir='C\\:/" in vf
    # hook font resolves to a real file (was previously a nonexistent relative path)
    assert _HOOK_FONT is None or os.path.isfile(_HOOK_FONT)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
