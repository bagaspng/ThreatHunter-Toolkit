"""SQLite job persistence (stdlib sqlite3, no ORM).

Jobs survive restart; the runtime progress/event stream lives in jobs.py (in-memory).
"""
import json
import os
import sqlite3
import threading
import time

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    """Lazy accessor so callers work even if init() wasn't run at startup."""
    if _conn is None:
        init(os.environ.get("DATA_DIR", "data"))
    return _conn


def init(data_dir: str) -> None:
    global _conn
    if _conn is not None:
        return
    os.makedirs(data_dir, exist_ok=True)
    _conn = sqlite3.connect(os.path.join(data_dir, "jobs.db"), check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            created_at INTEGER,
            finished_at INTEGER,
            status TEXT,
            title TEXT,
            request_json TEXT,
            outputs_json TEXT,
            error TEXT
        )"""
    )
    _conn.commit()


def create(job_id: str, request: dict, title: str = "") -> None:
    conn = _db()
    with _lock:
        conn.execute(
            "INSERT INTO jobs (id, created_at, status, title, request_json, outputs_json) "
            "VALUES (?, ?, 'queued', ?, ?, '[]')",
            (job_id, int(time.time() * 1000), title, json.dumps(request)),
        )
        conn.commit()


def update(job_id: str, **fields) -> None:
    if not fields:
        return
    if "outputs" in fields:
        fields["outputs_json"] = json.dumps(fields.pop("outputs"))
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn = _db()
    with _lock:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", (*fields.values(), job_id))
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["request"] = json.loads(d.pop("request_json") or "{}")
    d["outputs"] = json.loads(d.pop("outputs_json") or "[]")
    return d


def get(job_id: str) -> dict | None:
    conn = _db()
    with _lock:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_all(limit: int = 100) -> list[dict]:
    conn = _db()
    with _lock:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete(job_id: str) -> None:
    conn = _db()
    with _lock:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
