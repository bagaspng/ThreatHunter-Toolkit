import random

_CHUNK = 5000
_M = 65536


def _num(n):
    if n == 0:
        return "+[]"
    if n == 1:
        return "+!![]"
    return "+".join(["!![]"] * n)


def _rand_name():
    return "_" * random.randint(3, 6)


def _digit_map():
    lengths = list(range(1, 11))
    random.shuffle(lengths)
    return lengths


def _digit_object(g, dmap):
    parts = []
    for d in range(10):
        key = "_" * dmap[d]
        parts.append("%s:(%s)+[]" % (key, _num(d)))
    return "%s={%s}" % (g, ",".join(parts))


def _dref(g, dmap, d):
    return "%s.%s" % (g, "_" * dmap[d])


def _numx(g, dmap, value):
    return "(+(%s))" % "+".join(_dref(g, dmap, int(c)) for c in str(value))


def _units(text):
    out = []
    for ch in text:
        o = ord(ch)
        if o > 0xFFFF:
            o -= 0x10000
            out.append(0xD800 + (o >> 10))
            out.append(0xDC00 + (o & 0x3FF))
        else:
            out.append(o)
    return out


def _fcc(g, dmap, codes):
    if not codes:
        return "([]+[])"
    calls = []
    for i in range(0, len(codes), _CHUNK):
        chunk = codes[i:i + _CHUNK]
        args = ",".join(_numx(g, dmap, c) for c in chunk)
        calls.append("String.fromCharCode(%s)" % args)
    return "+".join(calls)


def _strx(g, dmap, text):
    return _fcc(g, dmap, _units(text))


def _encrypt(units, seed, mul):
    out = []
    key = seed
    for u in units:
        c = (u + key) % _M
        out.append(c)
        key = (key * mul + c + seed) % _M
    return out


def _from_units(units):
    out = []
    i = 0
    n = len(units)
    while i < n:
        u = units[i]
        if 0xD800 <= u <= 0xDBFF and i + 1 < n and 0xDC00 <= units[i + 1] <= 0xDFFF:
            out.append(chr(0x10000 + ((u - 0xD800) << 10) + (units[i + 1] - 0xDC00)))
            i += 2
        else:
            out.append(chr(u))
            i += 1
    return "".join(out)


def _replay(cipher, seed, mul):
    key = seed
    units = []
    for x in cipher:
        units.append((x - key) % _M)
        key = (key * mul + x + seed) % _M
    return units


def _pack_once(src):
    g = _rand_name()
    dmap = _digit_map()
    seed = random.randint(0, _M - 1)
    mul = random.randint(2, _M - 1) | 1
    cipher = _encrypt(_units(src), seed, mul)

    if _from_units(_replay(cipher, seed, mul)) != src:
        raise RuntimeError("packer self-check gagal: round-trip decode tidak cocok")

    kc, ka, ks, kk, kr, ki, kx = (
        "_" * 11, "_" * 12, "_" * 13, "_" * 14, "_" * 15, "_" * 16, "_" * 17,
    )
    m = _numx(g, dmap, _M)
    seedx = _numx(g, dmap, seed)
    mulx = _numx(g, dmap, mul)
    zero = _numx(g, dmap, 0)

    return (
        _digit_object(g, dmap) + ";"
        + g + "." + kc + "=" + _strx(g, dmap, "constructor") + ";"
        + g + "." + ka + "=" + _strx(g, dmap, "charCodeAt") + ";"
        + g + "." + ks + "=" + _fcc(g, dmap, cipher) + ";"
        + g + "." + kk + "=" + seedx + ";"
        + g + "." + kr + "=([]+[]);"
        + "for(" + g + "." + ki + "=" + zero + ";"
        + "(" + g + "." + kx + "=" + g + "." + ks + "[" + g + "." + ka + "]"
        + "(" + g + "." + ki + "))===" + g + "." + kx + ";"
        + g + "." + ki + "++){"
        + g + "." + kr + "=" + g + "." + kr + "+String.fromCharCode("
        + "((" + g + "." + kx + "-" + g + "." + kk + "+" + m + ")%" + m + "));"
        + g + "." + kk + "=((" + g + "." + kk + "*" + mulx + ")+"
        + g + "." + kx + "+" + seedx + ")%" + m + ";"
        + "}"
        + "[][" + g + "." + kc + "][" + g + "." + kc + "](" + g + "." + kr + ")()"
    )


def pack(src, layers=1):
    layers = max(1, min(5, int(layers)))
    out = src
    for _ in range(layers):
        out = _pack_once(out)
    return out
