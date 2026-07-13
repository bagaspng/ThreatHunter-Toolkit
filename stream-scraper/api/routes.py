"""
API routes — Milestone 4.

Reads from output/cameras.json (produced by main.py).
No live scraping per request — all data is pre-scraped.
"""

import json
from pathlib import Path

from flask import Blueprint, jsonify

import config

api_bp = Blueprint("api", __name__)

CAMERAS_FILE = Path(config.CAMERAS_OUTPUT_FILE)


def _load_cameras() -> list[dict]:
    if not CAMERAS_FILE.exists():
        return []
    with open(CAMERAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("cameras", [])


@api_bp.get("/cameras")
def cameras_list():
    """Return the full list of scraped cameras."""
    cameras = _load_cameras()
    return jsonify({"cameras": cameras, "total": len(cameras)})


@api_bp.get("/cameras/<camera_id>")
def camera_detail(camera_id: str):
    """Return detail for a single camera by id."""
    for cam in _load_cameras():
        if cam["id"] == camera_id:
            return jsonify(cam)
    return jsonify({"error": f"Kamera '{camera_id}' tidak ditemukan."}), 404