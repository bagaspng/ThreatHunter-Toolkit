#!/usr/bin/env python3
"""CLI: pindai file atau folder untuk obfuscate, keluarkan table/JSON/CSV.

Clue-only: tidak pernah menampilkan hasil decode payload.
Contoh:
    python detect.py suspicious.js
    python detect.py ./samples --format csv
    python detect.py ./repo --fail-on-detect     # exit 1 bila ada temuan (CI)
"""
import argparse
import csv
import io
import json
import os
import sys

import engine

_MAX_BYTES = 1_000_000
_SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".pdf", ".zip",
             ".gz", ".xz", ".bz2", ".7z", ".rar", ".exe", ".dll", ".so",
             ".dylib", ".pyc", ".o", ".class", ".woff", ".woff2", ".ttf"}


def iter_files(path):
    if os.path.isfile(path):
        yield path
        return
    for root, _, names in os.walk(path):
        for n in sorted(names):
            yield os.path.join(root, n)


def scan_path(path):
    """Analyze every readable text file under path; return list of results."""
    out = []
    for fp in iter_files(path):
        if os.path.splitext(fp)[1].lower() in _SKIP_EXT:
            continue
        try:
            with open(fp, "rb") as fh:
                data = fh.read(_MAX_BYTES + 1)
        except OSError:
            continue
        if len(data) > _MAX_BYTES:
            continue
        res = engine.analyze(data.decode("utf-8", "replace"))
        out.append({"file": fp, "verdict": res["verdict"],
                    "findings": res["findings"]})
    return out


def to_csv(results):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "obfuscated", "risk", "score", "dominant", "signals"])
    for r in results:
        v = r["verdict"]
        w.writerow([r["file"], v["obfuscated"], v["risk"], v["score"],
                    v["dominant"], v["signals"]])
    return buf.getvalue()


def to_table(results):
    lines = []
    for r in results:
        v = r["verdict"]
        flag = "OBF" if v["obfuscated"] else " - "
        lines.append("[%s] risk=%3d  %-20s  %s"
                     % (flag, v["risk"], v["dominant"] or "-", r["file"]))
    n_obf = sum(1 for r in results if r["verdict"]["obfuscated"])
    lines.append("--- %d file dipindai, %d obfuscated ---"
                 % (len(results), n_obf))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Deteksi obfuscate (clue-only, zero-decode).")
    ap.add_argument("path", help="file atau folder yang dipindai")
    ap.add_argument("--format", choices=["table", "json", "csv"],
                    default="table")
    ap.add_argument("--fail-on-detect", action="store_true",
                    help="exit code 1 bila ada file terdeteksi obfuscate")
    args = ap.parse_args(argv)

    if not os.path.exists(args.path):
        print("path tidak ada: %s" % args.path, file=sys.stderr)
        return 2

    results = scan_path(args.path)
    if args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif args.format == "csv":
        sys.stdout.write(to_csv(results))
    else:
        print(to_table(results))

    if args.fail_on_detect and any(
            r["verdict"]["obfuscated"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
