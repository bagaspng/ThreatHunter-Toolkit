import os

from modules import file_handler


def clear_screen():
    """Clear the terminal screen (cross-platform)."""
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    """Pause execution until the user presses Enter."""
    input("\nTekan Enter untuk melanjutkan...")


def print_header(title):
    """Print a formatted section header."""
    print("=" * 33)
    print(title.center(33))
    print("=" * 33)


def get_input(prompt="Enter text: "):
    """Read a single line of text from the user.

    Raises ValueError when the input is empty so callers can report a
    consistent "Empty input" error.
    """
    text = input(prompt)
    if text == "":
        raise ValueError("Input kosong")
    return text


def get_multiline(prompt="Masukkan baris (baris kosong untuk selesai):"):
    """Read multiple lines until an empty line is entered.

    Returns a list of non-empty lines.
    """
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


def get_text_source():
    """Ask the user whether to read text manually or from a file.

    Used by the Encode, Decode, and Obfuscation menus to support file
    input. Returns the resulting text string.
    """
    print("\nSumber input:")
    print("1. Input Teks Manual")
    print("2. Baca Dari File")
    choice = input("Pilih: ").strip()

    if choice == "2":
        filename = input("Masukkan nama file: ").strip()
        data = file_handler.read_file(filename)
        # Strip a single trailing newline that files commonly end with.
        return data.rstrip("\n")
    return get_input("Masukkan teks: ")


def print_menu(title, options):
    """Print a numbered menu given a title and a list of option labels."""
    print(f"\n=== {title} ===\n")
    for index, label in enumerate(options, start=1):
        print(f"{index}. {label}")
