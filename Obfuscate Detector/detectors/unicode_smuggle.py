from detectors.base import Finding, register

# zero-width space, ZWNJ, ZWJ, word-joiner, BOM/zero-width no-break space
_ZERO_WIDTH = frozenset((0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF))
# bidi embeddings/overrides (U+202A-202E) and isolates (U+2066-2069)
_BIDI = frozenset(list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A)))
_CYRILLIC = (0x0400, 0x04FF)
_GREEK = (0x0370, 0x03FF)


def _add(out, name, conf, evidence, clue):
    out.append(Finding(name=name, category="unicode", confidence=conf,
                       evidence=evidence, clue=clue))


def _count_range(text, lo, hi):
    return sum(1 for c in text if lo <= ord(c) <= hi)


def _has_latin(text):
    return any("a" <= c <= "z" or "A" <= c <= "Z" for c in text)


@register
def detect_unicode(text):
    text = text or ""
    out = []

    bidi = sum(1 for c in text if ord(c) in _BIDI)
    if bidi >= 1:
        _add(out, "bidi_override", 85,
             "%d karakter bidi override (U+202A-202E / U+2066-2069)" % bidi,
             "Karakter bidi dapat membalik urutan tampil kode tanpa mengubah "
             "eksekusi (Trojan Source). Lihat byte mentah atau buang karakter "
             "bidi untuk baca urutan asli.")

    zw = sum(1 for c in text if ord(c) in _ZERO_WIDTH)
    if zw >= 4:
        _add(out, "zero_width", 80,
             "%d karakter zero-width (ZWSP/ZWNJ/ZWJ/BOM)" % zw,
             "Karakter tak-terlihat dipakai menyisipkan/menyembunyikan data. "
             "Buang zero-width atau lihat hex untuk ungkap konten tersembunyi.")

    cyr = _count_range(text, *_CYRILLIC)
    grk = _count_range(text, *_GREEK)
    if _has_latin(text) and (cyr >= 1 or grk >= 1):
        _add(out, "homoglyph_mix", 50,
             "campur Latin dengan Cyrillic(%d)/Greek(%d) - mungkin homoglyph"
             % (cyr, grk),
             "Skrip campur bisa homoglyph (huruf mirip, mis. Cyrillic 'a'). "
             "Normalisasi ke ASCII / cek confusables untuk temukan nama palsu. "
             "Sinyal lemah - bisa juga teks multibahasa wajar.")

    return out
