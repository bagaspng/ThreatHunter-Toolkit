import re

from modules import decoder

_MIN_PRINTABLE = 0.85
_MAX_SIZE = 100000
_MAX_DEPTH = 12

_RE_BASE64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_RE_BASE32 = re.compile(r"^[A-Z2-7]+=*$")
_RE_HEX = re.compile(r"^[0-9A-Fa-f]+$")
_RE_BIN = re.compile(r"^[01\s]+$")
_RE_ASCII = re.compile(r"^\s*\d+(?:\s+\d+)*\s*$")
_RE_URL = re.compile(r"%[0-9A-Fa-f]{2}")
_RE_UNICODE = re.compile(r"\\[ux][0-9A-Fa-f]{2,}")


def _printable_ratio(s):
    if not s:
        return 0.0
    ok = sum(1 for c in s if c in "\t\n\r" or 32 <= ord(c) < 127)
    return ok / len(s)


def _meaningful(s):
    return bool(s) and _printable_ratio(s) >= _MIN_PRINTABLE


def _match_base64(t):
    t = t.strip()
    return len(t) >= 4 and len(t) % 4 == 0 and bool(_RE_BASE64.match(t))


def _match_base32(t):
    t = t.strip()
    return len(t) >= 8 and len(t) % 8 == 0 and bool(_RE_BASE32.match(t))


def _match_hex(t):
    t = t.strip()
    return len(t) >= 2 and len(t) % 2 == 0 and bool(_RE_HEX.match(t))


def _match_binary(t):
    bits = re.sub(r"\s", "", t)
    return len(bits) >= 8 and len(bits) % 8 == 0 and bool(_RE_BIN.match(t))


def _match_ascii(t):
    if not _RE_ASCII.match(t):
        return False
    try:
        return all(0 <= int(x) <= 0x10FFFF for x in t.split())
    except ValueError:
        return False


def _match_url(t):
    return bool(_RE_URL.search(t))


def _match_unicode(t):
    return bool(_RE_UNICODE.search(t))


_SNIFFERS = [
    ("base64", _match_base64, decoder.from_base64),
    ("base32", _match_base32, decoder.from_base32),
    ("hex", _match_hex, decoder.from_hex),
    ("binary", _match_binary, decoder.from_binary),
    ("ascii", _match_ascii, decoder.from_ascii),
    ("url", _match_url, decoder.from_url),
    ("unicode", _match_unicode, decoder.from_unicode_escape),
]


def next_layer(text):
    if not text or len(text) > _MAX_SIZE:
        return None
    for name, match, dec in _SNIFFERS:
        if not match(text):
            continue
        try:
            out = dec(text)
        except Exception:
            continue
        if out and out != text and _meaningful(out):
            return (name, out)
    return None


def hint(text):
    nl = next_layer(text)
    if nl is None:
        return {"again": False, "guess": None}
    return {"again": True, "guess": nl[0]}


def peel(text):
    steps = []
    cur = text
    for _ in range(_MAX_DEPTH):
        nl = next_layer(cur)
        if nl is None:
            break
        steps.append(nl)
        cur = nl[1]
    return steps
