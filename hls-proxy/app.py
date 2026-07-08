"""
app.py — Flask application with HLS proxy routes.

No dashboard HTML. Just the proxy endpoints:
  /playlist  — Fetched & rewritten .m3u8
  /segment   — Proxied video segments
  /key       — Proxied decryption keys
"""

from flask import Flask, request, Response
from playlist import get_playlist_response
from proxy import proxy_request

app = Flask(__name__)


# ── CORS ────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


# ── Routes ──────────────────────────────────────────────────────────
@app.route("/playlist", methods=["GET"])
def playlist():
    """Fetch, rewrite, and serve the HLS playlist."""
    return get_playlist_response()


@app.route("/segment", methods=["GET"])
def segment():
    """Proxy a video segment from the CDN."""
    url = request.args.get("url")
    if not url:
        return Response("Missing 'url' parameter", status=400)
    return proxy_request(url, request.headers)


@app.route("/key", methods=["GET"])
def key():
    """Proxy a decryption key from the CDN."""
    url = request.args.get("url")
    if not url:
        return Response("Missing 'url' parameter", status=400)
    return proxy_request(url, request.headers)
