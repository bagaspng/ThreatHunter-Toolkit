import re

from detectors.base import Finding, register

_RE_PACKER = re.compile(
    r"eval\s*\(\s*function\s*\(\s*p\s*,\s*a\s*,\s*c\s*,\s*k\s*,\s*e\s*,"
    r"\s*[dr]?\s*\)")
_RE_HEXNAME = re.compile(r"_0x[0-9a-fA-F]{3,}")
_RE_ARRAY_IDX = re.compile(r"_0x[0-9a-fA-F]+\[(?:0x)?[0-9a-fA-F]+\]")
_RE_HEX_ESC = re.compile(r"\\x[0-9a-fA-F]{2}")
_RE_FROMCHAR = re.compile(r"String\.fromCharCode\(")
_RE_EVAL_ATOB = re.compile(r"eval\(\s*atob\(")
_RE_DYN_DECODE = re.compile(r"\bunescape\(|\bdecodeURIComponent\(")
_RE_AAENCODE = re.compile("ﾟωﾟ|ﾟΘﾟ|ﾟДﾟ|ﾟ∀ﾟ|ﾟｰﾟ")
_RE_JJENCODE = re.compile(r"\$=~\[\]|\$\$\$\$|\$=\{")
_JSFUCK_CHARS = frozenset("[]()!+")


def _jsfuck_ratio(text):
    stripped = [c for c in text if not c.isspace()]
    if len(stripped) < 20:
        return 0.0
    hits = sum(1 for c in stripped if c in _JSFUCK_CHARS)
    return hits / len(stripped)


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
             "Kode JavaScript ini dibungkus dengan teknik 'packer' agar tidak "
             "terbaca. Untuk melihat isi aslinya dengan aman (tanpa "
             "menjalankannya), ganti perintah 'eval' di bagian akhir dengan "
             "'console.log', atau pakai alat pembuka packer daring seperti "
             "de4js.")

    hexnames = len(_RE_HEXNAME.findall(text))
    idx = len(_RE_ARRAY_IDX.findall(text))
    if hexnames >= 5 and (idx >= 1 or "['\\x" in text or '["\\x' in text):
        _add(out, "obfuscator_io", 90,
             "%d identifier _0x + %d akses array _0x[..], gaya obfuscator.io"
             % (hexnames, idx),
             "Kode ini diacak oleh alat obfuscator.io (nama variabel berubah "
             "jadi _0x...). Pakai alat pembuka daring seperti de4js untuk "
             "merapikannya dan memulihkan teks aslinya.")

    fromchar = len(_RE_FROMCHAR.findall(text))
    if fromchar >= 3:
        _add(out, "js_fromcharcode", 70,
             "%d pemakaian String.fromCharCode(" % fromchar,
             "Teks di kode ini dibangun dari kode angka setiap huruf agar "
             "tersembunyi. Kumpulkan angka-angkanya lalu ubah kembali menjadi "
             "huruf untuk membacanya.")

    hexesc = len(_RE_HEX_ESC.findall(text))
    if hexesc >= 20:
        _add(out, "js_hex_escape", 65,
             "%d escape heksadesimal \\xNN di dalam string" % hexesc,
             "Teks di kode ini disamarkan memakai kode heksadesimal (\\xNN). "
             "Rapikan dengan alat penata kode (beautifier) untuk melihat teks "
             "aslinya.")

    if idx >= 3:
        _add(out, "js_array_index", 75,
             "%d pola akses string via indeks array _0x[..]" % idx,
             "Teks disimpan dalam sebuah daftar lalu dipanggil lewat nomor "
             "urut agar sulit dibaca. Cari daftarnya, lalu cocokkan tiap "
             "nomor dengan isinya untuk memulihkan teks.")

    if _RE_EVAL_ATOB.search(text):
        _add(out, "js_eval_atob", 75,
             "eval(atob(...)) — dekode lalu eksekusi payload saat runtime",
             "Kode ini membuka lalu langsung menjalankan perintah yang "
             "disembunyikan. Untuk melihat isinya dengan aman, ganti perintah "
             "'eval' dengan 'console.log' supaya isinya ditampilkan, bukan "
             "dijalankan.")
    elif _RE_DYN_DECODE.search(text):
        _add(out, "js_eval_atob", 40,
             "pemakaian unescape()/decodeURIComponent() (bisa sah untuk URL)",
             "Ada pembukaan kode saat program berjalan. Ini sering wajar "
             "untuk menangani alamat web, jadi belum tentu berbahaya. Periksa "
             "apakah hasilnya kemudian dijalankan.")

    if _jsfuck_ratio(text) > 0.9:
        _add(out, "jsfuck", 95,
             "teks JS hampir seluruhnya simbol []()!+ (JSFuck)",
             "Kode ini ditulis hanya dengan simbol []()!+ (teknik JSFuck) agar "
             "tidak terbaca. Pakai pembuka JSFuck daring, atau ganti perintah "
             "di bagian akhir dengan 'console.log' agar isinya tampil tanpa "
             "dijalankan.")

    if _RE_AAENCODE.search(text):
        _add(out, "aaencode", 95,
             "pola emoji Jepang (ﾟωﾟ) khas AAencode",
             "Kode ini disamarkan menjadi bentuk 'emoji' Jepang (teknik "
             "AAencode). Ganti pemanggil di bagian akhir dengan 'console.log' "
             "untuk melihat isi aslinya tanpa menjalankannya.")

    if _RE_JJENCODE.search(text):
        _add(out, "jjencode", 90,
             "pola $=~[] khas JJencode",
             "Kode ini diacak dengan teknik JJencode (banyak simbol $). Pakai "
             "pembuka JJencode daring untuk memulihkan isi aslinya.")

    return out
