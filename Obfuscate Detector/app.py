#!/usr/bin/env python3
from flask import Flask, jsonify, render_template, request

import engine

app = Flask(__name__)
# Tanpa batas ukuran masukan (hanya dibatasi memori yang tersedia).
app.config["MAX_CONTENT_LENGTH"] = None


def _extract():
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            data = f.read()
            return data.decode("utf-8", "replace"), request.form.get("type")
    if request.is_json:
        body = request.get_json(silent=True) or {}
        return body.get("text"), body.get("type")
    return request.form.get("text"), request.form.get("type")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    text, type_hint = _extract()
    if not text or not text.strip():
        return jsonify({"error": "Input kosong."}), 400
    return jsonify(engine.analyze(text, type_hint))


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8001, debug=False)
