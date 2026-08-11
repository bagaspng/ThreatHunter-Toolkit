"""Runtime job manager: runs clip work in a thread, streams progress via asyncio.Queue.

Persistent record lives in db.py; this holds the live event stream + status for SSE.
"""
import asyncio
import os

from . import db
from .core import heatmap
from .core.clipper import process_clip, download_video, find_downloaded
from .core.auto_highlight import find_interesting
from .models import ClipRequest


class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.done = False


_jobs: dict[str, Job] = {}


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def _parse_time(value) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    parts = s.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(float(parts[1]))
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
    except ValueError:
        return None
    return None


def _resolve_targets(req: ClipRequest, video_id: str, total_duration: float | None) -> list[dict]:
    if req.segments:
        return [{"start": s.start, "duration": s.duration, "score": s.score}
                for s in req.segments if s.duration > 0]
    if req.mode == "custom":
        start_s = _parse_time(req.start)
        end_s = _parse_time(req.end)
        if start_s is None or end_s is None:
            raise ValueError("Start/End belum diisi")
        if end_s <= start_s:
            raise ValueError("End harus lebih besar dari Start")
        return [{"start": float(start_s), "duration": float(end_s - start_s), "score": 1.0}]
    if req.mode == "auto":
        # Auto mode: we'll compute targets after download in run()
        # Return empty list to signal this
        return []
    # heatmap mode
    segments, _dur = heatmap.get_segments_and_duration(video_id)
    if not segments:
        raise RuntimeError("Tidak ada heatmap / Most Replayed data")
    return segments[: req.max_clips]


def _list_outputs(job_dir: str) -> list[dict]:
    if not os.path.isdir(job_dir):
        return []
    items = [
        {"name": n, "size": os.path.getsize(os.path.join(job_dir, n))}
        for n in os.listdir(job_dir)
        if n.lower().endswith(".mp4") and not n.startswith("source.")
        and os.path.isfile(os.path.join(job_dir, n))
    ]
    items.sort(key=lambda x: x["name"])
    return items


async def run(job_id: str, req: ClipRequest, clips_root: str, title: str = ""):
    """Coroutine driving one job; pushes events into job.queue for SSE."""
    job = Job(job_id)
    _jobs[job_id] = job
    loop = asyncio.get_running_loop()

    last_error = {"msg": ""}

    def push(event: dict):
        loop.call_soon_threadsafe(job.queue.put_nowait, event)

    def emit(stage: str, data: dict):
        if stage == "error" and data.get("message"):
            last_error["msg"] = data["message"]
        push({"type": "stage", "stage": stage, **data})

    job_dir = os.path.join(clips_root, job_id)
    db.update(job_id, status="running")
    push({"type": "status", "status": "running"})

    try:
        video_id = heatmap.extract_video_id(req.url)
        if not video_id:
            raise ValueError("URL YouTube invalid")

        _segments, total_duration = heatmap.get_segments_and_duration(video_id)
        targets = _resolve_targets(req, video_id, total_duration)
        config = req.to_config(job_dir)

        push({"type": "total", "total": len(targets)})

        # --- download video once, keep it in job dir so edits don't re-download ---
        push({"type": "stage", "stage": "download", "pct": 0})
        out_tmpl = os.path.join(job_dir, "source.%(ext)s")
        await loop.run_in_executor(
            None, download_video, video_id, out_tmpl, emit
        )
        source_file = find_downloaded(job_dir)
        if not source_file:
            raise RuntimeError("Download gagal — file tidak ditemukan setelah yt-dlp selesai")
        push({"type": "stage", "stage": "download", "pct": 100})

        # If targets empty (no heatmap or auto mode without heatmap), auto-detect
        needs_auto = (req.mode == "auto" and not targets) or \
                     (req.mode == "heatmap" and not targets)
        if needs_auto:
            push({"type": "stage", "stage": "auto_detect", "pct": 0})
            try:
                targets = find_interesting(source_file, n_clips=req.max_clips, duration=total_duration)
                push({"type": "total", "total": len(targets)})
                push({"type": "stage", "stage": "auto_detect", "pct": 100})
            except Exception as e:
                push({"type": "stage", "stage": "auto_detect", "pct": 100, "error": str(e)})
                # fallback: if heatmap existed, use that
                if _segments:
                    targets = _segments[: req.max_clips]
                    push({"type": "total", "total": len(targets)})
                else:
                    raise RuntimeError("Auto mode gagal menemukan momen menarik")

        # --- process each clip ---
        success = 0
        for idx, item in enumerate(targets, start=1):
            push({"type": "clip_start", "index": idx, "total": len(targets)})
            ok = await loop.run_in_executor(
                None, process_clip, source_file, item, idx, total_duration, config, emit
            )
            if ok:
                success += 1
            outputs = _list_outputs(job_dir)
            db.update(job_id, outputs=outputs)
            push({"type": "clip_done", "index": idx, "success": success, "outputs": outputs})

        outputs = _list_outputs(job_dir)
        if success == 0 and targets:
            msg = last_error["msg"] or "Semua clip gagal diproses (cek URL / koneksi)"
            db.update(job_id, status="error", error=msg, finished_at=_now(), outputs=outputs)
            push({"type": "status", "status": "error", "error": msg, "outputs": outputs})
        else:
            db.update(job_id, status="done", finished_at=_now(), outputs=outputs)
            push({"type": "status", "status": "done", "outputs": outputs, "success": success})
    except Exception as e:
        db.update(job_id, status="error", error=str(e), finished_at=_now())
        push({"type": "status", "status": "error", "error": str(e)})
    finally:
        job.done = True
        push({"type": "end"})


def _now() -> int:
    import time
    return int(time.time() * 1000)
