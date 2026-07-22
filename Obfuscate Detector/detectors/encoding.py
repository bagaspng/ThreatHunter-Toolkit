import base64
import binascii
import re
import urllib.parse

from detectors.base import Finding, register

_MAX_DEPTH = 12
_MIN_PRINTABLE = 0.85

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


def _dec_base64(t):
    return base64.b64decode(t.strip()).decode("utf-8", "strict")


def _dec_base32(t):
    return base64.b32decode(t.strip()).decode("utf-8", "strict")


def _dec_hex(t):
    return bytes.fromhex(t.strip()).decode("utf-8", "strict")


def _dec_binary(t):
    bits = re.sub(r"\s", "", t)
    out = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    return out.decode("utf-8", "strict")


def _dec_ascii(t):
    return "".join(chr(int(x)) for x in t.split())


def _dec_url(t):
    return urllib.parse.unquote(t)


def _dec_unicode(t):
    return t.encode().decode("unicode_escape")


def _m_base64(t):
    t = t.strip()
    return len(t) >= 8 and len(t) % 4 == 0 and bool(_RE_BASE64.match(t))


def _m_base32(t):
    t = t.strip()
    return len(t) >= 8 and len(t) % 8 == 0 and bool(_RE_BASE32.match(t))


def _m_hex(t):
    t = t.strip()
    return len(t) >= 8 and len(t) % 2 == 0 and bool(_RE_HEX.match(t))


def _m_binary(t):
    bits = re.sub(r"\s", "", t)
    return len(bits) >= 16 and len(bits) % 8 == 0 and bool(_RE_BIN.match(t))


def _m_ascii(t):
    if not _RE_ASCII.match(t):
        return False
    try:
        return all(0 <= int(x) <= 0x10FFFF for x in t.split())
    except ValueError:
        return False


def _m_url(t):
    return bool(_RE_URL.search(t))


def _m_unicode(t):
    return bool(_RE_UNICODE.search(t))


_SNIFFERS = [
    ("base64", _m_base64, _dec_base64),
    ("base32", _m_base32, _dec_base32),
    ("hex", _m_hex, _dec_hex),
    ("binary", _m_binary, _dec_binary),
    ("ascii-desimal", _m_ascii, _dec_ascii),
    ("url", _m_url, _dec_url),
    ("unicode", _m_unicode, _dec_unicode),
]


def next_layer(text):
    if not text:
        return None
    for name, match, dec in _SNIFFERS:
        if not match(text):
            continue
        try:
            out = dec(text)
        except (ValueError, binascii.Error, UnicodeDecodeError):
            continue
        if out and out != text and _meaningful(out):
            return (name, out)
    return None


def _build_clue(seq):
    steps = " lalu ".join("decode %s" % n for n in seq)
    if len(seq) > 1:
        return ("Terdeteksi %d lapisan. Urutan dugaan: %s. Cek hasil di "
                "CyberChef 'Magic'. Lapisan dalam bisa gzip/zlib bila hasil "
                "masih biner." % (len(seq), steps))
    return ("Terlihat %s. Coba %s. Verifikasi di CyberChef 'Magic'." %
            (seq[0], steps))


@register
def detect_encoding(text):
    text = (text or "").strip()
    first = next_layer(text)
    if first is None:
        return []
    name, decoded = first
    ratio = _printable_ratio(decoded)  # used for confidence only
    seq = [name]
    cur = decoded
    for _ in range(_MAX_DEPTH - 1):
        nl = next_layer(cur)
        if nl is None:
            break
        seq.append(nl[0])
        cur = nl[1]
    decoded = cur = None  # discard all decoded content (zero-decode invariant)
    layers = len(seq)
    conf = min(95, 60 + int(ratio * 30) + (5 if layers > 1 else 0))
    evidence = "%d char, cocok pola %s" % (len(text), name)
    if layers > 1:
        evidence += ", terdeteksi %d lapisan (%s)" % (layers, " -> ".join(seq))
    return [Finding(name=name, category="encoding", confidence=conf,
                    evidence=evidence, clue=_build_clue(seq), layers=layers)]
