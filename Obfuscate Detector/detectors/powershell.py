import re

from detectors.base import Finding, register

_RE_ENC = re.compile(r"-e(?:nc(?:odedcommand)?)?\b\s+[A-Za-z0-9+/=]{16,}", re.I)
_RE_FROMB64 = re.compile(r"FromBase64String", re.I)
_RE_IEX = re.compile(r"\b(?:IEX|Invoke-Expression)\b", re.I)
_RE_COMPRESS = re.compile(r"(?:DeflateStream|GzipStream|IO\.Compression)", re.I)
_RE_JOIN = re.compile(r"-join\b", re.I)
_RE_CHAR = re.compile(r"\[char\]", re.I)
_RE_FORMAT = re.compile(r"['\"]\s*-f\s", re.I)
_RE_BACKTICK = re.compile(r"[A-Za-z]`[A-Za-z]")


def _add(out, name, conf, evidence, clue):
    out.append(Finding(name=name, category="powershell", confidence=conf,
                       evidence=evidence, clue=clue))


@register
def detect_powershell(text):
    text = text or ""
    out = []

    if _RE_ENC.search(text):
        _add(out, "ps_encoded_command", 90,
             "parameter -EncodedCommand/-enc + blob base64",
             "Perintah PowerShell ini disembunyikan dalam bentuk kode base64. "
             "Buka/decode base64-nya (teksnya dalam format UTF-16) untuk "
             "membaca perintah aslinya. Jangan dijalankan.")

    if _RE_COMPRESS.search(text) and _RE_FROMB64.search(text):
        _add(out, "ps_compressed", 85,
             "DeflateStream/Gzip + FromBase64String",
             "Perintah disembunyikan dengan cara dipadatkan lalu disandikan, "
             "kemudian dijalankan. Buka/decode lalu buka pemadatannya untuk "
             "membaca. Jangan dieksekusi.")
    elif _RE_FROMB64.search(text):
        _add(out, "ps_frombase64", 80,
             "[Convert]::FromBase64String",
             "Ada data base64 yang dibuka saat program berjalan. Buka/decode "
             "base64-nya untuk memeriksa isinya (bisa berupa teks atau "
             "program).")

    if _RE_JOIN.search(text) and _RE_CHAR.search(text):
        _add(out, "ps_char_join", 70,
             "-join dengan [char] (rakit string dari kode karakter)",
             "Teks perintah dirakit dari kode angka setiap huruf agar "
             "tersembunyi. Ubah angka-angkanya kembali menjadi huruf untuk "
             "membacanya.")

    if _RE_FORMAT.search(text) and _RE_BACKTICK.search(text):
        _add(out, "ps_format_backtick", 60,
             "format-operator -f + backtick split",
             "Perintah disamarkan dengan menyusun potongan teks (operator -f) "
             "dan tanda backtick. Susun ulang untuk membaca perintah "
             "aslinya.")

    if _RE_IEX.search(text):
        _add(out, "ps_iex", 55,
             "IEX/Invoke-Expression (eksekusi string dinamis)",
             "Ada perintah yang menjalankan teks secara langsung (IEX). Ini "
             "sinyal lemah; periksa apakah teksnya berasal dari sesuatu yang "
             "dibuka/decode sebelumnya.")

    return out
