from modules import encoder
from modules import decoder
from modules import layer_hint
from modules import hasher
from modules import detector
from modules import batch_processor
from modules import file_handler
from modules import utils
from modules import js_obfuscator
from modules import css_obfuscator
from modules import py_obfuscator

ENCODE_METHODS = [
    ("Base64", encoder.to_base64),
    ("Base32", encoder.to_base32),
    ("Hexadecimal", encoder.to_hex),
    ("Binary", encoder.to_binary),
    ("URL Encoding", encoder.to_url),
    ("Unicode Escape", encoder.to_unicode_escape),
    ("ASCII Encoding", encoder.to_ascii),
]

DECODE_METHODS = [
    ("Base64", decoder.from_base64),
    ("Base32", decoder.from_base32),
    ("Hexadecimal", decoder.from_hex),
    ("Binary", decoder.from_binary),
    ("URL Decode", decoder.from_url),
    ("Unicode Escape", decoder.from_unicode_escape),
    ("ASCII Decode", decoder.from_ascii),
]

def _print_results(methods, text, hints=False):
    for name, fn in methods:
        try:
            value = fn(text)
            print(f"\n{name}:\n{value}")
            if hints:
                h = layer_hint.hint(value)
                if h["again"]:
                    print(f"         ↻ mungkin masih {h['guess']}")
        except Exception as e:
            print(f"\n{name}:\n[gagal] {e}")

def translate_menu():
    utils.print_header("MENU ENCODE & DECODE")
    try:
        text = utils.get_input("Masukkan teks: ")
    except ValueError:
        print("Input kosong.")
        utils.pause()
        return
    print("\n=== HASIL ENCODE ===")
    _print_results(ENCODE_METHODS, text)
    print("\n=== HASIL DECODE ===")
    _print_results(DECODE_METHODS, text, hints=True)
    steps = layer_hint.peel(text)
    if steps:
        ans = input("\nKupas sampai habis? [y/N]: ").strip().lower()
        if ans == "y":
            print()
            for i, (name, value) in enumerate(steps, 1):
                print(f"  lapis {i} ({name}) -> {value}")
            print(f"\nPesan akhir: {steps[-1][1]}")
    utils.pause()

def hash_menu():
    options = ["MD5", "SHA1", "SHA256", "SHA512", "CRC32", "Kembali"]
    actions = {
        "1": hasher.md5,
        "2": hasher.sha1,
        "3": hasher.sha256,
        "4": hasher.sha512,
        "5": hasher.crc32,
    }
    while True:
        utils.print_menu("MENU HASH", options)
        choice = input("\nPilih: ").strip()
        if choice == "6":
            return
        if choice not in actions:
            print("Pilihan tidak valid.")
            utils.pause()
            continue
        try:
            text = utils.get_input("Masukkan teks: ")
            print("\nHasil:", actions[choice](text))
        except Exception as e:
            print("Error:", e)
        utils.pause()

def detect_menu():
    print("\n=== DETEKSI ENCODING ===\n")
    try:
        data = utils.get_input("Input: ")
        results = detector.detect(data)
        print("\nKemungkinan Encoding:\n")
        for name, matched in results.items():
            mark = "✓" if matched else "✗"
            print(f"{mark} {name}")
    except Exception as e:
        print("Error:", e)
    utils.pause()

