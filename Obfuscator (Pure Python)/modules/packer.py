"""Packer JS murni Python (tanpa Node.js).

Membungkus source JS menjadi sebuah IIFE (function(){...}()) yang men-decode
dirinya sendiri saat runtime lalu mengeksekusinya. Bisa dilapis beberapa kali
(IIFE di dalam IIFE).

Yang menyulitkan analisis statis:
  1. Rolling cipher berumpan-balik: kunci berubah tiap karakter dan bergantung
     pada karakter cipher sebelumnya (bukan tabel tetap), tanpa tabel invers
     yang ikut tertempel.
  2. Payload dipetakan ke rentang ASCII printable (32..126) sehingga tampil
     sebagai "teks sampah" rapat, bukan tembok \\xHH.
  3. Semua nama API disembunyikan sebagai hex-escape + akses bracket
     (charCodeAt, fromCharCode, constructor, atob, escape, decodeURIComponent).
     Tidak ada literal atob/Function yang bisa di-grep atau di-hook sepele.

Cara kerja tiap lapis:
  source -> UTF-8 -> base64 -> rolling cipher (printable) -> string teks
         -> tempel decoder kecil -> (function(){...}())
Saat dijalankan browser: decoder membalik cipher -> base64 -> UTF-8 -> source,
lalu Function-constructor (diakses via 'constructor') mengeksekusinya.
"""

import base64
import random

_R = 95  # jumlah karakter printable (32..126)


def _hexstr(s):
    # Literal string JS dengan tiap karakter di-escape \xHH, supaya nama API
    # (mis. "charCodeAt") tidak muncul apa adanya dan tidak bisa di-grep.
    return '"' + "".join("\\x%02x" % ord(ch) for ch in s) + '"'


def _js_string(codes):
    # Rangkai kode karakter (32..126) jadi literal string JS. Hanya karakter
    # yang bisa merusak parsing yang di-escape: kutip, backslash, dan '<'
    # (mencegah '</script>' bila ditempel inline).
    parts = ['"']
    for c in codes:
        ch = chr(c)
        if ch in ('"', "\\"):
            parts.append("\\" + ch)
        elif ch == "<":
            parts.append("\\x3c")
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def _pack_once(src):
    seed = random.randint(0, _R - 1)
    b64 = base64.b64encode(src.encode("utf-8")).decode("ascii")

    codes = []
    prev = seed
    for k, ch in enumerate(b64):
        key = (prev * 7 + k + seed) % _R
        c = ((ord(ch) - 32) + key) % _R        # 0..94
        codes.append(c + 32)                   # 32..126 (printable)
        prev = c
    blob = _js_string(codes)

    cca = _hexstr("charCodeAt")
    fcc = _hexstr("fromCharCode")
    ctor = _hexstr("constructor")
    atob = _hexstr("atob")
    esc = _hexstr("escape")
    duri = _hexstr("decodeURIComponent")
    s = str(seed)

    return (
        "(function(){"
        "var _G=this,_s=" + blob + ",_n=_s.length,_r=\"\",_p=" + s + ",_k=0,_c;"
        "for(;_k<_n;_k++){"
        "_c=_s[" + cca + "](_k)-32;"
        "_r+=\"\"[" + ctor + "][" + fcc + "]"
        "(((_c-((_p*7+_k+" + s + ")%95))%95+95)%95+32);"
        "_p=_c;}"
        "return (function(){})[" + ctor + "]"
        "(_G[" + duri + "](_G[" + esc + "](_G[" + atob + "](_r))))();"
        "}())"
    )


def pack(src, layers=2):
    """Bungkus src menjadi IIFE self-decoding. layers = jumlah lapis (1..5)."""
    layers = max(1, min(5, int(layers)))
    out = src
    for _ in range(layers):
        out = _pack_once(out)
    return out
