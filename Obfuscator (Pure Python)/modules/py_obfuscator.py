import random

MIN_LAYERS = 1
MAX_LAYERS = 3

_SOURCES = [
    ("type", type), ("int", int), ("dict", dict), ("object", object),
    ("complex", complex), ("bytes", bytes), ("true", True),
]
_SRC_EXPR = {
    "type": "str(type)", "int": "str(int)", "dict": "str(dict)",
    "object": "str(object)", "complex": "str(complex)",
    "bytes": "str(bytes)", "true": "str(True)",
}


def _num(n, d):
    z, o, t = d
    if n == 0:
        return z
    if n == 1:
        return o
    if n == 2:
        return t
    half = _num(n // 2, d)
    if n % 2:
        return "(" + t + "*" + half + "+" + o + ")"
    return "(" + t + "*" + half + ")"


def _replay(cipher, seed):
    out = bytearray()
    for k, c in enumerate(cipher):
        prev = seed if k == 0 else cipher[k - 1]
        key = (prev * 7 + k + seed) % 256
        out.append((c - key) % 256)
    return bytes(out)


def _wrap_once(source):
    raw = source.encode("utf-8")
    seed = random.randint(0, 255)
    cipher = []
    prev = seed
    for k, b in enumerate(raw):
        key = (prev * 7 + k + seed) % 256
        c = (b + key) % 256
        cipher.append(c)
        prev = c

    if _replay(cipher, seed) != raw:
        raise RuntimeError("py self-check gagal: round-trip decode tidak cocok")

    getter, z, o, t = "_", "__", "___", "____"
    d = (z, o, t)
    reprs = {k: str(v) for k, v in _SOURCES}

    def find(ch):
        for k, _v in _SOURCES:
            i = reprs[k].find(ch)
            if i >= 0:
                return k, i
        raise ValueError("tak ada sumber untuk %r" % ch)

    charmap = {}
    used = []
    for nm in ("builtins", "exec", "bytes", "decode"):
        for ch in nm:
            if ch not in charmap:
                k, i = find(ch)
                charmap[ch] = (k, i)
                if k not in used:
                    used.append(k)

    lines = [
        getter + "=lambda _:_.__code__.co_argcount",
        z + "=" + getter + "(lambda:" + getter + ")",
        o + "=" + getter + "(lambda _:_)",
        t + "=" + getter + "(lambda _,__:_)",
    ]
    srcvar = {}
    for idx, k in enumerate(used):
        srcvar[k] = "_" * (5 + idx)
        lines.append(srcvar[k] + "=" + _SRC_EXPR[k])

    def word(s):
        return "+".join(
            srcvar[charmap[ch][0]] + "[" + _num(charmap[ch][1], d) + "]" for ch in s
        )

    bimod = "_" * (5 + len(used))
    payvar = "_" * (6 + len(used))
    kvar = "_" * (7 + len(used))
    lines.append(bimod + "=__import__(" + word("builtins") + ")")
    lines.append(payvar + "=(" + ",".join(_num(c, d) for c in cipher) + ",)")

    decipher = (
        "[(" + payvar + "[" + kvar + "]-((" + _num(seed, d) + " if " + kvar
        + "==" + z + " else " + payvar + "[" + kvar + "-" + o + "])*" + _num(7, d)
        + "+" + kvar + "+" + _num(seed, d) + "))%" + _num(256, d)
        + " for " + kvar + " in range(len(" + payvar + "))]"
    )
    raw_call = "getattr(" + bimod + "," + word("bytes") + ")(" + decipher + ")"
    text_call = "getattr(" + raw_call + "," + word("decode") + ")()"
    lines.append(
        "getattr(" + bimod + "," + word("exec") + ")(" + text_call + ",globals())"
    )
    return ";".join(lines)


def obfuscate_python(source, layers=1):
    if not source.strip():
        raise ValueError("Input kosong")
    layers = max(MIN_LAYERS, min(MAX_LAYERS, int(layers)))
    result = source
    for _ in range(layers):
        result = _wrap_once(result)
    compile(result, "<obfuscated>", "exec")
    return result
