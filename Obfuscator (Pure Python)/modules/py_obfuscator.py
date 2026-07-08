import base64
import random
import zlib

MIN_LAYERS = 1
MAX_LAYERS = 5
_R = 94


def _name(s):
    return "''.join(map(chr,[%s]))" % ",".join(str(ord(c)) for c in s)


def _blob(codes):
    parts = ['"']
    for c in codes:
        ch = chr(c)
        if ch in ('"', "\\"):
            parts.append("\\" + ch)
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def _wrap_once(source):
    raw = zlib.compress(source.encode("utf-8"), 9)
    b64 = base64.b64encode(raw).decode("ascii")
    seed = random.randint(0, _R - 1)
    codes = []
    prev = seed
    for k, ch in enumerate(b64):
        key = (prev * 7 + k + seed) % _R
        c = ((ord(ch) - 33) + key) % _R
        codes.append(c + 33)
        prev = c
    blob = _blob(codes)
    unroll = (
        "''.join(chr(((ord(_[____])-33-(((__ if ____==0 else ord(_[____-1])-33)"
        "*7+____+__)%94))%94)+33)for ____ in range(len(_)))"
    )
    decode = (
        "___(" + _name("zlib") + "," + _name("decompress") + ")("
        "___(" + _name("base64") + "," + _name("b64decode") + ")("
        + unroll + ")).decode()"
    )
    return (
        "(lambda _,__,___:___(" + _name("builtins") + "," + _name("exec") + ")("
        + decode + ",globals()))(" + blob + "," + str(seed)
        + ",lambda _,__:getattr(__import__(_),__))"
    )


def obfuscate_python(source, layers=2):
    if not source.strip():
        raise ValueError("Input kosong")
    layers = max(MIN_LAYERS, min(MAX_LAYERS, int(layers)))
    result = source
    for _ in range(layers):
        result = _wrap_once(result)
    return result
