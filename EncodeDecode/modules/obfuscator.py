import codecs


def caesar_cipher(text, shift):
    """Shift each letter forward by `shift` positions (wrapping A-Z/a-z).

    Non-letter characters are left unchanged.
    """
    result = []
    for char in text:
        if char.isupper():
            result.append(chr((ord(char) - 65 + shift) % 26 + 65))
        elif char.islower():
            result.append(chr((ord(char) - 97 + shift) % 26 + 97))
        else:
            result.append(char)
    return "".join(result)


def rot13(text):
    """Apply the ROT13 substitution cipher."""
    return codecs.encode(text, "rot_13")


def reverse_string(text):
    """Reverse the order of characters in the text."""
    return text[::-1]


def xor_encode(text, key):
    """XOR each character with a repeating key, returning a hex string."""
    key_bytes = key.encode("utf-8")
    data = text.encode("utf-8")
    encoded = bytes(
        byte ^ key_bytes[i % len(key_bytes)] for i, byte in enumerate(data)
    )
    return encoded.hex()


def rail_fence(text, rails=2):
    """Encrypt text using the zig-zag Rail Fence cipher.

    Example: "HELLO" with 2 rails -> "HLOEL"
    """
    if rails < 2:
        return text

    fence = [[] for _ in range(rails)]
    rail = 0
    direction = 1
    for char in text:
        fence[rail].append(char)
        rail += direction
        if rail == 0 or rail == rails - 1:
            direction *= -1
    return "".join("".join(row) for row in fence)


def vigenere_cipher(text, key):
    """Encrypt text with the Vigenere cipher.

    Only alphabetic characters are shifted; others pass through and do
    not consume a key character. Example: "HELLO" + "KEY" -> "RIJVS".
    """
    result = []
    key = key.upper()
    key_index = 0
    for char in text:
        if char.isalpha():
            shift = ord(key[key_index % len(key)]) - 65
            base = 65 if char.isupper() else 97
            result.append(chr((ord(char) - base + shift) % 26 + base))
            key_index += 1
        else:
            result.append(char)
    return "".join(result)


def atbash_cipher(text):
    """Apply the Atbash cipher (A<->Z, B<->Y, ...).

    Example: "HELLO" -> "SVOOL"
    """
    result = []
    for char in text:
        if char.isupper():
            result.append(chr(90 - (ord(char) - 65)))
        elif char.islower():
            result.append(chr(122 - (ord(char) - 97)))
        else:
            result.append(char)
    return "".join(result)
