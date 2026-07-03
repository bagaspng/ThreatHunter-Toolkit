"""Wrapper Python untuk verifikasi jsdom (modules/verify.js).

Menjalankan loader hasil obfuscation di sandbox jsdom (Node subprocess) dan
memastikan output decode runtime identik dengan dokumen asli yang di-encode.
"""

import os
import subprocess
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY_JS = os.path.join(PROJECT_ROOT, "modules", "verify.js")


def jsdom_available():
    try:
        proc = subprocess.run(
            ["node", "-e", "require('jsdom')"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        return proc.returncode == 0
    except FileNotFoundError:
        return False


def verify(final_html, expected_rendered):
    """Return (ok: bool, message: str).

    ok=True hanya jika loader men-decode kembali persis `expected_rendered`.
    """
    if not jsdom_available():
        return False, (
            "jsdom belum terpasang, verifikasi dilewati.\n"
            "Install: npm install jsdom"
        )

    tmpdir = tempfile.mkdtemp(prefix="verify_")
    out_path = os.path.join(tmpdir, "out.html")
    exp_path = os.path.join(tmpdir, "expected.txt")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final_html)
        with open(exp_path, "w", encoding="utf-8") as f:
            f.write(expected_rendered)

        proc = subprocess.run(
            ["node", VERIFY_JS, out_path, exp_path],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        if proc.returncode == 0:
            return True, "Verifikasi OK: decode runtime identik dengan input."
        msg = (proc.stderr.strip() or proc.stdout.strip()
               or "verifikasi gagal")
        return False, msg
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
