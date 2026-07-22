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
             "Perintah PowerShell dikodekan base64 (UTF-16LE). Decode base64 "
             "lalu decode teks UTF-16LE untuk baca; JANGAN jalankan.")

    if _RE_COMPRESS.search(text) and _RE_FROMB64.search(text):
        _add(out, "ps_compressed", 85,
             "DeflateStream/Gzip + FromBase64String",
             "Payload = base64 lalu dekompresi Deflate/Gzip lalu jalan. "
             "Decode base64 lalu inflate untuk baca sumber. JANGAN eksekusi.")
    elif _RE_FROMB64.search(text):
        _add(out, "ps_frombase64", 80,
             "[Convert]::FromBase64String",
             "Data base64 didekode saat runtime. Decode base64 untuk periksa; "
             "hasil bisa biner/skrip.")

    if _RE_JOIN.search(text) and _RE_CHAR.search(text):
        _add(out, "ps_char_join", 70,
             "-join dengan [char] (rakit string dari kode karakter)",
             "String dirakit dari [char] kode. Kumpulkan kode karakter untuk "
             "memulihkan teks.")

    if _RE_FORMAT.search(text) and _RE_BACKTICK.search(text):
        _add(out, "ps_format_backtick", 60,
             "format-operator -f + backtick split",
             "Obfuscate string via -f dan backtick. Rakit ulang format untuk "
             "baca perintah asli.")

    if _RE_IEX.search(text):
        _add(out, "ps_iex", 55,
             "IEX/Invoke-Expression (eksekusi string dinamis)",
             "Eksekusi string dinamis. Sinyal lemah sendiri; periksa apakah "
             "argumennya hasil decode.")

    return out
