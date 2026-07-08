import hashlib
import zlib

def md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def sha512(text):
    return hashlib.sha512(text.encode("utf-8")).hexdigest()

def crc32(text):
    checksum = zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF
    return format(checksum, "08x")
