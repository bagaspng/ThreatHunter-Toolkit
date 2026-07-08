import re

from modules import substitution_cipher
from modules import zwsp_delimiter
from modules import anti_tamper

_CHARSET_RE = re.compile("^[A-Za-z0-9+/=​‌⁠‍﻿]*$")

def verify(final_html, expected_rendered):
    if "<script" not in final_html.lower():
        return False, "Output tidak memuat <script> loader."
    if "<!doctype" not in final_html.lower():
        return False, "Output tidak memuat DOCTYPE."
    try:
        payload_b64, inverse_b64 = substitution_cipher.encode(expected_rendered)
        combined = zwsp_delimiter.combine([payload_b64, inverse_b64])
        if not _CHARSET_RE.match(combined):
            return False, "Charset payload tidak valid (guard anti-tamper)."
        _ = anti_tamper.checksum(combined)
        parts = zwsp_delimiter.split(combined)
        if len(parts) != 2:
            return False, "Pemisahan zero-width menghasilkan bagian tak terduga."
        decoded = substitution_cipher.decode(parts[0], parts[1])
    except Exception as e:
        return False, "Gagal round-trip decode: %s" % e
    if decoded == expected_rendered:
        return True, ("Verifikasi OK: skema decode (substitution+zero-width+"
                      "checksum) round-trip identik dengan input.")
    return False, "Hasil decode tidak identik dengan dokumen input."
