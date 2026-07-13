"""
Verifier module — Milestone 2.

Responsibility: connect to a stream's websocket URL, confirm data is
actually flowing (stream is live), and read codec information from the
fragmented MP4 boxes received.

Does NOT decode video, does NOT render anything, does NOT persist media —
that belongs to Milestone 3 (player).
"""

import websocket

from . import mp4utils
from .exceptions import StreamConnectionError
from .models import VerificationResult
from .utils import logger


def verify_stream(
    websocket_url: str,
    timeout: int = 10,
    max_bytes: int = 262_144,
    origin: str | None = "https://stream.lihatcctv.com",
) -> VerificationResult:
    """
    Connect to the websocket stream and check whether it's active.

    Collects binary frames up to `max_bytes` or until `timeout` elapses,
    then inspects the collected bytes for ISO-BMFF box structure and
    codec fourccs.
    """
    headers = [
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ]

    try:
        ws = websocket.create_connection(
            websocket_url,
            timeout=timeout,
            origin=origin,
            header=headers,
        )
    except Exception as exc:
        raise StreamConnectionError(f"Gagal konek ke websocket: {exc}") from exc

    collected = bytearray()
    video_codec = None
    audio_codec = None

    try:
        ws.settimeout(timeout)
        while len(collected) < max_bytes:
            try:
                frame = ws.recv()
            except Exception:
                break  # timeout or connection closed — stop collecting

            if frame is None:
                break
            if isinstance(frame, str):
                # Some servers send text control frames; ignore for our purposes
                continue
            if not frame:
                break

            if len(frame) > 0 and frame[0] == 9:
                try:
                    codec_str = frame[1:].decode("utf-8", errors="ignore").strip()
                    if codec_str:
                        video_codec = codec_str
                except Exception:
                    pass
            else:
                collected.extend(frame)
    finally:
        ws.close()

    bytes_received = len(collected)

    if bytes_received == 0:
        logger.info("Tidak ada data diterima dari websocket — stream kemungkinan tidak aktif.")
        return VerificationResult(
            is_active=False,
            bytes_received=0,
            boxes_found=[],
            error="Tidak ada data diterima dalam batas waktu.",
        )

    inspection = mp4utils.inspect_fragment(bytes(collected))

    # Use inspected codecs as fallback
    if not video_codec:
        video_codec = inspection.video_codec
    if not audio_codec:
        audio_codec = inspection.audio_codec

    logger.info(
        f"Diterima {bytes_received} bytes. Boxes: {inspection.boxes_found}. "
        f"Video codec: {video_codec}, Audio codec: {audio_codec}"
    )

    return VerificationResult(
        is_active=True,
        bytes_received=bytes_received,
        boxes_found=inspection.boxes_found,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )