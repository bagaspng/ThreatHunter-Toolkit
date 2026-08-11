# -*- coding: utf-8 -*-
"""whisper_server.ipynb

Auto-transcribe microservice for the Heatmap Clipper — runs faster-whisper on a
free GPU (Google Colab / Kaggle) so the local machine doesn't load the model.

Stack: faster-whisper (GPU) -> FastAPI -> Cloudflare Tunnel

# Setup checklist before running this cell
1. Colab: Runtime -> Change runtime type -> GPU (T4). Kaggle: Accelerator -> GPU T4 x2.
2. Run this cell. Wait for install + model load (first run a few minutes).
3. Copy BASE_URL / API_KEY printed at the end into your local .env:
     WHISPER_BASE_URL="https://xxxx.trycloudflare.com"
     WHISPER_API_KEY="sk-whisper-local"
   The local backend then sends each clip's audio here and gets back SRT segments.

# Notes
- The Cloudflare URL is temporary — it changes every restart.
- Keep this cell RUNNING while clipping with subtitles.
- Stopping the cell runs cleanup (frees RAM/VRAM).
"""

import subprocess, time, os, re, sys, gc, atexit, signal, requests

# ── CONFIG ───────────────────────────────────────────────
# Model size: tiny / base / small / medium / large-v3.
# "small" = good accuracy on a free T4. Smaller = faster.
MODEL = "small"
PORT = 4000
API_KEY = "sk-whisper-local"

SERVER_SRC = r'''
import os, time, threading, tempfile
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from faster_whisper import WhisperModel

MODEL = os.environ.get("WHISPER_MODEL", "small")
API_KEY = os.environ.get("WHISPER_API_KEY", "sk-whisper-local")

app = FastAPI(title="Whisper Transcribe")
_model = None

# ponytail: in-memory status so callers can see "being used" + live progress
# via GET /status. Single-user notebook: one busy job at a time is enough.
_STATUS_LOCK = threading.Lock()
_STATUS = {"state": "idle", "source": "", "started_at": 0.0, "progress": 0, "message": ""}


def get_model():
    global _model
    if _model is None:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            _model = _try_cuda() or WhisperModel(MODEL, device="cpu", compute_type="int8")
        else:
            _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    return _model


def _set_status(**kw):
    with _STATUS_LOCK:
        _STATUS.update(kw)


# ponytail: probe real cuda inference once; get_cuda_device_count() reports a
# device even when cuBLAS is missing, which only fails at transcribe time.
def _try_cuda():
    import wave
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 1600)
        m = WhisperModel(MODEL, device="cuda", compute_type="float16")
        try:
            list(m.transcribe(path, language="en")[0])
            return m
        except Exception:
            return None
    finally:
        if os.path.exists(path):
            os.remove(path)


def _audio_duration(path: str) -> float:
    """Audio length in seconds via ffprobe (used to estimate progress %)."""
    import json, subprocess
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


@app.get("/health")
def health():
    with _STATUS_LOCK:
        state = _STATUS["state"]
    return {"ok": True, "model": MODEL, "loaded": _model is not None, "state": state}


@app.get("/status")
def status():
    with _STATUS_LOCK:
        return dict(_STATUS)


@app.post("/transcribe")
def transcribe(audio: UploadFile = File(...), authorization: str = Header(default="")):
    # Sync def => FastAPI runs this in a threadpool so /status & /health stay
    # responsive while the GPU is busy (feedback works during transcription).
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "bad key")
    with _STATUS_LOCK:
        if _STATUS["state"] == "busy":
            raise HTTPException(429, "notebook busy - tunggu transkripsi sebelumnya selesai")
        _STATUS.update(state="busy", source=audio.filename or "clip.mp3",
                       started_at=time.time(), progress=0, message="menyiapkan audio")
    fd, tmp = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            f.write(audio.file.read())
        _set_status(message="transkripsi berjalan")
        segments, info = get_model().transcribe(tmp, language=None)
        duration = float(getattr(info, "duration", 0) or 0)
        if not duration:
            duration = _audio_duration(tmp)
        out = []
        for s in segments:
            out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
            if duration > 0:
                _set_status(progress=min(99, int((s.end / duration) * 100)))
        _set_status(progress=100, message="selesai")
        print(f"[transcribe] done: {len(out)} segments")
        return {"ok": True, "segments": out}
    except Exception as e:
        _set_status(message=f"error: {e}")
        raise
    finally:
        _set_status(state="idle", progress=0, message="")
        try:
            os.remove(tmp)
        except OSError:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "4000")))
'''

# ── Utilities ────────────────────────────────────────────

