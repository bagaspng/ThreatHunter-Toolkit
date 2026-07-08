import base64
import random

def _make_tables():
    table = list(range(256))
    random.shuffle(table)
    inverse = [0] * 256
    for original, substituted in enumerate(table):
        inverse[substituted] = original
    return table, inverse

def encode(text):
    table, inverse = _make_tables()
    data = text.encode("utf-8")
    substituted = bytes(table[b] for b in data)
    payload_b64 = base64.b64encode(substituted).decode("ascii")
    inverse_b64 = base64.b64encode(bytes(inverse)).decode("ascii")
    return payload_b64, inverse_b64

def decode(payload_b64, inverse_b64):
    inverse = base64.b64decode(inverse_b64)
    raw = base64.b64decode(payload_b64)
    original = bytes(inverse[b] for b in raw)
    return original.decode("utf-8")

def js_decoder_function(fn_name):
    return (
        "function " + fn_name + "(b64,invB64){"
        "var inv=atob(invB64);"
        "var raw=atob(b64);"
        "var out=new Uint8Array(raw.length);"
        "for(var i=0;i<raw.length;i++){"
        "out[i]=inv.charCodeAt(raw.charCodeAt(i));"
        "}"
        "return new TextDecoder('utf-8').decode(out);"
        "}"
    )
