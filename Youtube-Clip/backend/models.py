"""Pydantic request/response schemas + conversion to core.ClipConfig."""
from pydantic import BaseModel, Field

from .core.config import ClipConfig, SubtitleStyle


class LoginRequest(BaseModel):
    password: str


class UrlRequest(BaseModel):
    url: str


class SubtitleStyleModel(BaseModel):
    font: str = "Plus Jakarta Sans"
    fonts_dir: str | None = "fonts"
    size: int = 12
    bold: bool = True
    primary_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline: int = 2
    shadow: int = 1
    location: str = "bottom"
    margin_v: int = 40

    def to_core(self) -> SubtitleStyle:
        return SubtitleStyle(**self.model_dump())


class SegmentModel(BaseModel):
    start: float
    duration: float
    score: float = 1.0


class ClipRequest(BaseModel):
    url: str
    mode: str = "heatmap"                 # heatmap | custom | auto
    ratio: str = "9:16"
    crop: str = "default"
    padding: int = 10
    max_clips: int = Field(default=6, ge=1, le=50)
    subtitle: bool = False
    whisper_model: str = "small"
    subtitle_style: SubtitleStyleModel = SubtitleStyleModel()
    smart_crop: bool = True               # face-aware crop center
    hook_text: str = ""                   # text overlay shown at clip start (empty=off, "auto"=pick from transcript)
    # custom mode
    start: str | None = None
    end: str | None = None
    # explicitly selected segments (overrides mode)
    segments: list[SegmentModel] | None = None

    def to_config(self, output_dir: str) -> ClipConfig:
        return ClipConfig(
            crop_mode=self.crop,
            ratio=self.ratio,
            padding=max(0, self.padding),
            subtitle=self.subtitle,
            whisper_model=self.whisper_model,
            subtitle_style=self.subtitle_style.to_core(),
            output_dir=output_dir,
            smart_crop=self.smart_crop,
            hook_text=self.hook_text,
        )


class EditClipRequest(BaseModel):
    """Request to re-render a single clip with custom parameters."""
    job_id: str
    clip_index: int           # 1-based index matching clip_N.mp4
    # Trim adjustments (seconds relative to original segment)
    trim_start_offset: float = 0.0   # additional start offset from original
    trim_end_offset: float = 0.0     # additional end offset from original
    # Crop center override (0.0-1.0), None = use smart_crop auto-detect
    crop_cx: float | None = None
    # Crop keyframes [(t_sec, cx), ...] clip-relative — overrides crop_cx/smart_crop
    crop_keyframes: list[tuple[float, float]] | None = None
    # Ranges [(start, end), ...] in clip-relative seconds to cut out (remove)
    cuts: list[tuple[float, float]] = []
    # Hook text override (empty = no hook, "auto" = pick from transcript)
    hook_text: str = ""
    # Subtitle toggle override
    subtitle: bool | None = None
    # Ratio override
    ratio: str | None = None
    # Crop mode override
    crop: str | None = None
