"""Zero-width unicode delimiter (layer Python).

Dipakai untuk menggabungkan beberapa bagian data (di sini: payload cipher dan
tabel invers) menjadi satu string tunggal di dalam loader, dipisah oleh
sederet karakter zero-width yang tak terlihat di editor.

Karena alfabet base64 (A-Za-z0-9+/=) sama sekali tidak memuat karakter
zero-width, pemisahan di sisi JS dijamin tidak ambigu.
"""

# Deretan karakter zero-width sebagai delimiter:
#   U+200B ZERO WIDTH SPACE
#   U+200C ZERO WIDTH NON-JOINER
#   U+2060 WORD JOINER
#   U+200D ZERO WIDTH JOINER
#   U+FEFF ZERO WIDTH NO-BREAK SPACE
ZW_DELIM = "​‌⁠‍﻿"

# Bentuk literal JS (escape \u supaya aman di dalam sumber loader).
ZW_DELIM_JS = "'\\u200b\\u200c\\u2060\\u200d\\ufeff'"


def combine(parts):
    """Gabungkan daftar string jadi satu, dipisah delimiter zero-width."""
    return ZW_DELIM.join(parts)


def js_split_function(fn_name):
    """JS yang mendefinisikan `fn_name(s)` -> array bagian (split delimiter)."""
    return (
        "function " + fn_name + "(s){return s.split(" + ZW_DELIM_JS + ");}"
    )
