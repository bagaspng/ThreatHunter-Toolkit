from modules import encoder
from modules import decoder

ENCODE_METHODS = {
    "base64": encoder.to_base64,
    "base32": encoder.to_base32,
    "hex": encoder.to_hex,
    "binary": encoder.to_binary,
    "url": encoder.to_url,
    "ascii": encoder.to_ascii,
}

DECODE_METHODS = {
    "base64": decoder.from_base64,
    "base32": decoder.from_base32,
    "hex": decoder.from_hex,
    "binary": decoder.from_binary,
    "url": decoder.from_url,
    "ascii": decoder.from_ascii,
}

def batch_process(lines, func):
    results = []
    for line in lines:
        try:
            results.append((line, func(line)))
        except Exception as e:
            results.append((line, f"Error: {e}"))
    return results

def batch_encode(lines, method):
    func = ENCODE_METHODS[method]
    return batch_process(lines, func)

def batch_decode(lines, method):
    func = DECODE_METHODS[method]
    return batch_process(lines, func)
