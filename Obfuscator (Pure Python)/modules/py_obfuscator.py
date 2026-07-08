import base64
import marshal
import random
import zlib

MIN_LAYERS = 1
MAX_LAYERS = 5
_R = 94  # jumlah karakter printable yang dipakai (kode 33..126)


def _pychr(s):
    # Ekspresi Python yang merangkai string dari kode karakter, supaya nama
    # sensitif (exec, marshal, base64, zlib, ...) tidak muncul sebagai literal
    # dan tidak bisa di-grep.
    return "''.join(map(chr,[%s]))" % ",".join(str(ord(c)) for c in s)


def _blob_literal(codes):
    # Rangkai kode karakter (33..126) jadi literal string Python. Hanya kutip
    # dan backslash yang perlu di-escape; sisanya printable apa adanya.
    parts = ['"']
    for c in codes:
        ch = chr(c)
        if ch in ('"', "\\"):
            parts.append("\\" + ch)
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def _wrap_once(source, filename="<obfuscated>"):
    code_obj = compile(source, filename, "exec")
    raw = zlib.compress(marshal.dumps(code_obj), 9)
    b64 = base64.b64encode(raw).decode("ascii")

    seed = random.randint(0, _R - 1)
    codes = []
    prev = seed
    for k, ch in enumerate(b64):
        key = (prev * 7 + k + seed) % _R
        c = ((ord(ch) - 33) + key) % _R          # 0..93
        codes.append(c + 33)                     # 33..126 (printable)
        prev = c
    blob = _blob_literal(codes)
    s = str(seed)

    # rolling cipher -> string base64
    unroll = (
        "''.join(chr(((ord(_B[_k])-33-(((_S if _k==0 else ord(_B[_k-1])-33)"
        "*7+_k+_S)%94))%94)+33)for _k in range(len(_B)))"
    )
    # base64 -> zlib -> marshal -> code object (semua nama disembunyikan)
    decode = (
        "_x(_i(" + _pychr("marshal") + ")," + _pychr("loads") + ")("
        "_x(_i(" + _pychr("zlib") + ")," + _pychr("decompress") + ")("
        "_x(_i(" + _pychr("base64") + ")," + _pychr("b64decode") + ")("
        + unroll + ")))"
    )
    # exec(code_object, globals()) via builtins, tanpa literal 'exec'
    return (
        "(lambda _B,_S,_i,_x:_x(_i(" + _pychr("builtins") + "),"
        + _pychr("exec") + ")(" + decode + ",globals()))("
        + blob + "," + s + ",__import__,getattr)"
    )


def obfuscate_python(source, layers=2):
    if not source.strip():
        raise ValueError("Input kosong")

    layers = max(MIN_LAYERS, min(MAX_LAYERS, int(layers)))

    result = source
    for _ in range(layers):
        result = _wrap_once(result)
    return result
