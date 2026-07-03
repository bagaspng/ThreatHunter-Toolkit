"""Custom substitution cipher (dilakukan di Python, di-decode di JS).

Cipher bekerja di level byte UTF-8 supaya karakter kompleks (emoji, aksara
non-latin) tetap utuh:

  Python (encoder):
    - Bangun permutasi acak 0..255 (tabel substitusi) + tabel inversnya.
    - Setiap byte UTF-8 dokumen dipetakan lewat tabel substitusi.
    - Hasil byte di-base64-kan jadi string ASCII (payload).
    - Tabel invers juga dikirim (base64) supaya JS bisa membalik.

  JS (decoder, disisipkan di loader):
    original_byte = inverse[ substituted_byte ]

Tabel invers ikut tertanam di loader, tapi loader nanti diobfuscate lagi
lewat javascript-obfuscator (lapis luar), jadi tidak terbaca langsung.
"""

import base64
import random


def _make_tables():
    table = list(range(256))
    random.shuffle(table)
    inverse = [0] * 256
    for original, substituted in enumerate(table):
        inverse[substituted] = original
    return table, inverse


def encode(text):
    """Return (payload_b64, inverse_b64).

    payload_b64  : base64 dari byte UTF-8 yang sudah disubstitusi.
    inverse_b64  : base64 dari 256 byte tabel invers (untuk decoder JS).
    """
    table, inverse = _make_tables()
    data = text.encode("utf-8")
    substituted = bytes(table[b] for b in data)
    payload_b64 = base64.b64encode(substituted).decode("ascii")
    inverse_b64 = base64.b64encode(bytes(inverse)).decode("ascii")
    return payload_b64, inverse_b64


def js_decoder_function(fn_name):
    """JS yang mendefinisikan `fn_name(b64, invB64)` -> string asli.

    Membalik substitusi lalu men-decode UTF-8 lewat TextDecoder supaya
    emoji/unicode kembali persis.
    """
    return (
        "function " + fn_name + "(b64,invB64){"
        "var inv=atob(invB64);"
        "var raw=atob(b64);"
        "var out=new Uint8Array(raw.length);"
        "for(var i=0;i<raw.length;i++){"
        "out[i]=inv.charCodeAt(raw.charCodeAt(i));"
        "}"
        "return new TextDecoder('utf-8').decode(out);"
        "}"
    )
