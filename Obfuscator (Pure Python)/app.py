#!/usr/bin/env python3

import base64

from flask import Flask, jsonify, request, render_template

from modules import encoder
from modules import decoder
from modules import layer_hint
from modules import js_obfuscator
from modules import css_obfuscator
from modules import py_obfuscator
from modules import stego

app = Flask(__name__)

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


def get_payload(*keys):
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            return f.read().decode("utf-8", errors="replace"), f.filename

    if request.is_json:
        data = request.get_json(silent=True) or {}
        for k in keys:
            if data.get(k):
                return data[k], None

    for k in keys:
        if request.form.get(k):
            return request.form[k], None

    return None, None


def _run_methods(methods, text):
    results = {}
    for name, fn in methods.items():
        try:
            results[name] = {"ok": True, "value": fn(text)}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}
    return results


def _with_hints(results):
    for item in results.values():
        if item.get("ok"):
            item["hint"] = layer_hint.hint(item["value"])
    return results


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
    return jsonify({"input": text,
                    "results": _with_hints(_run_methods(DECODE_METHODS, text))})


@app.route("/api/translate", methods=["POST"])
def api_translate():
    text, _ = get_payload("text", "code")
    if not text:
        return jsonify({"error": "Field 'text' kosong."}), 400
    return jsonify({
        "input": text,
        "encode": _run_methods(ENCODE_METHODS, text),
        "decode": _with_hints(_run_methods(DECODE_METHODS, text)),
    })


@app.route("/api/peel", methods=["POST"])
def api_peel():
    text, _ = get_payload("text", "code")
    if not text:
        return jsonify({"error": "Field 'text' kosong."}), 400
    steps = layer_hint.peel(text)
    return jsonify({
        "input": text,
        "steps": [{"name": n, "value": v} for n, v in steps],
        "final": steps[-1][1] if steps else text,
    })


@app.route("/api/stego/encode", methods=["POST"])
def api_stego_encode():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Gambar PNG belum diunggah."}), 400
    message = request.form.get("message", "")
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400
    try:
        out = stego.encode(f.read(), message)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    data_url = "data:image/png;base64," + base64.b64encode(out).decode("ascii")
    return jsonify({"image": data_url, "bytes": len(out),
                    "message_len": len(message.encode("utf-8"))})


@app.route("/api/stego/decode", methods=["POST"])
def api_stego_decode():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Gambar PNG belum diunggah."}), 400
    try:
        message = stego.decode(f.read())
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    score = stego.readability(message)
    readable = bool(message) and score >= 0.85
    return jsonify({"message": message, "readable": readable,
                    "score": round(score * 100)})


def _detect_type(explicit, filename):
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


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
