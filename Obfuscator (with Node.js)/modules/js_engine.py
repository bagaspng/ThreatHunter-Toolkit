"""Wrapper subprocess untuk `javascript-obfuscator` (Node.js).

Python berperan sebagai orchestrator; obfuscation JS yang sebenarnya
didelegasikan ke tool `javascript-obfuscator` (Node.js) lewat subprocess.

Alur `obfuscate()`:
  1. Tulis kode JS ke file temporary.
  2. Panggil CLI `javascript-obfuscator` dengan preset opsi tetap
     (stringArray, controlFlowFlattening, selfDefending, dll).
  3. Baca hasil dari file output, hapus semua file temporary.

Sesuai keluhan pengguna, TIDAK ada opsi level/intensitas yang diekspos —
seperti phpkobo, obfuscation berjalan dengan satu preset tetap.
"""

import os
import shutil
import subprocess
import tempfile

# Direktori root project (tempat package.json / node_modules berada).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BINARY_NAME = "javascript-obfuscator"

# Preset opsi tetap (tanpa level). Nilai boolean dikirim sebagai string
# "true"/"false" sesuai format CLI javascript-obfuscator.
_PRESET = [
    "--compact", "true",
    "--control-flow-flattening", "true",
    "--control-flow-flattening-threshold", "0.75",
    "--self-defending", "true",
    "--string-array", "true",
    "--string-array-encoding", "base64",
    "--string-array-threshold", "1",
    "--string-array-rotate", "true",
    "--string-array-shuffle", "true",
    "--numbers-to-expressions", "true",
    "--simplify", "true",
]

INSTALL_HINT = (
    "javascript-obfuscator tidak ditemukan.\n"
    "Install dulu (butuh Node.js + npm):\n"
    "  # lokal di folder project (disarankan):\n"
    "  npm install javascript-obfuscator\n"
    "  # atau global:\n"
    "  npm install -g javascript-obfuscator\n"
)


def _node_available():
    return shutil.which("node") is not None


def find_binary():
    """Cari executable javascript-obfuscator.

    Urutan: variabel env override -> PATH -> node_modules/.bin lokal project.
    Return path (str) atau None kalau tidak ketemu.
    """
    override = os.environ.get("JS_OBFUSCATOR_BIN")
    if override and os.path.exists(override):
        return override

    on_path = shutil.which(BINARY_NAME)
    if on_path:
        return on_path

    local = os.path.join(PROJECT_ROOT, "node_modules", ".bin", BINARY_NAME)
    if os.path.exists(local):
        return local
    return None


def is_available():
    return _node_available() and find_binary() is not None


def check_dependencies():
    """Validasi node + javascript-obfuscator terpasang.

    Return (ok: bool, message: str). message berisi instruksi kalau ada
    yang kurang.
    """
    problems = []
    if not _node_available():
        problems.append(
            "Node.js (perintah `node`) tidak ada di PATH.\n"
            "Install dari https://nodejs.org/ lalu coba lagi."
        )
    if find_binary() is None:
        problems.append(INSTALL_HINT)

    if problems:
        return False, "\n".join(problems)
    return True, "OK: node + javascript-obfuscator terdeteksi."


def obfuscate(code):
    """Obfuscate satu blok kode JS lewat subprocess javascript-obfuscator.

    Raise RuntimeError kalau dependency belum ada atau proses gagal.
    """
    binary = find_binary()
    if not _node_available() or binary is None:
        raise RuntimeError(INSTALL_HINT)

    tmpdir = tempfile.mkdtemp(prefix="jsobf_")
    in_path = os.path.join(tmpdir, "in.js")
    out_path = os.path.join(tmpdir, "out.js")
    try:
        with open(in_path, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = [binary, in_path, "--output", out_path] + _PRESET
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "javascript-obfuscator gagal (exit %d):\n%s"
                % (proc.returncode, proc.stderr.strip() or proc.stdout.strip())
            )
        with open(out_path, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
