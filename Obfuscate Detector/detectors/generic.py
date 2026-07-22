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
            clue="Isi teks ini sangat 'acak' — ciri khas data yang dipadatkan "
                 "atau dikunci. Biasanya ada perintah pembuka di dekatnya; "
                 "cari kata seperti decode, atob, atau base64 di sekitarnya "
                 "sebagai titik awal untuk membukanya."))
    elif len(text) > _WINDOW:
        went, woff = max_window_entropy(text)
        if went > 5.0:
            out.append(Finding(
                name="embedded_high_entropy", category="generic",
                confidence=min(85, 55 + int((went - 5.0) * 30)),
                evidence="blob entropy tinggi %.2f di sekitar offset %d "
                         "(file keseluruhan %.2f, rendah)" % (went, woff, ent),
                clue="Ada satu potongan yang jauh lebih 'acak' daripada sisa "
                     "berkas — kemungkinan ada data tersembunyi yang "
                     "disisipkan. Periksa bagian di sekitar posisi tersebut; "
                     "biasanya berupa teks tersandi atau berkas yang "
                     "dipadatkan."))

    hexnames = len(_RE_HEXNAME.findall(text))
    confuse = len(_RE_CONFUSE.findall(text))
    if hexnames >= 5 or confuse >= 3:
        out.append(Finding(
            name="identifier_entropy", category="generic",
            confidence=min(90, 55 + hexnames * 3 + confuse * 3),
            evidence="%d nama gaya _0x, %d nama menyerupai l/I/1/O/0" %
                     (hexnames, confuse),
            clue="Nama-nama variabel di kode ini sengaja diacak agar sulit "
                 "dibaca. Gunakan alat penata/perapi kode (beautifier) untuk "
                 "merapikannya, lalu ganti nama-nama itu agar bermakna."))

    uscore = len(_RE_USCORE.findall(text))
    if uscore >= 5:
        out.append(Finding(
            name="underscore_mangle", category="generic",
            confidence=min(90, 55 + uscore * 3),
            evidence="%d identifier underscore-only (_, __, ___ ...) — "
                     "gaya lambda/pyfuscate" % uscore,
            clue="Kode ini menyamarkan nama dengan deretan garis-bawah "
                 "(_, __, ___) dan memanggil fungsi secara tersembunyi. "
                 "Rapikan dengan penata kode, dan telusuri bagian __import__ "
                 "atau getattr untuk tahu fungsi aslinya. Jangan dijalankan; "
                 "cukup tampilkan isinya untuk diperiksa."))

    ratio = _printable_ratio(text)
    if len(text) >= 32 and ratio < 0.85:
        out.append(Finding(
            name="low_printable", category="generic",
            confidence=min(80, 50 + int((0.85 - ratio) * 60)),
            evidence="rasio karakter printable %.0f%% (rendah)" % (ratio * 100),
            clue="Banyak karakter yang tidak bisa ditampilkan — kemungkinan "
                 "ini data biner atau berkas yang dipadatkan, bukan teks "
                 "biasa. Buka dengan penampil hex untuk mengenali jenisnya."))

    return out
