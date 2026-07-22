#!/usr/bin/env python3
from flask import Flask, jsonify, render_template, request

import engine

app = Flask(__name__)
_MAX_BYTES = 5_000_000


def _extract():
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            data = f.read()
            if len(data) > _MAX_BYTES:
                return None, None, "File terlalu besar (maks 5 MB)."
            return data.decode("utf-8", "replace"), request.form.get("type"), None
    if request.is_json:
        body = request.get_json(silent=True) or {}
        return body.get("text"), body.get("type"), None
    return request.form.get("text"), request.form.get("type"), None


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    text, type_hint, err = _extract()
    if err:
        return jsonify({"error": err}), 400
    if not text or not text.strip():
        return jsonify({"error": "Input kosong."}), 400
    if len(text) > _MAX_BYTES:
        return jsonify({"error": "Input terlalu besar (maks 5 MB)."}), 400
    return jsonify(engine.analyze(text, type_hint))


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8001, debug=False)
