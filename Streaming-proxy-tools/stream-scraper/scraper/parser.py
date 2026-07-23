"""
Parser module.

Responsibility: turn extractor output into a StreamInfo object.
This is the ONLY place that knows the websocket URL format.
"""

from bs4 import BeautifulSoup

from . import extractor
from .exceptions import ServerNotFoundError, UUIDNotFoundError, StreamNotFoundError
from .models import StreamInfo
from .utils import download_html, logger

_WEBSOCKET_TEMPLATE = "wss://{server}/stream/{uuid}/channel/0/mse?uuid={uuid}&channel=0"


def build_websocket_url(server: str, uuid: str) -> str:
    return _WEBSOCKET_TEMPLATE.format(server=server, uuid=uuid)


def parse_stream_info(html: str, channel: int = 0) -> StreamInfo:
    """Parse raw HTML into a complete StreamInfo object."""
    soup = BeautifulSoup(html, "html.parser")

    uuid = extractor.extract_uuid(soup)
    server = extractor.extract_server(soup)

    if not uuid or not server:
        urls = extractor.extract_stream_urls(soup)
        if not urls:
            if not uuid:
                raise UUIDNotFoundError("uuid tidak ditemukan pada halaman.")
            if not server:
                raise ServerNotFoundError("server tidak ditemukan pada halaman.")
        
        if channel < 0 or channel >= len(urls):
            raise StreamNotFoundError(
                f"Index channel {channel} diluar batas. Ditemukan {len(urls)} channel."
            )
        
        target_url = urls[channel]
        logger.info(f"Menggunakan channel {channel} URL: {target_url}")
        
        stream_html = download_html(target_url)
        soup = BeautifulSoup(stream_html, "html.parser")
        
        uuid = extractor.extract_uuid(soup)
        if not uuid:
            raise UUIDNotFoundError(f"uuid tidak ditemukan pada halaman stream: {target_url}")

        server = extractor.extract_server(soup)
        if not server:
            raise ServerNotFoundError(f"server tidak ditemukan pada halaman stream: {target_url}")

    websocket = build_websocket_url(server=server, uuid=uuid)

    return StreamInfo(uuid=uuid, server=server, channel=channel, websocket=websocket)