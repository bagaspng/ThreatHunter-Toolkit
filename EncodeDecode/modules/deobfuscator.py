from modules import obfuscator


def caesar_decode(text, shift):
    """Reverse a Caesar cipher by shifting in the opposite direction."""
    return obfuscator.caesar_cipher(text, -shift)


def rot13_decode(text):
    """ROT13 is symmetric, so decoding equals encoding."""
    return obfuscator.rot13(text)


def reverse_restore(text):
    """Reversing a reversed string restores the original."""
    return obfuscator.reverse_string(text)


def xor_decode(hex_text, key):
    """Reverse XOR encoding given the hex output and the original key."""
    key_bytes = key.encode("utf-8")
    data = bytes.fromhex(hex_text.strip())
    decoded = bytes(
        byte ^ key_bytes[i % len(key_bytes)] for i, byte in enumerate(data)
    )
    return decoded.decode("utf-8")


def rail_fence_decode(text, rails=2):
    """Reverse the Rail Fence cipher.

    Rebuilds the zig-zag pattern, distributes characters onto the rails,
    then reads them off following the same zig-zag path.
    """
    if rails < 2:
        return text

    # Step 1: mark the rail index each position belongs to.
    pattern = []
    rail = 0
    direction = 1
    for _ in text:
        pattern.append(rail)
        rail += direction
        if rail == 0 or rail == rails - 1:
            direction *= -1

    # Step 2: count characters per rail and slice them from the input.
    counts = [pattern.count(r) for r in range(rails)]
    rows = []
    position = 0
    for count in counts:
        rows.append(list(text[position:position + count]))
        position += count

    # Step 3: read characters back following the zig-zag order.
    indices = [0] * rails
    result = []
    for rail in pattern:
        result.append(rows[rail][indices[rail]])
        indices[rail] += 1
    return "".join(result)


def vigenere_decode(text, key):
    """Reverse the Vigenere cipher using the same key."""
    result = []
    key = key.upper()
    key_index = 0
    for char in text:
        if char.isalpha():
            shift = ord(key[key_index % len(key)]) - 65
            base = 65 if char.isupper() else 97
            result.append(chr((ord(char) - base - shift) % 26 + base))
            key_index += 1
        else:
            result.append(char)
    return "".join(result)


def atbash_decode(text):
    """Atbash is symmetric, so decoding equals encoding."""
    return obfuscator.atbash_cipher(text)
