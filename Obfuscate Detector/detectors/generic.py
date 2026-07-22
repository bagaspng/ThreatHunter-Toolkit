import math
import re
from collections import Counter

from detectors.base import Finding, register

_RE_HEXNAME = re.compile(r"_0x[0-9a-fA-F]{3,}")
_RE_CONFUSE = re.compile(r"\b[lI1O0]{4,}\b")
_RE_USCORE = re.compile(r"\b_{2,}\b")


_WINDOW = 256
_STEP = 128


def shannon(s):
    if not s:
        return 0.0
    n = len(s)
    counts = Counter(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def max_window_entropy(text):
    """Return (best_entropy, offset) over sliding windows; (global, 0) if short."""
    if len(text) <= _WINDOW:
        return shannon(text), 0
    best, best_off = 0.0, 0
    for i in range(0, len(text) - _WINDOW + 1, _STEP):
        e = shannon(text[i:i + _WINDOW])
        if e > best:
            best, best_off = e, i
    return best, best_off


def _printable_ratio(s):
    if not s:
        return 0.0
    ok = sum(1 for c in s if c in "\t\n\r" or 32 <= ord(c) < 127)
    return ok / len(s)


@register
def detect_generic(text):
    text = text or ""
    out = []

    ent = shannon(text)
    if len(text) >= 32 and ent > 4.5:
        out.append(Finding(
            name="high_entropy", category="generic",
            confidence=min(85, 50 + int((ent - 4.5) * 40)),
            evidence="entropy Shannon %.2f bit/char (tinggi)" % ent,
            clue="Entropi tinggi menandakan data terpaket/terenkripsi. "
                 "Cari fungsi decode (atob/unescape/base64) di sekitar blob "
                 "ini sebagai titik masuk."))
    elif len(text) > _WINDOW:
        went, woff = max_window_entropy(text)
        if went > 5.0:
            out.append(Finding(
                name="embedded_high_entropy", category="generic",
                confidence=min(85, 55 + int((went - 5.0) * 30)),
                evidence="blob entropy tinggi %.2f di sekitar offset %d "
                         "(file keseluruhan %.2f, rendah)" % (went, woff, ent),
                clue="Ada blok pekat/terenkripsi tersembunyi dalam file yang "
                     "secara keseluruhan tampak normal. Periksa sekitar offset "
                     "itu; kemungkinan payload base64/terkompres disisipkan."))

    hexnames = len(_RE_HEXNAME.findall(text))
    confuse = len(_RE_CONFUSE.findall(text))
    if hexnames >= 5 or confuse >= 3:
        out.append(Finding(
            name="identifier_entropy", category="generic",
            confidence=min(90, 55 + hexnames * 3 + confuse * 3),
            evidence="%d nama gaya _0x, %d nama menyerupai l/I/1/O/0" %
                     (hexnames, confuse),
            clue="Nama identifier di-mangle. Pakai beautifier + rename "
                 "(js-beautify, atau Wakaru/de4js untuk JS) agar terbaca."))

    uscore = len(_RE_USCORE.findall(text))
    if uscore >= 5:
        out.append(Finding(
            name="underscore_mangle", category="generic",
            confidence=min(90, 55 + uscore * 3),
            evidence="%d identifier underscore-only (_, __, ___ ...) — "
                     "gaya lambda/pyfuscate" % uscore,
            clue="Nama diganti deretan underscore + dispatch dinamis "
                 "(__import__/getattr/globals). Beautify lalu rename; telusuri "
                 "__import__/getattr untuk temukan API asli. JANGAN exec — "
                 "cetak argumen exec/__import__ untuk lihat sumber."))

    ratio = _printable_ratio(text)
    if len(text) >= 32 and ratio < 0.85:
        out.append(Finding(
            name="low_printable", category="generic",
            confidence=min(80, 50 + int((0.85 - ratio) * 60)),
            evidence="rasio karakter printable %.0f%% (rendah)" % (ratio * 100),
            clue="Banyak byte non-printable. Kemungkinan biner mentah/terkompres. "
                 "Buka dengan hex viewer atau CyberChef untuk kenali magic bytes."))

    return out
