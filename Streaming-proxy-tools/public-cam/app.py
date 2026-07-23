import json
import os
import queue
import sys
import threading
import time
import concurrent.futures
import random

from flask import Flask, Response, jsonify, render_template, request
from public_cam import (
    COUNTRIES,
    FILTER_MODE,
    InsecamScraper,
    DorkEngine,
    CameraVerifier,
    USER_AGENTS,
)
from urllib.parse import urlparse

app = Flask(__name__)

# Global state
scan_state = {
    "running": False,
    "mode": "IDLE",
    "found": [],
    "total": 0,
    "filter": "ALL",
    "target_country": None,
}
scan_queue = queue.Queue()
scan_lock = threading.Lock()


def do_scan(mode, country, pages, filter_mode):
    """Run the camera scan in a background thread."""
    global scan_state

    insecam = InsecamScraper()
    dorker = DorkEngine()
    verifier = CameraVerifier()

    # Override global filter
    import public_cam
    public_cam.FILTER_MODE = filter_mode

    seen_urls = set()

    def verify_and_emit(camera):
        if camera["url"] in seen_urls:
            return
        seen_urls.add(camera["url"])

        result = verifier.verify(camera)
        if result:
            scan_queue.put({"event": "camera", "data": result})
            with scan_lock:
                scan_state["found"].append(result)
                scan_state["total"] = len(scan_state["found"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        if mode in ["UNIFIED", "INSECAM"]:
            scan_queue.put({"event": "status", "data": f"Scraping Insecam ({pages} pages)..."})
            cameras = insecam.scrape(country=country, max_pages=pages)
            scan_queue.put({"event": "status", "data": f"Found {len(cameras)} feeds from Insecam, verifying..."})
            list(executor.map(verify_and_emit, cameras))

        if mode in ["UNIFIED", "DORK"]:
            scan_queue.put({"event": "status", "data": f"Running deep search with Google Dorks..."})
            futures = []
            for camera in dorker.scan(limit=pages * 10):
                futures.append(executor.submit(verify_and_emit, camera))

    scan_queue.put({"event": "done", "data": {"total": scan_state["total"]}})

    # Save results
    os.makedirs("cam_scrape", exist_ok=True)
    filename = f"cam_scrape/scan_result_{int(time.time())}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(scan_state["found"], f, indent=4)

    with scan_lock:
        scan_state["running"] = False
        scan_state["mode"] = "IDLE"


@app.route("/")
def index():
    return render_template("index.html", countries=COUNTRIES)


@app.route("/api/start_scan", methods=["POST"])
def start_scan():
    global scan_state

    with scan_lock:
        if scan_state["running"]:
            return jsonify({"error": "A scan is already running."}), 409

        data = request.json
        mode = data.get("mode", "INSECAM").upper()
        country = data.get("country") or None
        pages = int(data.get("pages", 3))
        filter_mode = data.get("filter", "ALL").upper()

        scan_state = {
            "running": True,
            "mode": mode,
            "found": [],
            "total": 0,
            "filter": filter_mode,
            "target_country": country,
        }

    # Clear queue
    while not scan_queue.empty():
        scan_queue.get_nowait()

    thread = threading.Thread(
        target=do_scan, args=(mode, country, pages, filter_mode), daemon=True
    )
    thread.start()

    return jsonify({"status": "started", "mode": mode})


@app.route("/api/stop_scan", methods=["POST"])
def stop_scan():
    with scan_lock:
        scan_state["running"] = False
    scan_queue.put({"event": "done", "data": {"total": scan_state["total"], "stopped": True}})
    return jsonify({"status": "stopped"})


@app.route("/api/stream")
def stream():
    """SSE endpoint for real-time scan results."""
    def event_generator():
        # Send current state first
        yield f"data: {json.dumps({'event': 'init', 'data': scan_state})}\n\n"

        while True:
            try:
                item = scan_queue.get(timeout=1.0)
                yield f"data: {json.dumps(item)}\n\n"

                if item.get("event") == "done":
                    break
            except queue.Empty:
                # Send heartbeat
                yield f"data: {json.dumps({'event': 'ping'})}\n\n"

                if not scan_state["running"]:
                    break

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/state")
def get_state():
    return jsonify(scan_state)


@app.route("/api/results")
def get_results():
    """Return all found cameras in current session."""
    return jsonify(scan_state["found"])


@app.route("/api/history")
def get_history():
    """Return list of past scan result files."""
    results = []
    if os.path.exists("cam_scrape"):
        for f in sorted(os.listdir("cam_scrape"), reverse=True):
            if f.endswith(".json"):
                path = os.path.join("cam_scrape", f)
                try:
                    with open(path, encoding="utf-8") as fp:
                        data = json.load(fp)
                    results.append({
                        "filename": f,
                        "count": len(data),
                        "timestamp": int(f.replace("scan_result_", "").replace(".json", "")),
                    })
                except Exception:
                    pass
    return jsonify(results)


@app.route("/api/history/<filename>")
def get_history_file(filename):
    path = os.path.join("cam_scrape", filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
