import base64
import re


def is_base64(data):
    """Return True if the data looks like valid Base64."""
    data = data.strip()
    if len(data) < 4 or len(data) % 4 != 0:
        return False
    if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", data):
        return False
    try:
        base64.b64decode(data, validate=True)
        return True
    except Exception:
        return False


def is_base32(data):
    """Return True if the data looks like valid Base32."""
    data = data.strip()
    if len(data) < 8 or len(data) % 8 != 0:
        return False
    if not re.fullmatch(r"[A-Z2-7]+=*", data):
        return False
    try:
        base64.b32decode(data)
        return True
    except Exception:
        return False


def is_hex(data):
    """Return True if the data is a valid hexadecimal string."""
    data = data.strip()
    if len(data) == 0 or len(data) % 2 != 0:
        return False
    try:
        bytes.fromhex(data)
        return True
    except Exception:
        return False


def is_binary(data):
    """Return True if the data is a string of 0s and 1s (8-bit groups)."""
    cleaned = data.replace(" ", "").strip()
    if len(cleaned) == 0 or len(cleaned) % 8 != 0:
        return False
    return bool(re.fullmatch(r"[01]+", cleaned))


def is_url_encoded(data):
    """Return True if the data contains percent-encoded sequences."""
    return bool(re.search(r"%[0-9A-Fa-f]{2}", data))


def detect(data):
    """Run every check and return an ordered dict of results.

    Keys are human-readable encoding names; values are booleans.
    """
    return {
        "Base64": is_base64(data),
        "Base32": is_base32(data),
        "Hexadecimal": is_hex(data),
        "Binary": is_binary(data),
        "URL Encoded": is_url_encoded(data),
    }
