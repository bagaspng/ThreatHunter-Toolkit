import base64
import urllib.parse


def from_base64(text):
    """Decode a Base64 string back to text."""
    return base64.b64decode(text).decode("utf-8")


def from_base32(text):
    """Decode a Base32 string back to text."""
    return base64.b32decode(text).decode("utf-8")


def from_hex(text):
    """Decode a hexadecimal string back to text."""
    return bytes.fromhex(text.strip()).decode("utf-8")


def from_binary(text):
    """Decode space-separated 8-bit binary groups back to text.

    Also tolerates a continuous binary string with no separators.
    """
    cleaned = text.strip()
    if " " in cleaned:
        groups = cleaned.split()
    else:
        # Split a continuous stream into 8-bit chunks.
        groups = [cleaned[i:i + 8] for i in range(0, len(cleaned), 8)]
    byte_values = bytes(int(group, 2) for group in groups)
    return byte_values.decode("utf-8")


def from_url(text):
    """Decode a percent-encoded URL string."""
    return urllib.parse.unquote(text)


def from_unicode_escape(text):
    """Decode \\uXXXX escape sequences back to text."""
    return text.encode("utf-8").decode("unicode_escape")


def from_ascii(text):
    """Decode space-separated code points back to text.

    Example: "65 66 67" -> "ABC"
    """
    return "".join(chr(int(code)) for code in text.split())
