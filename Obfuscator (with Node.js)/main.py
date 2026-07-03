from modules import encoder
from modules import decoder
from modules import hasher
from modules import detector
from modules import batch_processor
from modules import file_handler
from modules import utils
from modules import js_engine
from modules import css_obfuscator
# html_obfuscator di-import lazy di dalam menu karena butuh bs4/lxml,
# supaya fitur lain tetap jalan meski dependency itu belum terpasang.

def encode_menu():
    options = [
        "Base64", "Base32", "Hexadecimal", "Binary",
        "URL Encoding", "Unicode Escape", "ASCII Encoding", "Kembali",
    ]
    actions = {
        "1": encoder.to_base64,
        "2": encoder.to_base32,
        "3": encoder.to_hex,
        "4": encoder.to_binary,
        "5": encoder.to_url,
        "6": encoder.to_unicode_escape,
        "7": encoder.to_ascii,
    }

    while True:
        utils.print_menu("MENU ENCODE", options)
        choice = input("\nPilih: ").strip()
        if choice == "8":
            return
        if choice not in actions:
            print("Pilihan tidak valid.")
            utils.pause()
            continue
        try:
            text = utils.get_text_source()
            print("\nHasil:", actions[choice](text))
        except Exception as e:
            print("Error:", e)
        utils.pause()

def decode_menu():
    options = [
        "Base64", "Base32", "Hexadecimal", "Binary",
        "URL Decode", "Unicode Escape", "ASCII Decode", "Kembali",
    ]
    actions = {
        "1": decoder.from_base64,
        "2": decoder.from_base32,
        "3": decoder.from_hex,
        "4": decoder.from_binary,
        "5": decoder.from_url,
        "6": decoder.from_unicode_escape,
        "7": decoder.from_ascii,
    }

    while True:
        utils.print_menu("MENU DECODE", options)
        choice = input("\nPilih: ").strip()
        if choice == "8":
            return
        if choice not in actions:
            print("Pilihan tidak valid.")
            utils.pause()
            continue
        try:
            text = utils.get_text_source()
            print("\nHasil:", actions[choice](text))
        except Exception as e:
            print("Error:", e)
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
    filename = input("\nMasukkan nama file: ").strip()
    return file_handler.read_file(filename)


def _write_or_show(result, extra=None):
    output = input("\nSimpan ke file? (kosongkan untuk tampilkan): ").strip()
    if output:
        file_handler.write_file(output, result)
        print(f"Tersimpan: {output}")
        if extra:
            print(extra)
    else:
        print("\n=== HASIL ===\n")
        print(result)


def file_obfuscate_menu():
    options = [
        "Obfuscate HTML (hybrid)", "Obfuscate JavaScript",
        "Obfuscate CSS", "Kembali",
    ]

    while True:
        utils.print_menu("OBFUSCATE FILE WEB (HTML/CSS/JS)", options)
        choice = input("\nPilih: ").strip()
        if choice == "4":
            return
        if choice not in ("1", "2", "3"):
            print("Pilihan tidak valid.")
            utils.pause()
            continue

        # HTML & JS butuh Node.js + javascript-obfuscator.
        html_obfuscator = None
        if choice in ("1", "2"):
            ok, msg = js_engine.check_dependencies()
            if not ok:
                print("\nDependency belum lengkap:\n" + msg)
                utils.pause()
                continue
        if choice == "1":
            try:
                from modules import html_obfuscator
                from modules import verifier
            except ImportError:
                print("\nFitur HTML butuh 'beautifulsoup4' dan 'lxml'.")
                print("Install dulu: pip install -r requirements.txt")
                utils.pause()
                continue

        try:
            code = _read_code_source()

            if choice == "1":
                # Ala phpkobo: tanpa opsi. Pipeline: inline JS -> cipher ->
                # zero-width delimiter -> loader -> lapis luar obfuscator.
                result, rendered = html_obfuscator.build(code)
                ok, vmsg = verifier.verify(result, rendered)
                print(("\n[verify] OK " if ok else "\n[verify] WARN ") + vmsg)
                _write_or_show(result)
            elif choice == "2":
                result = js_engine.obfuscate(code)
                _write_or_show(result)
            else:
                result, mapping = css_obfuscator.obfuscate_css(code)
                import json
                mapping_text = json.dumps(mapping, indent=2, ensure_ascii=False)
                print("\nMapping class/id:\n" + mapping_text)
                _write_or_show(result)
        except Exception as e:
            print("Error:", e)
        utils.pause()


def main():
    menu_actions = {
        "1": encode_menu,
        "2": decode_menu,
        "3": hash_menu,
        "4": detect_menu,
        "5": batch_menu,
        "6": file_obfuscate_menu,
    }

    while True:
        utils.print_header("PYTHON ENCODER SECURITY TOOLKIT")
        print("\n1. Encode")
        print("2. Decode")
        print("3. Hashing")
        print("4. Deteksi Encoding")
        print("5. Batch Processing")
        print("6. Obfuscate File Web (HTML/CSS/JS)")
        print("7. Keluar")
        choice = input("\nPilih: ").strip()

        if choice == "7":
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
