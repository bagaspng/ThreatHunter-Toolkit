"""
Minimal ISO Base Media File Format (fragmented MP4) box reader.

Only reads box headers/structure to identify metadata such as codec
fourcc from the stsd box. Does NOT decode, render, or store video data.
"""

from dataclasses import dataclass, field
from typing import Optional

# Boxes we may want to descend into to find stsd
_CONTAINER_BOXES = {
    b"moov", b"trak", b"mdia", b"minf", b"stbl", b"moof", b"traf",
}

# Common codec fourccs we might find inside stsd
_KNOWN_VIDEO_CODECS = {b"avc1", b"avc3", b"hev1", b"hvc1", b"vp09", b"av01"}
_KNOWN_AUDIO_CODECS = {b"mp4a", b"ac-3", b"ec-3", b"opus", b"Opus"}


@dataclass
class Box:
    box_type: str
    size: int
    start: int


@dataclass
class Mp4Inspection:
    boxes_found: list[str] = field(default_factory=list)
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    is_valid_mp4: bool = False


def _iter_boxes(data: bytes, offset: int = 0, limit: Optional[int] = None):
    """Yield (box_type, size, payload_start, payload_end) for top-level boxes in data."""
    end = limit if limit is not None else len(data)
    pos = offset
    while pos + 8 <= end:
        size = int.from_bytes(data[pos:pos + 4], "big")
        box_type = data[pos + 4:pos + 8]
        header_len = 8

        if size == 1:
            # 64-bit extended size
            if pos + 16 > end:
                break
            size = int.from_bytes(data[pos + 8:pos + 16], "big")
            header_len = 16
        elif size == 0:
            # Box extends to end of data (common for mdat in streamed fragments)
            size = end - pos

        if size < header_len:
            break

        payload_start = pos + header_len
        payload_end = pos + size
        yield box_type, size, payload_start, min(payload_end, end)

        if size == 0:
            break
        pos += size


def _find_stsd_codecs(data: bytes, start: int, end: int, inspection: Mp4Inspection) -> None:
    """Recursively walk container boxes looking for stsd and extract codec fourccs."""
    for box_type, size, p_start, p_end in _iter_boxes(data, start, end):
        type_str = box_type.decode("ascii", errors="replace")
        inspection.boxes_found.append(type_str)

        if box_type == b"stsd":
            # stsd: version(1) + flags(3) + entry_count(4) + entries...
            entry_offset = p_start + 8
            if entry_offset + 8 <= p_end:
                entry_size = int.from_bytes(data[entry_offset:entry_offset + 4], "big")
                codec_fourcc = data[entry_offset + 4:entry_offset + 8]
                if codec_fourcc in _KNOWN_VIDEO_CODECS and not inspection.video_codec:
                    inspection.video_codec = codec_fourcc.decode("ascii", errors="replace")
                elif codec_fourcc in _KNOWN_AUDIO_CODECS and not inspection.audio_codec:
                    inspection.audio_codec = codec_fourcc.decode("ascii", errors="replace")
        elif box_type in _CONTAINER_BOXES:
            _find_stsd_codecs(data, p_start, p_end, inspection)


def inspect_fragment(data: bytes) -> Mp4Inspection:
    """
    Inspect a chunk of binary data received from the stream and report
    which ISO-BMFF boxes are present and, if discoverable, the codec(s)
    declared in the stsd box.
    """
    inspection = Mp4Inspection()

    # Single recursive walk populates boxes_found (including nested ones)
    # and extracts codec fourccs from stsd along the way.
    _find_stsd_codecs(data, 0, len(data), inspection)

    top_level_types = {t.encode("ascii") for t in inspection.boxes_found}
    # A valid ISO-BMFF fragment usually starts with ftyp, or contains moov/moof
    inspection.is_valid_mp4 = bool(top_level_types & {b"ftyp", b"moov", b"moof", b"styp"})

    return inspection