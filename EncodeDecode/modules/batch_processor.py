from modules import encoder
from modules import decoder


# Method name -> encode function.
ENCODE_METHODS = {
    "base64": encoder.to_base64,
    "base32": encoder.to_base32,
    "hex": encoder.to_hex,
    "binary": encoder.to_binary,
    "url": encoder.to_url,
    "ascii": encoder.to_ascii,
}

# Method name -> decode function.
DECODE_METHODS = {
    "base64": decoder.from_base64,
    "base32": decoder.from_base32,
    "hex": decoder.from_hex,
    "binary": decoder.from_binary,
    "url": decoder.from_url,
    "ascii": decoder.from_ascii,
}


def batch_process(lines, func):
    """Run `func` over each line, returning (line, result) tuples.

    If a line fails, its result is an "Error: ..." string so one bad
    line does not abort the whole batch.
    """
    results = []
    for line in lines:
        try:
            results.append((line, func(line)))
        except Exception as e:
            results.append((line, f"Error: {e}"))
    return results


def batch_encode(lines, method):
    """Encode every line using the named method."""
    func = ENCODE_METHODS[method]
    return batch_process(lines, func)


def batch_decode(lines, method):
    """Decode every line using the named method."""
    func = DECODE_METHODS[method]
    return batch_process(lines, func)
