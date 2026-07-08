import os

from modules import file_handler

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def pause():
    input("\nTekan Enter untuk melanjutkan...")

def print_header(title):
    print("=" * 33)
    print(title.center(33))
    print("=" * 33)

def get_input(prompt="Enter text: "):
    text = input(prompt)
    if text == "":
        raise ValueError("Input kosong")
    return text

def get_multiline(prompt="Masukkan baris (baris kosong untuk selesai):"):
    print(prompt)
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    if not lines:
        raise ValueError("Input kosong")
    return lines

def get_pasted_code(end_marker="EOF"):
    print(
        f"\nTempel (paste) kode di bawah ini.\n"
        f"Setelah selesai, ketik '{end_marker}' di baris baru lalu Enter "
        f"(atau tekan Ctrl+D):"
    )
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == end_marker:
            break
        lines.append(line)
    code = "\n".join(lines)
    if not code.strip():
        raise ValueError("Input kosong")
    return code

def get_text_source():
    print("\nSumber input:")
    print("1. Input Teks Manual")
    print("2. Baca Dari File")
    choice = input("Pilih: ").strip()
    if choice == "2":
        filename = input("Masukkan nama file: ").strip()
        data = file_handler.read_file(filename)
        return data.rstrip("\n")
    return get_input("Masukkan teks: ")

def print_menu(title, options):
    print(f"\n=== {title} ===\n")
    for index, label in enumerate(options, start=1):
        print(f"{index}. {label}")
