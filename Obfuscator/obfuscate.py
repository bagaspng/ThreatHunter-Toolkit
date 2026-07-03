import argparse
import json
import os
import sys

from modules import css_obfuscator
from modules import js_engine

def detect_type(path, forced, content):
    if forced != "auto":
        return forced
    if path:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".js":
            return "js"
        if ext == ".css":
            return "css"
        if ext in (".html", ".htm"):
            return "html"
    low = content.lower()
    if "<html" in low or "<script" in low or "<style" in low \
            or content.lstrip().startswith("<"):
        return "html"
    return "html"

def read_input(args):
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            return f.read()
    if sys.stdin.isatty():
        print("Tempel kode, lalu tekan Ctrl+D (EOF) untuk selesai:",
              file=sys.stderr)
    return sys.stdin.read()

def check_dependencies(need_html=False):
    ok, msg = js_engine.check_dependencies()
    if not ok:
        return False, msg
    if need_html:
        try:
            import bs4
            import lxml
        except ImportError:
            return False, (
                "Mode HTML butuh 'beautifulsoup4' + 'lxml'.\n"
                "Install: pip install -r requirements.txt"
            )
    return True, msg

def build_parser():
    p = argparse.ArgumentParser(
        prog="obfuscate.py",
        description="Obfuscate file HTML/CSS/JS (Python + javascript-obfuscator).",
    )
    p.add_argument("--input", "-i", help="File input. Kalau kosong, baca stdin.")
    p.add_argument("--output", "-o", help="File output. Kalau kosong, cetak ke stdout.")
    p.add_argument("--type", "-t", choices=["auto", "html", "js", "css"],
                   default="auto",
                   help="Paksa tipe input (default: auto dari ekstensi).")
    p.add_argument("--map-output",
                   help="Path file JSON mapping untuk mode CSS.")
    p.add_argument("--no-verify", action="store_true",
                   help="Lewati verifikasi jsdom untuk mode HTML.")
    return p

def _run_html(content, args):
    from modules import html_obfuscator
    from modules import verifier

    final, rendered = html_obfuscator.build(content)
    if not args.no_verify:
        ok, msg = verifier.verify(final, rendered)
        prefix = "[verify] " + ("OK " if ok else "WARN ")
        print(prefix + msg, file=sys.stderr)
    return final

def main(argv=None):
    args = build_parser().parse_args(argv)
    content = read_input(args)
    if not content.strip():
        print("Error: input kosong.", file=sys.stderr)
        return 1

    ftype = detect_type(args.input, args.type, content)

    if ftype in ("html", "js"):
        ok, msg = check_dependencies(need_html=(ftype == "html"))
        if not ok:
            print("Dependency belum lengkap:\n" + msg, file=sys.stderr)
            return 2

    map_path = None
    if ftype == "js":
        result = js_engine.obfuscate(content)
    elif ftype == "css":
        result, mapping = css_obfuscator.obfuscate_css(content)
        map_path = args.map_output
        if map_path is None and args.output:
            map_path = args.output + ".map.json"
        if map_path:
            with open(map_path, "w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2, ensure_ascii=False)
        elif mapping:
            print("Mapping class/id:", file=sys.stderr)
            print(json.dumps(mapping, indent=2, ensure_ascii=False),
                  file=sys.stderr)
    else:
        result = _run_html(content, args)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print("Tersimpan: %s" % args.output, file=sys.stderr)
        if map_path:
            print("Mapping  : %s" % map_path, file=sys.stderr)
    else:
        sys.stdout.write(result)
        if not result.endswith("\n"):
            sys.stdout.write("\n")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nDihentikan.", file=sys.stderr)
        sys.exit(130)
    except RuntimeError as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)
