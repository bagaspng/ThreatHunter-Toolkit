import hashlib
import zlib


def md5(text):
    """Return the MD5 hex digest of the text."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sha1(text):
    """Return the SHA1 hex digest of the text."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def sha256(text):
    """Return the SHA256 hex digest of the text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha512(text):
    """Return the SHA512 hex digest of the text."""
    return hashlib.sha512(text.encode("utf-8")).hexdigest()


def crc32(text):
    """Return the CRC32 checksum of the text as an 8-digit hex string."""
    checksum = zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF
    return format(checksum, "08x")
