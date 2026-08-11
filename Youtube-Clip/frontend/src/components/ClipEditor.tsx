import { useEffect, useRef, useState } from "react";
import { Pause, Play, SkipBack, SkipForward, Wand2, X } from "lucide-react";
import { api } from "../api";
import { translate, type Lang } from "../i18n";

interface EditorProps {
  lang: Lang;
  jobId: string;
  clipName: string;      // e.g. "clip_1.mp4"
  clipIndex: number;     // 1-based
  onClose: () => void;
  onSaved: () => void;
}

const fmt = (s: number) => {
  if (!isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
};

export default function ClipEditor({ lang, jobId, clipName, clipIndex, onClose, onSaved }: EditorProps) {
  const t = (k: string, vars?: Record<string, string | number>) => translate(lang, k, vars);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dur, setDur] = useState(0);
  const [playhead, setPlayhead] = useState(0);
  const [hookText, setHookText] = useState("auto");
  const [ratio, setRatio] = useState("9:16");
  const [params, setParams] = useState({
    trim_start_offset: 0.0,
    trim_end_offset: 0.0,
    crop: "default",
    crop_cx: 0.5,
  });
  const videoRef = useRef<HTMLVideoElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<"start" | "end" | "playhead" | null>(null);
  const boundsRef = useRef({ start: 0, end: 0 });

  // effective in-clip trim positions (seconds) — start in [0,dur], end in [start,dur]
  const startSec = Math.max(0, Math.min(params.trim_start_offset, dur));
  const endSec = Math.max(startSec, Math.min(dur + params.trim_end_offset, dur));
  boundsRef.current = { start: startSec, end: endSec };

  const pct = (s: number) => (dur > 0 ? (Math.max(0, Math.min(s, dur)) / dur) * 100 : 0);

  // realtime CSS preview of ratio + crop
  const isSplit = params.crop !== "default";
  const showCropPos = !isSplit && ratio !== "original";
  const ratioAspect = ratio === "original" ? "16/9" : ratio.replace(":", "/");
  const ratioStyle = { aspectRatio: ratioAspect };
  const cropPreview = isSplit || ratio === "original" ? "contain" : "cover";

  const seekTo = (s: number) => {
    const v = videoRef.current;
    if (v) v.currentTime = Math.max(0, Math.min(s, dur));
    setPlayhead(s);
  };

  const posToSec = (clientX: number) => {
    const el = trackRef.current;
    if (!el || dur <= 0) return 0;
    const rect = el.getBoundingClientRect();
    return ((clientX - rect.left) / rect.width) * dur;
  };

  const onPointerDown = (e: React.PointerEvent, kind: "start" | "end" | "playhead") => {
    e.preventDefault();
    dragRef.current = kind;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const kind = dragRef.current;
    if (!kind) return;
    const sec = posToSec(e.clientX);
    if (kind === "start") {
      setParams((p) => ({ ...p, trim_start_offset: Math.round(sec * 10) / 10 }));
      seekTo(sec);
    } else if (kind === "end") {
      setParams((p) => ({ ...p, trim_end_offset: Math.round((sec - dur) * 10) / 10 }));
      seekTo(sec);
    } else {
      seekTo(sec);
    }
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      const { start, end } = boundsRef.current;
      if (v.currentTime < start || v.currentTime > end) v.currentTime = start;
      v.play();
    } else v.pause();
  };

  useEffect(() => {
    videoRef.current?.load();
  }, [clipName]);

  // Prefill editor from the original job's settings so ratio/crop/hook
  // aren't silently reset to defaults on edit. Ratio & subtitle follow the
  // job — they can't change here (ratio is fixed from the start).
  useEffect(() => {
    let cancelled = false;
    api
      .job(jobId)
      .then(({ job }) => {
        if (cancelled) return;
        const r = job.request ?? {};
        setRatio(typeof r.ratio === "string" && r.ratio ? r.ratio : "9:16");
        setParams((p) => ({
          ...p,
          crop: typeof r.crop === "string" && r.crop ? r.crop : p.crop,
        }));
        if (typeof r.hook_text === "string") setHookText(r.hook_text);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const onMeta = () => setDur(v.duration || 0);
    const onTime = () => {
      if (dragRef.current !== "playhead") setPlayhead(v.currentTime);
      if (!v.paused) {
        const { start, end } = boundsRef.current;
        if (v.currentTime < start) v.currentTime = start;
        else if (v.currentTime > end) {
          v.currentTime = start;
          v.pause();
        }
      }
    };
    v.addEventListener("loadedmetadata", onMeta);
    v.addEventListener("timeupdate", onTime);
    return () => {
      v.removeEventListener("loadedmetadata", onMeta);
      v.removeEventListener("timeupdate", onTime);
    };
  }, [clipName]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === " ") {
        e.preventDefault();
        togglePlay();
      }
      if (e.key === "ArrowLeft") seekTo(playhead - 5);
      if (e.key === "ArrowRight") seekTo(playhead + 5);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playhead, dur]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(api.editUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          job_id: jobId,
          clip_index: clipIndex,
          trim_start_offset: params.trim_start_offset,
          trim_end_offset: params.trim_end_offset,
          crop: params.crop,
          crop_cx: params.crop_cx,
          hook_text: hookText.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      await res.json();
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal re-render");
    } finally {
      setLoading(false);
    }
  };

  const clipLen = Math.max(0, endSec - startSec);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <div className="bg-surface rounded-2xl border border-line shadow-[var(--shadow-lift)] w-full max-w-5xl max-h-[92vh] overflow-hidden flex flex-col" style={{ animation: "fade-up 0.3s var(--ease-snap) both" }}>
        {/* Header */}
        <header className="flex items-center justify-between p-4 border-b border-line">
          <h2 className="text-lg font-bold">
            {t("editor.title")} <span className="font-mono text-faint text-sm">{clipName}</span>
          </h2>
          <button className="icon-btn" onClick={onClose} disabled={loading} aria-label={t("btn.cancel")}>
            <X className="h-4 w-4" />
          </button>
        </header>

        {/* Body */}
        <div className="flex flex-col lg:flex-row overflow-y-auto lg:overflow-hidden">
          {/* ---------- Preview side ---------- */}
          <div className="lg:w-[55%] flex flex-col gap-3 p-4 lg:p-5 bg-void border-b lg:border-b-0 lg:border-r border-line overflow-y-auto lg:max-h-[calc(92vh-64px)]">
            <div className="relative mx-auto w-full max-w-[420px] shrink-0 overflow-hidden rounded-2xl bg-black ring-1 ring-line" style={ratioStyle}>
              <video
                ref={videoRef}
                className="absolute inset-0 h-full w-full"
                style={{ objectFit: cropPreview }}
                src={api.clipSourceUrl(jobId, clipIndex)}
                playsInline
                preload="metadata"
              />
              {/* big play/pause toggle on click */}
              <button
                type="button"
                className="absolute inset-0 z-0 flex items-center justify-center bg-black/0 text-white/0 transition hover:bg-black/30 hover:text-white/90"
                onClick={togglePlay}
                aria-label="Play / pause"
              >
                {videoRef.current && !videoRef.current.paused ? (
                  <Pause className="h-10 w-10" fill="currentColor" />
                ) : (
                  <Play className="ml-1 h-10 w-10" fill="currentColor" />
                )}
              </button>
              {/* manual crop position guide */}
              {showCropPos && (
                <div
                  className="pointer-events-none absolute inset-y-0 z-20 w-0.5 bg-white/80"
                  style={{ left: `${params.crop_cx * 100}%` }}
                />
              )}
            </div>

            {/* transport + timecode */}
            <div className="mx-auto flex w-full max-w-[420px] items-center gap-3">
              <button type="button" className="icon-btn" onClick={() => seekTo(playhead - 10)} title="-10s">
                <SkipBack className="h-4 w-4" />
              </button>
              <button
                type="button"
                className="btn btn-heat px-5 py-2"
                onClick={togglePlay}
                aria-label="Play / pause"
              >
                {videoRef.current && !videoRef.current.paused ? (
                  <Pause className="h-4 w-4" fill="currentColor" />
                ) : (
                  <Play className="ml-0.5 h-4 w-4" fill="currentColor" />
                )}
              </button>
              <button type="button" className="icon-btn" onClick={() => seekTo(playhead + 10)} title="+10s">
                <SkipForward className="h-4 w-4" />
              </button>
              <div className="ml-auto font-mono text-xs text-muted">
                <span className="text-ink">{fmt(playhead)}</span>
                {" / "}
                {fmt(dur)}
              </div>
            </div>
          </div>

          {/* ---------- Controls side ---------- */}
          <form onSubmit={handleSubmit} className="lg:w-[45%] p-4 lg:p-5 flex flex-col gap-5 overflow-y-auto lg:max-h-[calc(92vh-64px)]">
            {error && <div className="text-sm text-heat-hot bg-heat-hot/10 p-3 rounded-xl">{error}</div>}

            {/* ---- Timeline ---- */}
            <div>
              <h3 className="label !mb-0">{t("editor.timeline")}</h3>

              <div
                ref={trackRef}
                className="relative mt-2 h-16 overflow-hidden rounded-xl bg-void border border-line select-none touch-none cursor-pointer"
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerDown={(e) => {
                  if (e.target === e.currentTarget) onPointerDown(e, "playhead");
                }}
              >
                {/* dimmed area outside trimmed region */}
                {startSec > 0 && (
                  <div className="absolute inset-y-0 left-0 bg-black/50" style={{ width: `${pct(startSec)}%` }} />
                )}
                {endSec < dur && (
                  <div className="absolute inset-y-0 right-0 bg-black/50" style={{ width: `${pct(dur) - pct(endSec)}%` }} />
                )}
                {/* trimmed region */}
                <div
                  className="absolute top-0 bottom-0 bg-heat-hot/25"
                  style={{ left: `${pct(startSec)}%`, width: `${pct(endSec) - pct(startSec)}%` }}
                />
                {/* tick marks */}
                {Array.from({ length: Math.min(24, Math.max(4, Math.floor(dur / 5))) }).map((_, i) => (
                  <div key={i} className="absolute top-1 bottom-1 w-px bg-white/10"
                    style={{ left: `${(i / Math.max(1, Math.floor(dur / 5))) * 100}%` }} />
                ))}
                {/* start handle */}
                <div
                  className="absolute top-0 bottom-0 w-4 -ml-2 bg-white cursor-ew-resize rounded-md flex flex-col items-center justify-center gap-0.5 shadow"
                  style={{ left: `${pct(startSec)}%` }}
                  onPointerDown={(e) => { e.stopPropagation(); onPointerDown(e, "start"); }}
                >
                  <div className="w-1.5 h-0.5 bg-black/60" />
                  <div className="w-1.5 h-0.5 bg-black/60" />
                </div>
                {/* end handle */}
                <div
                  className="absolute top-0 bottom-0 w-4 -ml-2 bg-white cursor-ew-resize rounded-md flex flex-col items-center justify-center gap-0.5 shadow"
                  style={{ left: `${pct(endSec)}%` }}
                  onPointerDown={(e) => { e.stopPropagation(); onPointerDown(e, "end"); }}
                >
                  <div className="w-1.5 h-0.5 bg-black/60" />
                  <div className="w-1.5 h-0.5 bg-black/60" />
                </div>
                {/* playhead */}
                <div className="absolute top-0 bottom-0 w-0.5 bg-heat-peak z-10" style={{ left: `${pct(playhead)}%` }} />
                <div
                  className="absolute w-0 h-0 border-l-[6px] border-r-[6px] border-t-[7px] border-l-transparent border-r-transparent border-t-heat-peak z-10"
                  style={{ left: `${pct(playhead)}%`, transform: "translateX(-50%)" }}
                />
              </div>

              <div className="mt-2 flex items-center justify-between font-mono text-[11px] text-faint">
                <span>{fmt(startSec)}</span>
                <span className="rounded-full bg-surface-2 px-2 py-0.5 text-ink">
                  {t("editor.time_clip")}: {fmt(clipLen)}
                </span>
                <span>{fmt(endSec)}</span>
              </div>
              <p className="hint">{t("editor.trim_hint")}</p>
            </div>

            {/* ---- Crop ---- */}
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex items-center gap-2">
                <span className="label shrink-0 !mb-0">{t("editor.crop")}</span>
                <select
                  className="field flex-1"
                  value={params.crop}
                  onChange={(e) => setParams({ ...params, crop: e.target.value })}
                >
                  <option value="default">{t("crop.default")}</option>
                  <option value="split_left">{t("crop.split_left")}</option>
                  <option value="split_right">{t("crop.split_right")}</option>
                </select>
              </label>
              <div className="flex items-center">
                <span className="label shrink-0 !mb-0">{t("editor.ratio")}</span>
                <span className="ml-2 rounded-full bg-surface-2 px-2.5 py-1 font-mono text-xs text-muted">{ratio}</span>
              </div>
            </div>

            {/* ---- Manual crop position ---- */}
            <div className={showCropPos ? "" : "pointer-events-none opacity-40"}>
              <div className="flex items-center justify-between">
                <span className="label !mb-0">{t("editor.crop_pos")}</span>
                <span className="font-mono text-[11px] text-faint">
                  {t("editor.crop_left")} · {t("editor.crop_center")} · {t("editor.crop_right")}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(params.crop_cx * 100)}
                disabled={!showCropPos}
                onChange={(e) => setParams({ ...params, crop_cx: Number(e.target.value) / 100 })}
                className="slider w-full"
                style={{
                  background: `linear-gradient(90deg, var(--color-heat-hot) ${Math.round(params.crop_cx * 100)}%, var(--color-line) ${Math.round(params.crop_cx * 100)}%)`,
                }}
              />
              <p className="hint">{t("editor.crop_pos_hint")}</p>
            </div>

            {/* ---- Hook text ---- */}
            <div>
              <label className="label">{t("editor.hook_text")}</label>
              <input
                type="text"
                className="field"
                value={hookText}
                placeholder="auto"
                onChange={(e) => setHookText(e.target.value)}
              />
              <p className="hint">{t("editor.hook_text_hint")}</p>
            </div>

            {/* ---- Actions ---- */}
            <div className="flex gap-3 pt-2 mt-auto">
              <button type="button" className="btn btn-ghost flex-1" onClick={onClose} disabled={loading}>
                {t("btn.cancel")}
              </button>
              <button type="submit" className="btn btn-heat flex-1" disabled={loading}>
                <Wand2 className="h-4 w-4" />
                {loading ? t("editor.rendering") : t("editor.render")}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
