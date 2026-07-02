import base64
import urllib.parse


def to_base64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def to_base32(text):
    return base64.b32encode(text.encode("utf-8")).decode("ascii")


def to_hex(text):
    return text.encode("utf-8").hex()


def to_binary(text):
    return " ".join(format(byte, "08b") for byte in text.encode("utf-8"))


def to_url(text):
    return urllib.parse.quote(text)


def to_unicode_escape(text):
    return "".join("\\u{:04x}".format(ord(char)) for char in text)


def to_ascii(text):
    return " ".join(str(ord(char)) for char in text)
