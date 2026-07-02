import base64
import urllib.parse


def to_base64(text):
    """Encode text to Base64."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def to_base32(text):
    """Encode text to Base32."""
    return base64.b32encode(text.encode("utf-8")).decode("ascii")


def to_hex(text):
    """Encode text to a hexadecimal string."""
    return text.encode("utf-8").hex()


def to_binary(text):
    """Encode text to space-separated 8-bit binary groups.

    Example: "A" -> "01000001"
    """
    return " ".join(format(byte, "08b") for byte in text.encode("utf-8"))


def to_url(text):
    """Percent-encode text for use in URLs."""
    return urllib.parse.quote(text)


def to_unicode_escape(text):
    """Encode every character as a \\uXXXX escape sequence.

    Example: "Hello" -> "\\u0048\\u0065\\u006c\\u006c\\u006f"
    """
    return "".join("\\u{:04x}".format(ord(char)) for char in text)


def to_ascii(text):
    """Encode text to space-separated ASCII/Unicode code points.

    Example: "ABC" -> "65 66 67"
    """
    return " ".join(str(ord(char)) for char in text)
