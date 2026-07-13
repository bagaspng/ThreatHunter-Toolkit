#!/usr/bin/env python3

import struct
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _unfilter(raw, w, h, ch):
    stride = w * ch
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif f == 4:
                q = a + b - c
                pa, pb, pc = abs(q - a), abs(q - b), abs(q - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out += line
        prev = line
    return out


def read_png_rgba(data):
    if data[:8] != PNG_SIG:
        raise ValueError("Berkas ini bukan PNG.")

    w, h = struct.unpack(">II", data[16:24])
    bitdepth, colortype, interlace = data[24], data[25], data[28]
    if bitdepth != 8:
        raise ValueError("Hanya mendukung PNG 8-bit (berkas ini %d-bit)." % bitdepth)
    if interlace != 0:
        raise ValueError("PNG interlaced belum didukung.")
    if colortype not in CHANNELS:
        raise ValueError("Tipe warna PNG tidak dikenal: %d" % colortype)

    idat = b""
    plte = None
    trns = None
    i = 8
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        payload = data[i + 8:i + 8 + n]
        if typ == b"IDAT":
            idat += payload
        elif typ == b"PLTE":
            plte = payload
        elif typ == b"tRNS":
            trns = payload
        i += 12 + n
        if typ == b"IEND":
            break

    ch = CHANNELS[colortype]
    samples = _unfilter(zlib.decompress(idat), w, h, ch)

    rgba = bytearray(w * h * 4)
    npix = w * h
    if colortype == 6:
        return w, h, bytearray(samples)
    if colortype == 2:
        for k in range(npix):
            rgba[k * 4:k * 4 + 3] = samples[k * 3:k * 3 + 3]
            rgba[k * 4 + 3] = 255
    elif colortype == 0:
        for k in range(npix):
            g = samples[k]
            rgba[k * 4] = rgba[k * 4 + 1] = rgba[k * 4 + 2] = g
            rgba[k * 4 + 3] = 255
    elif colortype == 4:
        for k in range(npix):
            g = samples[k * 2]
            rgba[k * 4] = rgba[k * 4 + 1] = rgba[k * 4 + 2] = g
            rgba[k * 4 + 3] = samples[k * 2 + 1]
    elif colortype == 3:
        if plte is None:
            raise ValueError("PNG palette tanpa chunk PLTE.")
        for k in range(npix):
            idx = samples[k]
            rgba[k * 4:k * 4 + 3] = plte[idx * 3:idx * 3 + 3]
            rgba[k * 4 + 3] = trns[idx] if (trns and idx < len(trns)) else 255
    return w, h, rgba


def _chunk(typ, payload):
    return (struct.pack(">I", len(payload)) + typ + payload
            + struct.pack(">I", zlib.crc32(typ + payload) & 0xffffffff))


def write_png_rgba(w, h, rgba):
    stride = w * 4
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)
    return PNG_SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def capacity_bytes(w, h):
    return (w * h * 3) // 8


def encode(png_bytes, message):
    w, h, rgba = read_png_rgba(png_bytes)
    payload = message.encode("utf-8")

    bits = []
    for byte in payload:
        for b in range(7, -1, -1):
            bits.append((byte >> b) & 1)

    if len(bits) > w * h * 3:
        raise ValueError("Pesan terlalu panjang untuk gambar ini "
                         "(maks %d byte)." % capacity_bytes(w, h))

    counter = 0
    total = len(bits)
    for i in range(0, len(rgba), 4):
        for offset in range(3):
            idx = i + offset
            rgba[idx] &= 0xFE
            if counter < total:
                rgba[idx] |= bits[counter]
                counter += 1
        if counter >= total:
            for offset in range(3):
                nxt = i + 4 + offset
                if nxt < len(rgba):
                    rgba[nxt] &= 0xFE
            break

    return write_png_rgba(w, h, rgba)


def readability(text):
    if not text:
        return 0.0
    ok = 0
    for c in text:
        o = ord(c)
        if c == "�" or o == 127 or (o < 32 and c not in "\t\n\r"):
            continue
        ok += 1
    return ok / len(text)


def decode(png_bytes):
    _w, _h, rgba = read_png_rgba(png_bytes)
    bits = []
    for i in range(0, len(rgba), 4):
        for offset in range(3):
            bits.append(rgba[i + offset] & 1)

    out = bytearray()
    for k in range(0, len(bits) - 7, 8):
        v = 0
        for j in range(8):
            v = (v << 1) | bits[k + j]
        if v == 0:
            break
        out.append(v)
    return out.decode("utf-8", errors="replace")
