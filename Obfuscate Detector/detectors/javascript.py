import re

from detectors.base import Finding, register

_RE_PACKER = re.compile(r"eval\(function\(p,a,c,k,e,[dr]?\)")
_RE_HEXNAME = re.compile(r"_0x[0-9a-fA-F]{3,}")
_RE_ARRAY_IDX = re.compile(r"_0x[0-9a-fA-F]+\[(?:0x)?[0-9a-fA-F]+\]")
_RE_HEX_ESC = re.compile(r"\\x[0-9a-fA-F]{2}")
_RE_FROMCHAR = re.compile(r"String\.fromCharCode\(")
_RE_EVAL_ATOB = re.compile(r"eval\(\s*atob\(")
_RE_DYN_DECODE = re.compile(r"\bunescape\(|\bdecodeURIComponent\(")


def _add(out, name, conf, evidence, clue):
    out.append(Finding(name=name, category="javascript", confidence=conf,
                       evidence=evidence, clue=clue))


@register
def detect_javascript(text):
    text = text or ""
    out = []

    if _RE_PACKER.search(text):
        _add(out, "js_packer", 95,
             "signature Dean Edwards packer: eval(function(p,a,c,k,e,d))",
             "Ini packer Dean Edwards. JANGAN eval. Ganti 'eval(' terakhir "
             "dengan 'console.log(' / return untuk lihat sumber, atau pakai "
             "de4js (mode 'Packer').")

    hexnames = len(_RE_HEXNAME.findall(text))
    idx = len(_RE_ARRAY_IDX.findall(text))
    if hexnames >= 5 and (idx >= 1 or "['\\x" in text or '["\\x' in text):
        _add(out, "obfuscator_io", 90,
             "%d identifier _0x + %d akses array _0x[..], gaya obfuscator.io"
             % (hexnames, idx),
             "Kemungkinan output obfuscator.io. Pakai de4js atau Wakaru untuk "
             "un-flatten string-array dan rename identifier.")

    fromchar = len(_RE_FROMCHAR.findall(text))
    if fromchar >= 3:
        _add(out, "js_fromcharcode", 70,
             "%d pemakaian String.fromCharCode(" % fromchar,
             "String dibangun dari kode karakter. Kumpulkan argumen "
             "fromCharCode lalu chr() di sisi analisis untuk baca string.")

    hexesc = len(_RE_HEX_ESC.findall(text))
    if hexesc >= 20:
        _add(out, "js_hex_escape", 65,
             "%d escape heksadesimal \\xNN di dalam string" % hexesc,
             "Literal string disamarkan pakai \\xNN. Un-escape dengan "
             "js-beautify atau CyberChef 'JS String' untuk baca teks asli.")

    if idx >= 3:
        _add(out, "js_array_index", 75,
             "%d pola akses string via indeks array _0x[..]" % idx,
             "Pola string-array lookup. Cari deklarasi array-nya, petakan "
             "indeks -> nilai untuk memulihkan string.")

    if _RE_EVAL_ATOB.search(text):
        _add(out, "js_eval_atob", 75,
             "eval(atob(...)) — dekode lalu eksekusi payload saat runtime",
             "Ada eval(atob()). Ganti eval dengan console.log untuk menangkap "
             "payload tanpa menjalankannya.")
    elif _RE_DYN_DECODE.search(text):
        _add(out, "js_eval_atob", 40,
             "pemakaian unescape()/decodeURIComponent() (bisa sah untuk URL)",
             "Dekode runtime terdeteksi. Sinyal lemah — sering dipakai wajar "
             "untuk URL. Periksa apakah hasilnya di-eval/di-Function().")

    return out
