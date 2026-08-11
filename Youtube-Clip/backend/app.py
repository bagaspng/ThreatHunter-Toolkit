"""FastAPI app: auth, preview, scan, clip jobs (SSE), history, ZIP, static serve."""
import asyncio
import io
import os
import subprocess
import uuid
import zipfile

from dotenv import load_dotenv

load_dotenv()  # read .env (WHISPER_BASE_URL, WHISPER_API_KEY, DATA_DIR, ...)

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import auth, db, jobs
from .jobs import _resolve_targets
from .core import heatmap
from .core.ffmpeg_filters import ensure_ffmpeg_on_path, ffmpeg_available
from .models import ClipRequest, LoginRequest, UrlRequest, EditClipRequest

DATA_DIR = os.environ.get("DATA_DIR", "data")
CLIPS_ROOT = os.path.join(DATA_DIR, "clips")
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

app = FastAPI(title="YouTube Heatmap Clipper")

_preview_cache: dict[str, dict] = {}


@app.on_event("startup")
def _startup():
    os.makedirs(CLIPS_ROOT, exist_ok=True)
    db.init(DATA_DIR)
    ensure_ffmpeg_on_path()


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    path = request.url.path
    open_paths = ("/api/login", "/api/health")
    if path.startswith("/api/") and path not in open_paths and not auth.is_authed(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


# ---------------------------------------------------------------- auth / health
@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": ffmpeg_available(), "auth": auth.enabled()}


@app.post("/api/login")
def login(body: LoginRequest, response: Response):
    if not auth.enabled():
        return {"ok": True, "auth": False}
    if not auth.check_password(body.password):
        raise HTTPException(status_code=401, detail="Password salah")
    response.set_cookie(
        auth.COOKIE_NAME, auth.make_token(),
        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30,
    )
    return {"ok": True}


# ---------------------------------------------------------------- preview / scan
@app.post("/api/preview")
async def preview(body: UrlRequest):
    key = body.url.strip()
    if not key:
        raise HTTPException(400, "URL kosong")
    if key in _preview_cache:
        return {"ok": True, "preview": _preview_cache[key]}

    video_id = heatmap.extract_video_id(key)
    if not video_id:
        raise HTTPException(400, "URL YouTube invalid")
    try:
        info = await run_in_threadpool(heatmap.fetch_info, video_id)
    except Exception as e:
        raise HTTPException(400, str(e))

    data = {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "id": info.get("id"),
        "webpage_url": info.get("webpage_url") or key,
    }
    if len(_preview_cache) > 200:
        _preview_cache.clear()
    _preview_cache[key] = data
    return {"ok": True, "preview": data}


@app.post("/api/scan")
async def scan(body: UrlRequest):
    video_id = heatmap.extract_video_id(body.url.strip())
    if not video_id:
        raise HTTPException(400, "URL YouTube invalid")
    segments, duration = await run_in_threadpool(heatmap.get_segments_and_duration, video_id)
    return {"ok": True, "video_id": video_id, "duration": duration, "segments": segments}


# ---------------------------------------------------------------- clip jobs
@app.post("/api/clip")
async def create_clip(body: ClipRequest):
    if not ffmpeg_available():
        raise HTTPException(400, "FFmpeg tidak ketemu")
    job_id = uuid.uuid4().hex[:12]
    title = _preview_cache.get(body.url.strip(), {}).get("title", "")
    db.create(job_id, body.model_dump(), title=title)
    asyncio.create_task(jobs.run(job_id, body, CLIPS_ROOT, title=title))
    return {"ok": True, "job_id": job_id}


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        # Job may already be finished (persisted only). Send its final state once.
        record = db.get(job_id)
        if not record:
            raise HTTPException(404, "Job not found")

        async def once():
            yield _sse({"type": "status", "status": record["status"],
                        "outputs": record["outputs"], "error": record["error"]})
            yield _sse({"type": "end"})
        return StreamingResponse(once(), media_type="text/event-stream")

    async def stream():
        while True:
            event = await job.queue.get()
            yield _sse(event)
            if event.get("type") == "end":
                break

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/jobs")
def list_jobs():
    return {"ok": True, "jobs": db.list_all()}


@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str):
    record = db.get(job_id)
    if not record:
        raise HTTPException(404, "Job not found")
    return {"ok": True, "job": record}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    import shutil
    shutil.rmtree(os.path.join(CLIPS_ROOT, job_id), ignore_errors=True)
    db.delete(job_id)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/download.zip")
def download_zip(job_id: str):
    job_dir = os.path.join(CLIPS_ROOT, job_id)
    if not os.path.isdir(job_dir):
        raise HTTPException(404, "Job not found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name in sorted(os.listdir(job_dir)):
            if name.lower().endswith(".mp4"):
                zf.write(os.path.join(job_dir, name), arcname=name)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="clips_{job_id}.zip"'},
    )


# ---------------------------------------------------------------- clip edit (re-render)