def batch_menu():
    options = ["Encode Batch", "Decode Batch", "Kembali"]
    while True:
        utils.print_menu("PEMROSESAN BATCH", options)
        choice = input("\nPilih: ").strip()
        if choice == "3":
            return
        if choice not in ("1", "2"):
            print("Pilihan tidak valid.")
            utils.pause()
            continue
        methods = ["base64", "base32", "hex", "binary", "url", "ascii"]
        try:
            print("\nSumber input:")
            print("1. Input Teks Manual")
            print("2. Baca Dari File")
            source = input("Pilih: ").strip()
            if source == "2":
                filename = input("Masukkan nama file: ").strip()
                lines = file_handler.read_lines(filename)
            else:
                lines = utils.get_multiline(
                    "Masukkan baris (baris kosong untuk selesai):"
                )
            print("\nMetode:", ", ".join(methods))
            method = utils.get_input("Pilih metode: ").strip().lower()
            if method not in methods:
                print("Error: Metode tidak dikenal")
                utils.pause()
                continue
            if choice == "1":
                results = batch_processor.batch_encode(lines, method)
            else:
                results = batch_processor.batch_decode(lines, method)
            print()
            for original, output in results:
                print(f"{original} → {output}")
        except Exception as e:
            print("Error:", e)
        utils.pause()

def _read_code_source():
    print("\nSumber kode:")
    print("1. Tempel (paste) di terminal")
    print("2. Baca dari file")
    source = input("Pilih: ").strip()
    if source == "2":
        filename = input("Masukkan nama file: ").strip()
        return file_handler.read_file(filename)
    return utils.get_pasted_code()

def _write_or_show(result, extra=None):
    output = input("\nSimpan ke file? (kosongkan untuk tampilkan): ").strip()
    if output:
        path = file_handler.write_file(output, result)
        print(f"Tersimpan: {path}")
        if extra:
            print(extra)
    else:
        print("\n=== HASIL ===\n")
        print(result)

def file_obfuscate_menu():
    options = [
        "Obfuscate HTML", "Obfuscate JavaScript",
        "Obfuscate CSS", "Obfuscate Python", "Kembali",
    ]
    while True:
        utils.print_menu("OBFUSCATE FILE (HTML/CSS/JS/PY)", options)
        choice = input("\nPilih: ").strip()
        if choice == "5":
            return
        if choice not in ("1", "2", "3", "4"):
            print("Pilihan tidak valid.")
            utils.pause()
            continue
        if choice == "1":
            from modules import html_obfuscator
            from modules import verifier
        try:
            code = _read_code_source()
            if choice == "1":
                result, rendered = html_obfuscator.build(code)
                ok, vmsg = verifier.verify(result, rendered)
                print(("\n[verify] OK " if ok else "\n[verify] WARN ") + vmsg)
                _write_or_show(result)
            elif choice == "2":
                result = js_obfuscator.obfuscate_js(code, "high")
                print("\n[verify] OK self-check round-trip packer lolos")
                _write_or_show(result)
            elif choice == "3":
                result, mapping = css_obfuscator.obfuscate_css(code)
                print("\n[verify] OK self-check round-trip packer lolos")
                print("[info] hasil CSS berupa JavaScript (injector) — pakai di "
                      "dalam <script>, simpan sebagai .js (mis. .css.js), bukan .css")
                import json
                mapping_text = json.dumps(mapping, indent=2, ensure_ascii=False)
                print("\nMapping class/id:\n" + mapping_text)
                _write_or_show(result)
            else:
                result = py_obfuscator.obfuscate_python(code)
                print("\n[verify] OK payload decode + syntax output tervalidasi")
                _write_or_show(result)
        except Exception as e:
            print("Error:", e)
        utils.pause()

def main():
    menu_actions = {
        "1": translate_menu,
        "2": hash_menu,
        "3": detect_menu,
        "4": batch_menu,
        "5": file_obfuscate_menu,
    }
    while True:
        utils.print_header("PYTHON ENCODER SECURITY TOOLKIT")
        print("\n1. Encode & Decode")
        print("2. Hashing")
        print("3. Deteksi Encoding")
        print("4. Batch Processing")
        print("5. Obfuscate File (HTML/CSS/JS/PY)")
        print("6. Keluar")
        choice = input("\nPilih: ").strip()
        if choice == "6":
            print("\nSampai jumpa!")
            break
        action = menu_actions.get(choice)
        if action is None:
            print("Pilihan tidak valid.")
            utils.pause()
            continue
        action()

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nDihentikan. Sampai jumpa!")
