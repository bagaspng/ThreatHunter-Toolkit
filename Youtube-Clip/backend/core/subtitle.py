"""Auto subtitle generation via faster-whisper (local) or a remote whisper notebook.

Flow:
  - Local (default): transcribe with language=None (auto-detect) via faster-whisper.
  - Remote: if WHISPER_BASE_URL env is set, extract audio locally (ffmpeg) and POST it
    to the whisper notebook (Colab/Kaggle, GPU) which returns JSON segments.
  - Reformat into short entries (MAX_WORDS_PER_LINE) for mobile readability.
  - Also provide pick_hook_text() for the auto-hook feature.
"""
import os
import subprocess
import tempfile

from .config import ClipConfig

MAX_WORDS_PER_LINE = 5  # ponytail: tune if subtitles feel too fast/slow

# Words that signal an engaging/hook moment — used by auto-hook.
_HOOK_WORDS = {
    "wow", "gila", "amazing", "insane", "crazy", "incredible", "terrible",
    "luar biasa", "tunggu", "wait", "omg", "seriously", "nggak", "tidak",
    "ini", "dia", "kamu", "anda", "you", "this", "that", "guys", "teman-teman",
    "check", "watch", "lihat", "coba", "bayangin", "imagine", "yang",
    "rahasia", "secret", "hack", "tips", "fakta", "fact", "akhirnya",
    "finally", "stop", "jangan", "don't", "dont",
}


def format_timestamp(seconds: float) -> str:
    """seconds -> SRT timestamp HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _split_segment(start: float, end: float, text: str) -> list[tuple[float, float, str]]:
    """Split one whisper segment into chunks of MAX_WORDS_PER_LINE words.
    Distribute time proportionally to word count.
    """
    words = text.split()
    if not words:
        return []
    if len(words) <= MAX_WORDS_PER_LINE:
        return [(start, end, text)]

    duration = end - start
    chunks = [words[i:i + MAX_WORDS_PER_LINE] for i in range(0, len(words), MAX_WORDS_PER_LINE)]
    total_words = len(words)
    result = []
    t = start
    for chunk in chunks:
        chunk_dur = duration * len(chunk) / total_words
        chunk_end = min(t + chunk_dur, end)
        result.append((t, chunk_end, " ".join(chunk)))
        t = chunk_end
    return result


def _transcribe_remote(video_file: str, emit) -> list[dict]:
    """Transcribe via the remote whisper notebook. Returns [{start, end, text}, ...]."""
    import requests

    base = os.environ["WHISPER_BASE_URL"].rstrip("/")
    api_key = os.environ.get("WHISPER_API_KEY", "")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        audio = f.name
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", video_file, "-ac", "1", "-ar", "16000", "-b:a", "96k", audio],
            capture_output=True,
        )
        if r.returncode != 0:
            raise RuntimeError("ffmpeg audio extraction failed")
        if emit:
            emit("subtitle_transcribe", {})
        # Run the POST on a worker thread so we can poll the notebook's /status
        # in parallel and stream its progress as subtitle_transcribe stage events.
        import concurrent.futures

        def _report(pct):
            if emit:
                emit("subtitle_transcribe", {"pct": pct})

        holder: dict = {}
        last_pct = -1

        def _post():
            with open(audio, "rb") as f:
                holder["resp"] = requests.post(
                    f"{base}/transcribe",
                    files={"audio": (os.path.basename(audio), f, "audio/mpeg")},
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=300,
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_post)
            while not fut.done():
                try:
                    pct = requests.get(f"{base}/status", timeout=5).json().get("progress")
                except Exception:
                    pct = None
                if isinstance(pct, int) and pct != last_pct:
                    last_pct = pct
                    _report(pct)
                try:
                    fut.result(timeout=0.5)
                except concurrent.futures.TimeoutError:
                    continue
        resp = holder.get("resp")
        if resp is None:
            raise RuntimeError("Whisper notebook timed out")
        if not resp.ok:
            raise RuntimeError(
                f"Whisper notebook error {resp.status_code}: {resp.text[:200]}")
        _report(100)
        return resp.json().get("segments", [])
    finally:
        try:
            os.remove(audio)
        except OSError:
            pass


def generate_srt(video_file: str, srt_file: str, config: ClipConfig, emit=None) -> bool:
    """Transcribe video_file (local or remote notebook) and write a reformatted SRT."""
    remote_base = os.environ.get("WHISPER_BASE_URL", "").strip()
    if remote_base:
        try:
            segments = _transcribe_remote(video_file, emit)
        except Exception:
            if emit:
                emit("subtitle_error", {})
            return False
    else:
        from faster_whisper import WhisperModel

        def _run():
            if emit:
                emit("subtitle_model_load", {})
            model = WhisperModel(config.whisper_model, device="cpu", compute_type="int8")
            if emit:
                emit("subtitle_transcribe", {})
            # Always auto-detect the actual language.
            segments, _info = model.transcribe(video_file, language=None)
            return segments

        try:
            segments = _run()
        except Exception as e:
            msg = str(e)
            if os.name == "nt" and "WinError 1314" in msg:
                try:
                    segments = _run()
                except Exception:
                    return False
            else:
                return False

    if emit:
        emit("subtitle_write", {})

    entries: list[tuple[float, float, str]] = []
    for seg in segments:
        text = (seg.text if hasattr(seg, "text") else seg.get("text", "")).strip()
        start = seg.start if hasattr(seg, "start") else float(seg.get("start", 0))
        end = seg.end if hasattr(seg, "end") else float(seg.get("end", 0))
        entries.extend(_split_segment(start, end, text))

    if not entries:
        return False  # silent/empty transcription -> nothing to burn

    with open(srt_file, "w", encoding="utf-8") as f:
        for i, (s, e, text) in enumerate(entries, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp(s)} --> {format_timestamp(e)}\n")
            f.write(f"{text}\n\n")

    return True


def pick_hook_text(srt_file: str, max_words: int = 6) -> str:
    """Pick an engaging sentence from an SRT for the auto-hook overlay.

    Preference: sentence with '!'/'?', then one containing a hook word,
    then the first non-empty sentence. Truncated to max_words.
    """
    texts = []
    with open(srt_file, encoding="utf-8") as f:
        lines = [l.strip() for l in f]
    for i, line in enumerate(lines):
        # SRT cue text is every 4th line starting at index 2: index, time, TEXT, blank
        if i % 4 == 2 and line and not line.isdigit() and "-->" not in line:
            texts.append(line)

    if not texts:
        return ""

    def _score(t: str) -> int:
        tl = t.lower()
        s = 0
        if "!" in t or "?" in t:
            s += 3
        for w in _HOOK_WORDS:
            if w in tl:
                s += 1
                break
        return s

    best = max(texts, key=_score)
    words = best.split()
    return " ".join(words[:max_words])