@app.post("/api/clip/edit")
async def edit_clip(body: EditClipRequest):
    """Re-render a single clip with custom parameters."""
    if not ffmpeg_available():
        raise HTTPException(400, "FFmpeg tidak ketemu")

    record = db.get(body.job_id)
    if not record:
        raise HTTPException(404, "Job not found")

    job_dir = os.path.join(CLIPS_ROOT, body.job_id)
    if not os.path.isdir(job_dir):
        raise HTTPException(404, "Job clips not found")

    # Find original clip file to get index
    clip_name = f"clip_{body.clip_index}.mp4"
    orig_path = os.path.join(job_dir, clip_name)
    if not os.path.isfile(orig_path):
        raise HTTPException(404, f"Original clip {clip_name} not found")

    # Find source video: prefer the copy kept in the job dir by jobs.run()
    video_id = heatmap.extract_video_id(record["request"]["url"])
    if not video_id:
        raise HTTPException(400, "Invalid URL in job record")

    # Source video cached in job dir by jobs.run(); download once if absent
    source_file = _find_source(job_dir)
    if source_file is None:
        from .core.clipper import download_video, find_downloaded
        out_tmpl = os.path.join(job_dir, "source.%(ext)s")
        def _download_emit(stage, data): pass  # no SSE for edit
        download_video(video_id, out_tmpl, _download_emit)
        source_file = find_downloaded(job_dir)
        if not source_file:
            raise HTTPException(500, "Download gagal")

    # Reconstruct original segment params from request
    req_data = record["request"]
    config = ClipRequest(**req_data).to_config(job_dir)

    # Find the target segment for this clip index
    segments, total_duration = heatmap.get_segments_and_duration(video_id)
    targets = _resolve_targets(ClipRequest(**req_data), video_id, total_duration)
    if body.clip_index > len(targets):
        raise HTTPException(404, "Clip index out of range")
    original_item = targets[body.clip_index - 1]

    # Build edit dict
    edit = {
        "trim_start_offset": body.trim_start_offset,
        "trim_end_offset": body.trim_end_offset,
        "crop_cx": body.crop_cx,
        "crop_keyframes": body.crop_keyframes,
        "cuts": body.cuts,
        "hook_text": body.hook_text,
        "subtitle": body.subtitle,
        "ratio": body.ratio,
        "crop": body.crop,
    }

    # Re-render
    from .core.clipper import rerender_clip
    ok = rerender_clip(source_file, original_item, body.clip_index,
                       total_duration, config, edit)
    if not ok:
        raise HTTPException(500, "Re-render gagal")

    return {"ok": True, "path": f"/clips/{body.job_id}/clip_{body.clip_index}_edited.mp4"}


def _find_source(job_dir: str) -> str | None:
    """Locate the cached source video in a job dir (source.<ext>)."""
    for name in os.listdir(job_dir):
        if name.startswith("source.") and os.path.isfile(os.path.join(job_dir, name)):
            return os.path.join(job_dir, name)
    return None


@app.get("/clips/{job_id}/{filename}")
def serve_clip(job_id: str, filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "bad path")
    path = os.path.join(CLIPS_ROOT, job_id, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Not found")
    return FileResponse(path)


@app.get("/api/clip/{job_id}/{clip_index}/source")
def clip_source(job_id: str, clip_index: int):
    """Served trimmed-but-uncropped source segment for realtime editor preview.

    Cache: clips/{job_id}/source_preview_{clip_index}.mp4 (stream-copied once,
    reused on every edit — no re-download, no re-encode).
    """
    record = db.get(job_id)
    if not record:
        raise HTTPException(404, "Job not found")
    job_dir = os.path.join(CLIPS_ROOT, job_id)
    source_file = _find_source(job_dir)
    if source_file is None:
        raise HTTPException(404, "Source video not found")

    video_id = heatmap.extract_video_id(record["request"]["url"])
    if not video_id:
        raise HTTPException(400, "Invalid URL in job record")

    _, total_duration = heatmap.get_segments_and_duration(video_id)
    targets = _resolve_targets(ClipRequest(**record["request"]), video_id, total_duration)
    if clip_index > len(targets):
        raise HTTPException(404, "Clip index out of range")
    item = targets[clip_index - 1]

    config = ClipRequest(**record["request"]).to_config(job_dir)
    start = max(0.0, item["start"] - config.padding)
    end = min(item["start"] + item["duration"] + config.padding, total_duration or 1e9)

    cached = os.path.join(job_dir, f"source_preview_{clip_index}.mp4")
    if not os.path.isfile(cached):
        from .core.clipper import _trim_cmd
        r = subprocess.run(_trim_cmd(source_file, start, end, cached), capture_output=True)
        if r.returncode != 0 or not os.path.isfile(cached):
            raise HTTPException(500, "Gagal membuat preview source")
    return FileResponse(cached)


def _sse(event: dict) -> str:
    import json
    return f"data: {json.dumps(event)}\n\n"


# ---------------------------------------------------------------- static frontend
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
