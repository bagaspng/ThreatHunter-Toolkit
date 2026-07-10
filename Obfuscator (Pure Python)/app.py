#!/usr/bin/env python3
"""Web API (Flask) untuk Obfuscator (Pure Python).

Entry point KETIGA — melengkapi:
  - main.py       : menu interaktif di terminal
  - obfuscate.py  : CLI non-interaktif
  - app.py (ini)  : Web API + halaman form, diakses lewat HTTP

app.py hanya "kulit" web; semua logika tetap memakai modul di folder modules/.
Halaman web ada di templates/index.html.

Menjalankan:
    python3 app.py
Lalu buka http://127.0.0.1:8000/ di browser.
"""

from flask import Flask, jsonify, request, render_template

from modules import encoder
from modules import decoder
from modules import js_obfuscator
from modules import css_obfuscator
from modules import py_obfuscator

app = Flask(__name__)

# --- Daftar metode: dipetakan sekali, dipakai ulang oleh endpoint ---------
ENCODE_METHODS = {
    "base64": encoder.to_base64,
    "base32": encoder.to_base32,
    "hex": encoder.to_hex,
    "binary": encoder.to_binary,
    "url": encoder.to_url,
    "unicode": encoder.to_unicode_escape,
    "ascii": encoder.to_ascii,
}

DECODE_METHODS = {
    "base64": decoder.from_base64,
    "base32": decoder.from_base32,
    "hex": decoder.from_hex,
    "binary": decoder.from_binary,
    "url": decoder.from_url,
    "unicode": decoder.from_unicode_escape,
    "ascii": decoder.from_ascii,
}


# --- Helper input: terima JSON, form biasa, atau upload file --------------
def get_payload(*keys):
    """Ambil teks dari body request.

    Prioritas: file yang di-upload -> JSON -> form biasa.
    `keys` adalah nama field yang dicari (mis. "text" atau "code").
    Mengembalikan (teks, nama_file) — nama_file bisa None.
    """
    # 1) Upload file (multipart/form-data, field bernama "file")
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            return f.read().decode("utf-8", errors="replace"), f.filename

    # 2) Body JSON
    if request.is_json:
        data = request.get_json(silent=True) or {}
        for k in keys:
            if data.get(k):
                return data[k], None

    # 3) Form biasa (application/x-www-form-urlencoded)
    for k in keys:
        if request.form.get(k):
            return request.form[k], None

    return None, None


def _run_methods(methods, text):
    """Jalankan semua metode; metode yang gagal ditandai, tidak meng-crash."""
    results = {}
    for name, fn in methods.items():
        try:
            results[name] = {"ok": True, "value": fn(text)}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}
    return results


# --- Endpoint API ---------------------------------------------------------
@app.route("/api/encode", methods=["POST"])
def api_encode():
    text, _ = get_payload("text", "code")
    if not text:
        return jsonify({"error": "Field 'text' kosong."}), 400
    return jsonify({"input": text, "results": _run_methods(ENCODE_METHODS, text)})


@app.route("/api/decode", methods=["POST"])
def api_decode():
    text, _ = get_payload("text", "code")
    if not text:
        return jsonify({"error": "Field 'text' kosong."}), 400
    return jsonify({"input": text, "results": _run_methods(DECODE_METHODS, text)})


@app.route("/api/translate", methods=["POST"])
def api_translate():
    """Encode DAN decode sekaligus dari satu input (gaya dencode)."""
    text, _ = get_payload("text", "code")
    if not text:
        return jsonify({"error": "Field 'text' kosong."}), 400
    return jsonify({
        "input": text,
        "encode": _run_methods(ENCODE_METHODS, text),
        "decode": _run_methods(DECODE_METHODS, text),
    })


def _detect_type(explicit, filename):
    """Tentukan tipe obfuscate dari field 'type' atau ekstensi file."""
    if explicit:
        return explicit.lower()
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        return {"htm": "html"}.get(ext, ext)
    return "py"


@app.route("/api/obfuscate", methods=["POST"])
def api_obfuscate():
    code, filename = get_payload("code", "text")
    if not code:
        return jsonify({"error": "Field 'code' kosong."}), 400

    explicit = None
    if request.is_json:
        explicit = (request.get_json(silent=True) or {}).get("type")
    explicit = explicit or request.form.get("type")
    ftype = _detect_type(explicit, filename)

    try:
        if ftype == "js":
            result = js_obfuscator.obfuscate_js(code, "high")
            return jsonify({"type": "js", "result": result})
        if ftype == "css":
            result, mapping = css_obfuscator.obfuscate_css(code)
            return jsonify({"type": "css", "result": result, "mapping": mapping})
        if ftype == "py":
            result = py_obfuscator.obfuscate_python(code)
            return jsonify({"type": "py", "result": result})
        if ftype == "html":
            from modules import html_obfuscator
            from modules import verifier
            result, rendered = html_obfuscator.build(code)
            ok, msg = verifier.verify(result, rendered)
            return jsonify({"type": "html", "result": result,
                            "verify": {"ok": ok, "message": msg}})
        return jsonify({"error": "Tipe tidak dikenal: %s "
                                 "(pakai js|css|py|html)" % ftype}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Halaman web ----------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
