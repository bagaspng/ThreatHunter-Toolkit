"""Charset / integrity anti-tamper check.

Snippet JS di-*generate dari Python* dan disisipkan di awal loader. Saat
runtime snippet:
  1. Memastikan payload hanya berisi charset yang diharapkan (alfabet base64 +
     karakter zero-width delimiter). Karakter lain = indikasi payload diutak-atik.
  2. Menghitung ulang checksum djb2 payload dan membandingkannya dengan nilai
     yang sudah dihitung Python. Kalau beda -> throw, loader berhenti.

Checksum djb2 (varian XOR) dibuat identik antara Python dan JS dengan
aritmetika 32-bit unsigned.
"""

# Charset yang diizinkan: base64 (A-Za-z0-9+/=) + 5 karakter zero-width
# delimiter (U+200B U+200C U+2060 U+200D U+FEFF).
_CHARSET_REGEX = "/^[A-Za-z0-9+/=\\u200b\\u200c\\u2060\\u200d\\ufeff]*$/"


def checksum(s):
    """djb2-xor 32-bit unsigned. Harus cocok dengan js_checksum_function()."""
    h = 5381
    for ch in s:
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    return h


def js_checksum_function(fn_name):
    return (
        "function " + fn_name + "(s){var h=5381;"
        "for(var i=0;i<s.length;i++){h=((h*33)^s.charCodeAt(i))>>>0;}"
        "return h;}"
    )


def js_guard(payload_var, ck_fn, expected):
    """Statement JS yang membatalkan eksekusi kalau payload tampak dirusak."""
    return (
        "if(!" + _CHARSET_REGEX + ".test(" + payload_var + ")){"
        "throw new Error('tamper: charset');}"
        "if(" + ck_fn + "(" + payload_var + ")!==" + str(expected) + "){"
        "throw new Error('tamper: checksum');}"
    )
