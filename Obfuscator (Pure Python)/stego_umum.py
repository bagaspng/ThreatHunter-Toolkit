#!/usr/bin/env python3

import argparse
import base64
import re
import struct
import zlib

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
COLOR_NAMES = {0: "grayscale", 2: "RGB", 3: "palette (indexed)",
               4: "grayscale+alpha", 6: "RGBA"}


def baca_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Berkas ini bukan PNG.")
    w, h = struct.unpack(">II", data[16:24])
    bitdepth = data[24]
    colortype = data[25]
    interlace = data[28]
    if bitdepth != 8:
        raise ValueError("Hanya mendukung PNG 8-bit (berkas ini %d-bit)." % bitdepth)
    if interlace != 0:
        raise ValueError("PNG interlaced belum didukung.")
    if colortype not in CHANNELS:
        raise ValueError("Tipe warna PNG tidak dikenal: %d" % colortype)

    idat = b""
    i = 8
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if typ == b"IDAT":
            idat += data[i + 8:i + 8 + n]
        i += 12 + n
        if typ == b"IEND":
            break

    ch = CHANNELS[colortype]
    samples = _unfilter(zlib.decompress(idat), w, h, ch)
    return {"width": w, "height": h, "colortype": colortype,
            "channels": ch, "samples": samples}


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


def ambil_pesan(samples, nchan, channels, nbits=1, sample_order="lsb",
                max_bytes=65536):
    bits = []
    limit = max_bytes * 8
    for base_i in range(0, len(samples) - nchan + 1, nchan):
        for c in channels:
            s = samples[base_i + c]
            if sample_order == "msb":
                for b in range(nbits):
                    bits.append((s >> (nbits - 1 - b)) & 1)
            else:
                for b in range(nbits):
                    bits.append((s >> b) & 1)
        if len(bits) >= limit:
            break

    out = bytearray()
    for k in range(0, len(bits) - 7, 8):
        v = 0
        for j in range(8):
            v = (v << 1) | bits[k + j]
        out.append(v)
    return bytes(out)


def bagian_terbaca(bs):
    out = []
    for c in bs:
        if 32 <= c < 127 or c in (9, 10, 13):
            out.append(c)
        else:
            break
    return bytes(out).decode("ascii", "replace")


def skor_terbaca(bs, n=96):
    sample = bs[:n]
    if not sample:
        return 0.0
    ok = sum(1 for c in sample if 32 <= c < 127 or c in (9, 10, 13))
    return ok / len(sample)


def _mirip_base64(s):
    s = s.strip()
    return (len(s) >= 4 and len(s) % 4 == 0
            and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", s) is not None)


def kupas_base64(s):
    langkah = []
    while _mirip_base64(s):
        try:
            dec = base64.b64decode(s).decode("utf-8")
        except Exception:
            break
        langkah.append(dec)
        s = dec
    return s, langkah


def _preset_channel(nchan):
    if nchan == 1:
        return [("channel 0", [0])]
    if nchan == 2:
        return [("gray", [0]), ("gray+alpha", [0, 1]), ("alpha", [1])]
    if nchan == 3:
        return [("R,G,B", [0, 1, 2]), ("R", [0]), ("G", [1]), ("B", [2])]
    return [("R,G,B", [0, 1, 2]), ("R,G,B,A", [0, 1, 2, 3]),
            ("R", [0]), ("G", [1]), ("B", [2]), ("A (alpha)", [3])]


def mode_auto(info):
    samples, nchan = info["samples"], info["channels"]
    hasil = []
    for nama, chs in _preset_channel(nchan):
        data = ambil_pesan(samples, nchan, chs, nbits=1, max_bytes=8192)
        hasil.append((skor_terbaca(data), nama, chs, data))
    hasil.sort(reverse=True, key=lambda t: t[0])

    print("Peringkat kombinasi (LSB 1 bit):")
    for skor, nama, _chs, data in hasil:
        cuplik = bagian_terbaca(data)[:60]
        print("  %-11s  terbaca %3d%%  ->  %s" % (nama, round(skor * 100), cuplik))

    skor, nama, chs, data = hasil[0]
    teks = bagian_terbaca(data)
    print("\nKandidat terbaik: %s" % nama)
    print("Teks mentah     :", teks[:120] if teks else "(kosong)")
    final, langkah = kupas_base64(teks)
    for i, s in enumerate(langkah, 1):
        print("  base64 lapis %d ->" % i, s[:120])
    print("\nKEMUNGKINAN PESAN:", final if final else "(tidak ditemukan teks terbaca)")


def mode_manual(info, channels, nbits, order, pakai_base64):
    samples, nchan = info["samples"], info["channels"]
    for c in channels:
        if c >= nchan:
            raise ValueError("Channel %d tidak ada (gambar hanya punya %d channel)."
                             % (c, nchan))
    data = ambil_pesan(samples, nchan, channels, nbits=nbits, sample_order=order)
    teks = bagian_terbaca(data)
    print("Channel dipakai :", channels, "| bit:", nbits, "| urutan:", order)
    print("Teks mentah     :", teks[:200] if teks else "(kosong)")
    if pakai_base64:
        final, langkah = kupas_base64(teks)
        for i, s in enumerate(langkah, 1):
            print("  base64 lapis %d ->" % i, s[:200])
        print("PESAN           :", final)


def main():
    ap = argparse.ArgumentParser(
        description="Ekstraktor pesan LSB serba-guna untuk PNG.")
    ap.add_argument("image", help="Berkas PNG yang diperiksa.")
    ap.add_argument("--channels",
                    help="Indeks channel dipisah koma, mis. 0,1,2 (mode manual).")
    ap.add_argument("--bits", type=int, default=1,
                    help="Jumlah bit LSB per sample (default 1).")
    ap.add_argument("--order", choices=["lsb", "msb"], default="lsb",
                    help="Urutan bit dalam satu sample bila --bits > 1.")
    ap.add_argument("--no-base64", action="store_true",
                    help="Jangan coba mengupas base64.")
    args = ap.parse_args()

    info = baca_png(args.image)
    print("Gambar   : %s" % args.image)
    print("Ukuran   : %d x %d piksel" % (info["width"], info["height"]))
    print("Tipe     : %s (%d channel)\n"
          % (COLOR_NAMES[info["colortype"]], info["channels"]))

    if args.channels:
        chs = [int(x) for x in args.channels.split(",") if x.strip() != ""]
        mode_manual(info, chs, args.bits, args.order, not args.no_base64)
    else:
        mode_auto(info)


if __name__ == "__main__":
    main()
