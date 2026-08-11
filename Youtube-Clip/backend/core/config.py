"""Per-job configuration as plain dataclasses (no module globals -> no race).

The old run.py stored these as module-level globals that the web layer mutated per
request; two concurrent jobs would clobber each other. Passing a ClipConfig instance
down the call chain removes that class of bug entirely.
"""
from dataclasses import dataclass, field

from .ffmpeg_filters import ratio_to_size


@dataclass
class SubtitleStyle:
    font: str = "Plus Jakarta Sans"
    fonts_dir: str | None = "fonts"
    size: int = 12
    bold: bool = True
    primary_color: str = "#FFFFFF"   # text fill
    outline_color: str = "#000000"
    outline: int = 2
    shadow: int = 1
    location: str = "bottom"          # "bottom" | "center"
    margin_v: int = 40

    def to_force_style(self) -> str:
        """Render an ASS force_style string for ffmpeg's subtitles filter."""
        alignment = "2" if self.location == "bottom" else "5"
        margin_v = self.margin_v if self.location == "bottom" else 0
        return (
            f"FontName={self.font},"
            f"FontSize={self.size},"
            f"Bold={1 if self.bold else 0},"
            f"PrimaryColour={_hex_to_ass(self.primary_color)},"
            f"OutlineColour={_hex_to_ass(self.outline_color)},"
            f"BorderStyle=1,Outline={self.outline},Shadow={self.shadow},"
            f"Alignment={alignment},MarginV={margin_v}"
        )


@dataclass
class ClipConfig:
    crop_mode: str = "default"           # default | split_left | split_right
    ratio: str = "9:16"                  # 9:16 | 1:1 | 16:9 | original
    padding: int = 10
    subtitle: bool = False
    whisper_model: str = "small"
    subtitle_style: SubtitleStyle = field(default_factory=SubtitleStyle)
    output_dir: str = "clips"
    smart_crop: bool = True              # use face detection to pick crop_cx
    hook_text: str = ""                  # optional text overlay at clip start (0–3s)

    @property
    def out_size(self):
        return ratio_to_size(self.ratio)


def _hex_to_ass(hex_color: str) -> str:
    """#RRGGBB -> &HBBGGRR (ASS uses BGR, no alpha here)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "&HFFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{b}{g}{r}".upper()
