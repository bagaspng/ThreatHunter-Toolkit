import base64
import urllib.parse


def from_base64(text):
    return base64.b64decode(text).decode("utf-8")


def from_base32(text):
    return base64.b32decode(text).decode("utf-8")


def from_hex(text):
    return bytes.fromhex(text.strip()).decode("utf-8")


def from_binary(text):
    cleaned = text.strip()
    if " " in cleaned:
        groups = cleaned.split()
    else:
        groups = [cleaned[i:i + 8] for i in range(0, len(cleaned), 8)]
    byte_values = bytes(int(group, 2) for group in groups)
    return byte_values.decode("utf-8")


def from_url(text):
    return urllib.parse.unquote(text)


def from_unicode_escape(text):
    return text.encode("utf-8").decode("unicode_escape")


def from_ascii(text):
    return "".join(chr(int(code)) for code in text.split())
