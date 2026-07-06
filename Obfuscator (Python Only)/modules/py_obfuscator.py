import base64
import marshal
import random
import zlib

MIN_LAYERS = 1
MAX_LAYERS = 5

def _rand_name():
    return "_0x" + "".join(random.choice("0123456789abcdef") for _ in range(8))

def _wrap_once(source, filename="<obfuscated>"):
    code_obj = compile(source, filename, "exec")
    blob = marshal.dumps(code_obj)
    packed = base64.b64encode(zlib.compress(blob, 9)).decode("ascii")

    b = _rand_name()
    m = _rand_name()
    z = _rand_name()
    data = _rand_name()
    return (
        "import base64 as %s,marshal as %s,zlib as %s\n"
        "%s=%r\n"
        "exec(%s.loads(%s.decompress(%s.b64decode(%s))))\n"
        % (b, m, z, data, packed, m, z, b, data)
    )

def obfuscate_python(source, layers=2):
    if not source.strip():
        raise ValueError("Input kosong")

    layers = max(MIN_LAYERS, min(MAX_LAYERS, int(layers)))

    result = source
    for _ in range(layers):
        result = _wrap_once(result)

    header = (
        "# -*- coding: utf-8 -*-\n"
        "# Obfuscated with Python Encoder Security Toolkit (py_obfuscator).\n"
        "# Catatan: butuh versi CPython yang sama dengan saat obfuscate.\n"
    )
    return header + result
