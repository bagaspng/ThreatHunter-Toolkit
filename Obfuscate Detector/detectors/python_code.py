import ast

from detectors.base import Finding, register


def _func_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _func_name(node.value)
        return "%s.%s" % (base, node.attr) if base else node.attr
    return ""


def _arg_call_names(call):
    """Short call names appearing anywhere inside a call's arguments."""
    names = set()
    for arg in call.args:
        for n in ast.walk(arg):
            if isinstance(n, ast.Call):
                fn = _func_name(n.func)
                if fn:
                    names.add(fn)
    dotted = set(names)
    short = {n.rsplit(".", 1)[-1] for n in names}
    return dotted, short


def _add(out, name, conf, evidence, clue):
    out.append(Finding(name=name, category="python", confidence=conf,
                       evidence=evidence, clue=clue))


@register
def detect_python(text):
    text = text or ""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []

    out = []
    seen = set()

    def once(name):
        if name in seen:
            return False
        seen.add(name)
        return True

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        short = _func_name(node.func).rsplit(".", 1)[-1]

        if short in {"exec", "eval"}:
            dotted, arg = _arg_call_names(node)
            if "loads" in arg and any("marshal" in n for n in dotted) \
                    and once("python_marshal_exec"):
                _add(out, "python_marshal_exec", 90,
                     "exec/eval atas marshal.loads(...)",
                     "Kode ini menjalankan perintah tersembunyi dalam bentuk "
                     "'bytecode' Python. Jangan dijalankan. Untuk memeriksanya, "
                     "tampilkan isinya (bukan menjalankannya) di lingkungan "
                     "terpisah/sandbox.")
            if "compile" in arg and once("python_eval_compile"):
                _add(out, "python_eval_compile", 80,
                     "exec/eval atas compile(...)",
                     "Kode ini menyusun lalu menjalankan perintah saat "
                     "program berjalan. Tampilkan dulu isi perintahnya, jangan "
                     "langsung dijalankan.")
            if ("b64decode" in arg or "a85decode" in arg) and \
                    "decompress" in arg and once("python_b64_zlib_exec"):
                _add(out, "python_b64_zlib_exec", 85,
                     "rantai exec/eval + base64 decode + zlib decompress",
                     "Kode ini menyembunyikan perintah dengan cara "
                     "memadatkan + menyandikannya, lalu menjalankannya. "
                     "Berhenti sebelum bagian 'jalankan': buka/decode dan "
                     "buka pemadatannya untuk dibaca. Jangan dieksekusi.")

        if short == "join" and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Constant) \
                and isinstance(node.func.value.value, str):
            _, arg = _arg_call_names(node)
            if "chr" in arg and once("python_chr_join"):
                _add(out, "python_chr_join", 65,
                     "pola ''.join(chr(...)) untuk membangun string",
                     "Teks di kode ini dirakit dari kode angka setiap huruf "
                     "agar tersembunyi. Ubah angka-angka itu kembali menjadi "
                     "huruf untuk membacanya.")

    return out