def sh(cmd, check=True, quiet=False, capture=False):
    kw = dict(shell=True, check=check)
    if capture:
        kw.update(capture_output=True, text=True)
    elif quiet:
        kw.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.run(cmd, **kw)


def bg(cmd, log=None):
    out = open(log, "w") if log else subprocess.DEVNULL
    return subprocess.Popen(cmd, shell=True, stdout=out, stderr=subprocess.STDOUT)


def wait_http(url, timeout=60, name=""):
    for i in range(timeout):
        try:
            if requests.get(url, timeout=2).status_code < 500:
                print(f"  [OK] {name} ready")
                return True
        except Exception:
            pass
        if i > 0 and i % 15 == 14:
            print(f"  [..] waiting for {name} ({i + 1}s)")
        time.sleep(1)
    print(f"  [!!] {name} not confirmed after {timeout}s — continuing")
    return False


def section(n, title):
    bar = "-" * 64
    print(f"\n{bar}\n [{n}/4] {title}\n{bar}")


_procs = {"server": None, "cloudflared": None}
_cleaned_up = False


def cleanup(*_args):
    global _cleaned_up
    if _cleaned_up:
        return
    _cleaned_up = True
    print("\n  [cleanup] stopping processes + freeing VRAM...")
    for name, proc in _procs.items():
        if proc is None:
            continue
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    sh("pkill -9 -f cloudflared", check=False, quiet=True)
    sh("pkill -9 -f whisper_server", check=False, quiet=True)
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    print("  [OK] cleanup complete")


atexit.register(cleanup)
signal.signal(signal.SIGTERM, cleanup)

# Pre-cleanup in case this cell was re-run after a crash.
sh("pkill -9 -f cloudflared", check=False, quiet=True)
sh("pkill -9 -f whisper_server", check=False, quiet=True)
time.sleep(1)

print("=" * 64)
print("  Whisper Server - GPU microservice for Heatmap Clipper")
print(f"  Model: {MODEL}   Port: {PORT}")
print("=" * 64)

try:
    # -- 1. INSTALL ------------------------------------------
    section(1, "Install deps")
    sh("pip install -q faster-whisper fastapi 'uvicorn[standard]' python-multipart")

    # -- 2. WRITE + START SERVER -----------------------------
    section(2, "Start FastAPI whisper server")
    with open("/tmp/whisper_server.py", "w") as f:
        f.write(SERVER_SRC)
    env = os.environ.copy()
    env.update({"WHISPER_MODEL": MODEL, "WHISPER_API_KEY": API_KEY, "PORT": str(PORT)})
    _procs["server"] = bg("python /tmp/whisper_server.py", "/tmp/whisper.log")
    if not wait_http(f"http://localhost:{PORT}/health", 90, "whisper server"):
        print("  [!!] server log tail:")
        try:
            print("  " + open("/tmp/whisper.log").read()[-1500:])
        except Exception:
            pass

    # -- 3. CLOUDFLARE TUNNEL --------------------------------
    section(3, "Cloudflare tunnel -> public URL")
    sh("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/"
       "cloudflared-linux-amd64 -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared")
    _procs["cloudflared"] = bg(
        f"cloudflared tunnel --url http://localhost:{PORT}", "/tmp/cloudflared.log")
    tunnel_url = None
    for _ in range(90):
        time.sleep(1)
        try:
            m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com",
                          open("/tmp/cloudflared.log").read())
            if m:
                tunnel_url = m.group(0)
                break
        except Exception:
            pass

    # -- 4. READY --------------------------------------------
    section(4, "Ready")
    if tunnel_url:
        print(f"""
  BASE_URL="{tunnel_url}"
  API_KEY="{API_KEY}"

  Paste both into your local .env (youtube-heatmap-clipper/.env)
  to route subtitle transcription through this GPU notebook.
""")
    else:
        print("  [!!] no tunnel URL found. Check: !cat /tmp/cloudflared.log")
        print(f"      Local server: http://localhost:{PORT}")

except Exception as e:
    print(f"\n  [FAIL] startup error: {e}")
    cleanup()
    sys.exit(1)

# ── KEEP ALIVE (Heartbeat) ───────────────────────────────
tick = 0
try:
    while True:
        time.sleep(60)
        tick += 1
        ts = time.strftime("%H:%M:%S")
        try:
            requests.get(f"http://localhost:{PORT}/health", timeout=5)
            status = "healthy"
        except Exception:
            status = "unreachable"
        print(f"  [{ts}] heartbeat #{tick:04d} | {status} | {tunnel_url or 'no tunnel'}")
except KeyboardInterrupt:
    cleanup()
