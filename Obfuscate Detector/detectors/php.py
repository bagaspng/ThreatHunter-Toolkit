import re

from detectors.base import Finding, register

_DECODERS = (r"(?:gzinflate|gzuncompress|gzdecode|base64_decode|str_rot13|"
             r"convert_uudecode|hex2bin|urldecode)")
_RE_EVAL_DECODE = re.compile(
    r"\b(?:eval|assert|create_function|preg_replace_callback)\s*\([^;]{0,200}?"
    + _DECODERS, re.I | re.S)
_RE_PREG_E = re.compile(
    r"preg_replace\s*\(\s*(['\"])(?:(?!\1).){0,80}/[a-zA-Z]*e[a-zA-Z]*\1",
    re.I | re.S)
_RE_GLOBALS = re.compile(r"\$GLOBALS\s*\[")
_RE_VARVAR = re.compile(r"\$\$[A-Za-z_]")
_RE_CHR_CONCAT = re.compile(r"chr\s*\(\s*\d+\s*\)\s*\.")


def _add(out, name, conf, evidence, clue):
    out.append(Finding(name=name, category="php", confidence=conf,
                       evidence=evidence, clue=clue))


@register
def detect_php(text):
    text = text or ""
    out = []

    if _RE_EVAL_DECODE.search(text):
        _add(out, "php_eval_decode", 90,
             "eval/assert atas rantai decode (base64/gzinflate/str_rot13 ...)",
             "Ini ciri khas 'webshell' PHP: perintah tersembunyi dibuka lalu "
             "langsung dijalankan di server. Jangan dijalankan. Untuk melihat "
             "isinya, ganti perintah 'eval' dengan 'echo' agar hanya "
             "ditampilkan.")

    if _RE_PREG_E.search(text):
        _add(out, "php_preg_e", 85,
             "preg_replace dengan modifier /e (mengeksekusi replacement)",
             "Kode ini memakai trik lama PHP (preg_replace dengan tanda /e) "
             "untuk menjalankan teks sebagai perintah. Baca bagian "
             "penggantinya sebagai perintah, bukan sebagai teks biasa.")

    g = len(_RE_GLOBALS.findall(text))
    vv = len(_RE_VARVAR.findall(text))
    if g >= 3 or vv >= 2:
        _add(out, "php_globals_obf", 70,
             "%d $GLOBALS[...] + %d variable-variable $$" % (g, vv),
             "Kode ini menyembunyikan alur kerjanya lewat variabel global dan "
             "variabel-berlapis agar sulit diikuti. Catat nilai tiap variabel "
             "untuk memahami maksud sebenarnya.")

    cc = len(_RE_CHR_CONCAT.findall(text))
    if cc >= 5:
        _add(out, "php_char_concat", 55,
             "%d chr(n). dirangkai membangun string/kode" % cc,
             "Teks dirakit dari kode angka setiap huruf agar tersembunyi. Ini "
             "sinyal lemah; ubah angka-angkanya menjadi huruf untuk "
             "membacanya.")

    return out
