#!/usr/bin/env python3

import argparse
import json
import sys

from modules import jwt_tool


def _dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


def cmd_decode(args):
    info = jwt_tool.decode(args.token)
    print("Algoritma :", info["algorithm"])
    print("\n=== HEADER ===")
    print(_dump(info["header"]))
    print("\n=== PAYLOAD ===")
    print(_dump(info["payload"]))
    if info["claims"]:
        print("\n=== KLAIM STANDAR ===")
        for c in info["claims"]:
            baris = "  %-18s: %s" % (c["label"], c["value"])
            if c["note"]:
                baris += "  ->  %s" % c["note"]
            print(baris)
    print("\n=== SIGNATURE (base64url) ===")
    print(info["signature"] or "(kosong)")
    if args.secret is not None:
        hasil = jwt_tool.verify(args.token, args.secret)
        tanda = "VALID" if hasil["verified"] else "TIDAK VALID"
        print("\n=== VERIFIKASI ===")
        print("Status :", tanda)
        print("Alasan :", hasil["reason"])


def cmd_verify(args):
    hasil = jwt_tool.verify(args.token, args.secret)
    tanda = "VALID" if hasil["verified"] else "TIDAK VALID"
    print("Algoritma :", hasil["algorithm"])
    print("Status    :", tanda)
    print("Alasan    :", hasil["reason"])
    sys.exit(0 if hasil["verified"] else 1)


def cmd_encode(args):
    payload = json.loads(args.payload)
    header = json.loads(args.header) if args.header else None
    token = jwt_tool.encode(payload, args.secret, args.alg, header=header)
    print(token)


def main():
    ap = argparse.ArgumentParser(
        description="Alat JWT serba-guna (decode / verify / encode) — "
                    "murni Python, HMAC HS256/HS384/HS512.")
    sub = ap.add_subparsers(dest="perintah", required=True)

    d = sub.add_parser("decode", help="Baca header, payload, dan klaim token.")
    d.add_argument("token", help="String JWT (header.payload.signature).")
    d.add_argument("--secret", help="Bila diisi, sekalian verifikasi signature.")
    d.set_defaults(func=cmd_decode)

    v = sub.add_parser("verify", help="Cek signature dengan secret.")
    v.add_argument("token")
    v.add_argument("--secret", required=True)
    v.set_defaults(func=cmd_verify)

    e = sub.add_parser("encode", help="Buat & tanda tangani token baru.")
    e.add_argument("--payload", required=True,
                   help="Payload JSON, mis. '{\"sub\":\"123\",\"name\":\"Ana\"}'.")
    e.add_argument("--secret", required=True, help="Secret untuk HMAC.")
    e.add_argument("--alg", default="HS256",
                   choices=["HS256", "HS384", "HS512"], help="Algoritma (HS256).")
    e.add_argument("--header", help="Header JSON tambahan (opsional).")
    e.set_defaults(func=cmd_encode)

    args = ap.parse_args()
    try:
        args.func(args)
    except (ValueError, json.JSONDecodeError) as err:
        print("Error:", err, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
