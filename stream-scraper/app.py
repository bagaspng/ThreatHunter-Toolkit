"""
Flask app entry point — Milestone 4.

No parsing/scraping logic here; only app setup and blueprint registration.
"""

import threading
from flask import Flask, jsonify, render_template, request
from flask_sock import Sock
import websocket

from api.routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    sock = Sock(app)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/")
    def index():
        return jsonify({
            "service": "CCTV Stream Discovery API",
            "endpoints": [
                "GET /player  — Dashboard CCTV",
                "GET /api/cameras  — List semua kamera (dari cameras.json)",
                "GET /api/cameras/<camera_id>  — Detail satu kamera",
            ],
        })

    @app.get("/player")
    def player():
        return render_template("player.html")

    @sock.route("/ws-proxy")
    def ws_proxy(ws):
        target_url = request.args.get("url")
        if not target_url:
            ws.close(1008, "Missing url parameter")
            return

        try:
            remote_ws = websocket.create_connection(
                target_url,
                origin="https://stream.lihatcctv.com",
                header=[
                    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ]
            )
        except Exception as e:
            ws.close(1011, f"Failed to connect to remote server: {e}")
            return

        running = True

        def forward_remote():
            nonlocal running
            try:
                while running:
                    frame = remote_ws.recv()
                    if frame is None:
                        break
                    ws.send(frame)
            except Exception:
                pass
            finally:
                running = False
                try:
                    ws.close()
                except Exception:
                    pass

        thread = threading.Thread(target=forward_remote, daemon=True)
        thread.start()

        try:
            while running:
                message = ws.receive()
                if message is None:
                    break
                remote_ws.send(message)
        except Exception:
            pass
        finally:
            running = False
            try:
                remote_ws.close()
            except Exception:
                pass

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)