from modules import encoder
from modules import decoder
from modules import obfuscator
from modules import deobfuscator
from modules import hasher
from modules import web_security
from modules import detector
from modules import batch_processor
from modules import file_handler
from modules import utils

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

def obfuscate_menu():
    options = [
        "Caesar Cipher", "ROT13", "Reverse String", "XOR Encoding",
        "Rail Fence Cipher", "Vigenere Cipher", "Atbash Cipher", "Kembali",
    ]

    while True:
        utils.print_menu("MENU OBFUSCATION", options)
        choice = input("\nPilih: ").strip()
        if choice == "8":
            return
        try:
            if choice == "1":
                text = utils.get_text_source()
                shift = int(utils.get_input("Masukkan pergeseran: "))
                print("\nHasil:", obfuscator.caesar_cipher(text, shift))
            elif choice == "2":
                text = utils.get_text_source()
                print("\nHasil:", obfuscator.rot13(text))
            elif choice == "3":
                text = utils.get_text_source()
                print("\nHasil:", obfuscator.reverse_string(text))
            elif choice == "4":
                text = utils.get_text_source()
                key = utils.get_input("Masukkan kunci: ")
                print("\nHasil:", obfuscator.xor_encode(text, key))
            elif choice == "5":
                text = utils.get_text_source()
                rails = int(utils.get_input("Masukkan jumlah rel (default 2): "))
                print("\nHasil:", obfuscator.rail_fence(text, rails))
            elif choice == "6":
                text = utils.get_text_source()
                key = utils.get_input("Masukkan kunci: ")
                print("\nHasil:", obfuscator.vigenere_cipher(text, key))
            elif choice == "7":
                text = utils.get_text_source()
                print("\nHasil:", obfuscator.atbash_cipher(text))
            else:
                print("Pilihan tidak valid.")
        except Exception as e:
            print("Error:", e)
        utils.pause()

def deobfuscate_menu():
    options = [
        "Caesar Decode", "ROT13 Decode", "Reverse String Restore",
        "XOR Decode", "Rail Fence Decode", "Vigenere Decode",
        "Atbash Decode", "Kembali",
    ]

    while True:
        utils.print_menu("MENU DEOBFUSCATION", options)
        choice = input("\nPilih: ").strip()
        if choice == "8":
            return
        try:
            if choice == "1":
                text = utils.get_input("Masukkan teks: ")
                shift = int(utils.get_input("Masukkan pergeseran: "))
                print("\nHasil:", deobfuscator.caesar_decode(text, shift))
            elif choice == "2":
                text = utils.get_input("Masukkan teks: ")
                print("\nHasil:", deobfuscator.rot13_decode(text))
            elif choice == "3":
                text = utils.get_input("Masukkan teks: ")
                print("\nHasil:", deobfuscator.reverse_restore(text))
            elif choice == "4":
                text = utils.get_input("Masukkan teks hex: ")
                key = utils.get_input("Masukkan kunci: ")
                print("\nHasil:", deobfuscator.xor_decode(text, key))
            elif choice == "5":
                text = utils.get_input("Masukkan teks: ")
                rails = int(utils.get_input("Masukkan jumlah rel (default 2): "))
                print("\nHasil:", deobfuscator.rail_fence_decode(text, rails))
            elif choice == "6":
                text = utils.get_input("Masukkan teks: ")
                key = utils.get_input("Masukkan kunci: ")
                print("\nHasil:", deobfuscator.vigenere_decode(text, key))
            elif choice == "7":
                text = utils.get_input("Masukkan teks: ")
                print("\nHasil:", deobfuscator.atbash_decode(text))
            else:
                print("Pilihan tidak valid.")
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

def web_security_menu():
    options = [
        "URL Encode Payload", "HTML Escape", "Unicode Escape Payload",
        "Base64 Payload Wrapper", "JavaScript CharCode Obfuscator", "Kembali",
    ]
    actions = {
        "1": web_security.url_encode_payload,
        "2": web_security.html_escape,
        "3": web_security.unicode_escape_payload,
        "4": web_security.base64_wrapper,
        "5": web_security.js_charcode_obfuscator,
    }

    while True:
        utils.print_menu("MENU KEAMANAN WEB", options)
        choice = input("\nPilih: ").strip()
        if choice == "6":
            return
        if choice not in actions:
            print("Pilihan tidak valid.")
            utils.pause()
            continue
        try:
            payload = utils.get_input("Masukkan payload: ")
            print("\nHasil:", actions[choice](payload))
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

def main():
    menu_actions = {
        "1": encode_menu,
        "2": decode_menu,
        "3": obfuscate_menu,
        "4": deobfuscate_menu,
        "5": hash_menu,
        "6": web_security_menu,
        "7": detect_menu,
        "8": batch_menu,
    }

    while True:
        utils.print_header("PYTHON ENCODER SECURITY TOOLKIT")
        print("\n1. Encode")
        print("2. Decode")
        print("3. Obfuscate")
        print("4. Deobfuscate")
        print("5. Hashing")
        print("6. Web Security Payload Tools")
        print("7. Deteksi Encoding")
        print("8. Batch Processing")
        print("9. Keluar")
        choice = input("\nPilih: ").strip()

        if choice == "9":
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
