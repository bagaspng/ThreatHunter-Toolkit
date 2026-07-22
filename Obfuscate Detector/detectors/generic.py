import math
import re
from collections import Counter

from detectors.base import Finding, register

_RE_HEXNAME = re.compile(r"_0x[0-9a-fA-F]{3,}")
_RE_CONFUSE = re.compile(r"\b[lI1O0]{4,}\b")


def shannon(s):
    if not s:
        return 0.0
    n = len(s)
    counts = Counter(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


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

    ratio = _printable_ratio(text)
    if len(text) >= 32 and ratio < 0.85:
        out.append(Finding(
            name="low_printable", category="generic",
            confidence=min(80, 50 + int((0.85 - ratio) * 60)),
            evidence="rasio karakter printable %.0f%% (rendah)" % (ratio * 100),
            clue="Banyak byte non-printable. Kemungkinan biner mentah/terkompres. "
                 "Buka dengan hex viewer atau CyberChef untuk kenali magic bytes."))

    return out
