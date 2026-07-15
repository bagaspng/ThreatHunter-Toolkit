#!/usr/bin/env python3
import argparse
import base64
import getpass
import os
import struct
import sys
import json

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet, InvalidToken

MAGIC = b"FVEIL01\x00"
SALT_LEN = 16
KDF_ITERATIONS = 480_000
NO_PASSWORD_DEFAULT = "default-script-password"


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


def check_extension_match(cover_path, output_path):
    cover_ext = os.path.splitext(cover_path)[1].lower()
    output_ext = os.path.splitext(output_path)[1].lower()

    if cover_ext != output_ext:
        print(f"[GAGAL] Ekstensi tidak cocok: cover='{cover_ext or '(tanpa ekstensi)'}' "
              f"vs output='{output_ext or '(tanpa ekstensi)'}'")
        print("        Gunakan ekstensi output yang sama dengan cover agar file tetap bisa dibuka normal.")
        sys.exit(1)


def pack_files(paths):
    entries = []
    blob = bytearray()
    for p in paths:
        with open(p, "rb") as f:
            data = f.read()
        entries.append({"name": os.path.basename(p), "size": len(data)})
        blob += data

    header = json.dumps({"files": entries}).encode("utf-8")
    return struct.pack(">I", len(header)) + header + bytes(blob)


def unpack_files(blob: bytes, out_dir: str):
    header_len = struct.unpack(">I", blob[:4])[0]
    header = json.loads(blob[4:4 + header_len].decode("utf-8"))
    offset = 4 + header_len

    os.makedirs(out_dir, exist_ok=True)
    restored = []
    for entry in header["files"]:
        size = entry["size"]
        data = blob[offset:offset + size]
        offset += size
        out_path = os.path.join(out_dir, entry["name"])
        with open(out_path, "wb") as f:
            f.write(data)
        restored.append(out_path)
    return restored


def hide(cover_path, secret_paths, output_path, password):
    check_extension_match(cover_path, output_path)

    with open(cover_path, "rb") as f:
        cover_data = f.read()

    plain_blob = pack_files(secret_paths)

    salt = os.urandom(SALT_LEN)
    key = derive_key(password, salt)
    token = Fernet(key).encrypt(plain_blob)

    protected_flag = b"\x01" if password != NO_PASSWORD_DEFAULT else b"\x00"
    appended = MAGIC + protected_flag + salt + struct.pack(">I", len(token)) + token

    with open(output_path, "wb") as f:
        f.write(cover_data)
        f.write(appended)

    print(f"[OK] {len(secret_paths)} file disembunyikan ke dalam '{output_path}'")
    print(f"     Ukuran asli cover : {len(cover_data)} bytes")
    print(f"     Ukuran ditambahkan: {len(appended)} bytes")


def extract(input_path, out_dir):
    with open(input_path, "rb") as f:
        data = f.read()

    idx = data.rfind(MAGIC)
    if idx == -1:
        print("[GAGAL] Tidak ditemukan data tersembunyi (marker tidak ada).")
        sys.exit(1)

    pos = idx + len(MAGIC)
    protected_flag = data[pos:pos + 1]
    pos += 1
    salt = data[pos:pos + SALT_LEN]
    pos += SALT_LEN
    token_len = struct.unpack(">I", data[pos:pos + 4])[0]
    pos += 4
    token = data[pos:pos + token_len]

    if protected_flag == b"\x01":
        password = getpass.getpass("Password enkripsi: ")
    else:
        print("[INFO] File ini tidak memakai password, langsung diekstrak.")
        password = NO_PASSWORD_DEFAULT

    key = derive_key(password, salt)
    try:
        plain_blob = Fernet(key).decrypt(token)
    except InvalidToken:
        print("[GAGAL] Password salah atau data korup.")
        sys.exit(1)

    restored = unpack_files(plain_blob, out_dir)
    print(f"[OK] {len(restored)} file berhasil diekstrak ke '{out_dir}':")
    for p in restored:
        print(f"     - {p}")


def main():
    parser = argparse.ArgumentParser(description="Sembunyikan/ekstrak file di dalam file lain.")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_hide = sub.add_parser("hide", help="Sembunyikan file ke dalam cover file")
    p_hide.add_argument("-c", "--cover", required=True, help="File cover (mis. foto.jpg)")
    p_hide.add_argument("-s", "--secret", required=True, nargs="+", help="Satu/lebih file yang disembunyikan")
    p_hide.add_argument("-o", "--output", required=True, help="Nama file hasil")

    p_hide.add_argument("-p", "--password", action="store_true",
                         help="Aktifkan proteksi password (jika tidak diberikan, file tidak dienkripsi password)")

    p_ext = sub.add_parser("extract", help="Ekstrak file tersembunyi")
    p_ext.add_argument("-i", "--input", required=True, help="File yang berisi data tersembunyi")
    p_ext.add_argument("-o", "--output", required=True, help="Folder tujuan hasil ekstrak")

    args = parser.parse_args()

    if args.mode == "hide":
        if args.password:
            password = getpass.getpass("Password enkripsi: ")
            confirm = getpass.getpass("Konfirmasi password: ")
            if password != confirm:
                print("[GAGAL] Password tidak sama.")
                sys.exit(1)
        else:
            password = NO_PASSWORD_DEFAULT
            print("[INFO] Tidak menggunakan password, file akan disembunyikan tanpa proteksi tambahan.")
        hide(args.cover, args.secret, args.output, password)
    elif args.mode == "extract":
        extract(args.input, args.output)


if __name__ == "__main__":
    main()