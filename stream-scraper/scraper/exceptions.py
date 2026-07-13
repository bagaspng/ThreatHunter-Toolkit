"""
Custom exceptions for the stream scraper package.
"""


class StreamNotFoundError(Exception):
    """Base exception for any failure to locate stream information."""


class UUIDNotFoundError(StreamNotFoundError):
    """Raised when the uuid value cannot be located in the page."""


class ServerNotFoundError(StreamNotFoundError):
    """Raised when the server value cannot be located in the page."""


class StreamConnectionError(Exception):
    """Raised when the websocket connection to the stream cannot be established."""


class StreamInactiveError(Exception):
    """Raised when the connection succeeds but no stream data is received in time."""


class CameraNotFoundError(Exception):
    """Raised when a camera cannot be found in the registry."""