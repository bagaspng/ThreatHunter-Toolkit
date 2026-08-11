import { useEffect, useRef, useState } from "react";
import { Captions, CheckCircle2, Crop, Download, Flame, Loader2, Package, Scissors, TriangleAlert, type LucideIcon } from "lucide-react";
import { translate, type Lang } from "../i18n";
import type { JobStreamState } from "../useJobStream";

// Stages shown in breadcrumb pills (per-clip phase)
const CLIP_STAGES = ["trim", "crop", "subtitle", "burn_subtitle", "finalize"];
const PCT_STAGES = new Set(["download", "trim", "crop", "burn_subtitle", "subtitle_transcribe"]);

const STAGE_ICONS: Record<string, LucideIcon> = {
  download: Download,
  trim: Scissors,
  crop: Crop,
  subtitle: Captions,
  subtitle_transcribe: Captions,
  burn_subtitle: Flame,
  finalize: Package,
};

export default function Progress({ lang, job }: { lang: Lang; job: JobStreamState }) {
  const t = (k: string, v?: Record<string, string | number>) => translate(lang, k, v);

  // Elapsed timer — resets on new clip or phase change
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number>(Date.now());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (job.status === "running") {
      startRef.current = Date.now();
      setElapsed(0);
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [job.status, job.currentIndex, job.phase]);

  if (job.status === "idle") {
    return <p className="py-6 text-center text-sm text-faint">{t("prog.idle")}</p>;
  }

  const isDownloadPhase = job.phase === "download" || (job.stage === "download" && job.currentIndex === 0);
  const stageLabel = job.stage ? t(`stage.${job.stage}`) : "";
  const StageIcon = job.stage ? STAGE_ICONS[job.stage] : undefined;
  const hasStagePct = job.stagePct != null && PCT_STAGES.has(job.stage);

  // Overall progress: download phase = 0–20%, clips = 20–100%
  const overallPct = (() => {
    if (job.status === "done") return 100;
    if (isDownloadPhase) {
      return job.stagePct != null ? Math.round(job.stagePct * 0.2) : 5;
    }
    if (job.total > 0) {
      const clipsDone = job.currentIndex - 1;
      return Math.max(20, Math.min(99, Math.round(20 + (clipsDone / job.total) * 80)));
    }
    return 0;
  })();

  const fmtElapsed = elapsed >= 60
    ? `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`
    : `${elapsed}s`;

  const showHint = job.stage === "download" && elapsed >= 10;

  return (
    <div className="grid gap-4">
      {/* Header */}
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-semibold">
          {job.status === "done" && <CheckCircle2 className="h-4 w-4 text-heat-peak" />}
          {job.status === "error" && <TriangleAlert className="h-4 w-4 text-heat-hot" />}
          {job.status === "running" && <Loader2 className="h-4 w-4 animate-spin text-heat-hot" />}
          {job.status === "done"
            ? t("prog.done", { success: job.success })
            : job.status === "error"
              ? t("stage.error")
              : isDownloadPhase
                ? t("prog.downloading")
                : job.total > 0
                  ? t("prog.clip", { i: job.currentIndex, n: job.total })
                  : "…"}
        </span>
        <div className="flex items-center gap-3">
          {job.status === "running" && elapsed > 0 && (
            <span className="font-mono text-xs text-faint">{fmtElapsed}</span>
          )}
          {job.stage === "download" && job.speedKb != null && (
            <span className="font-mono text-xs text-muted">{job.speedKb} KB/s</span>
          )}
        </div>
      </div>

      {/* Overall progress bar */}
      <div>
        <div className="mb-1 flex justify-between text-[11px] text-faint">
          <span>{t("prog.overall")}</span>
          <span>{overallPct}%</span>
        </div>
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${overallPct}%`,
              background: job.status === "error"
                ? "var(--color-heat-hot)"
                : "linear-gradient(90deg, var(--color-heat-cool), var(--color-heat-hot), var(--color-heat-peak))",
              boxShadow: job.status !== "error" ? "0 0 12px rgba(244, 63, 94, 0.5)" : "none",
            }}
          />
        </div>
      </div>

      {/* Current stage progress bar */}
      {job.status === "running" && stageLabel && (
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-semibold">
              {StageIcon && <StageIcon className="h-3.5 w-3.5 text-heat-hot" />}
              {stageLabel}
            </span>
            {hasStagePct && (
              <span className="font-mono text-xs text-muted">{job.stagePct}%</span>
            )}
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-line">
            {hasStagePct ? (
              <div
                className="h-full rounded-full transition-all duration-200"
                style={{
                  width: `${job.stagePct}%`,
                  background: "linear-gradient(90deg, var(--color-heat-cool), var(--color-heat-hot))",
                }}
              />
            ) : (
              <div
                className="h-full w-1/3 rounded-full"
                style={{
                  background: "linear-gradient(90deg, transparent, var(--color-heat-hot), transparent)",
                  animation: "shimmer 1.5s ease-in-out infinite",
                }}
              />
            )}
          </div>
          {showHint && (
            <p className="mt-1.5 text-xs text-faint">{t("stage.download.hint")}</p>
          )}
        </div>
      )}

      {/* Per-clip stage pills — only in clips phase */}
      {job.status === "running" && !isDownloadPhase && (
        <div className="flex flex-wrap gap-1.5">
          {CLIP_STAGES.map((s) => {
            const active = job.stage === s || job.stage.startsWith(s + "_");
            const pct = active && hasStagePct ? job.stagePct : null;
            const Icon = STAGE_ICONS[s];
            return (
              <span
                key={s}
                className="flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[11px] transition-colors"
                style={{
                  borderColor: active ? "var(--color-heat-hot)" : "var(--color-line)",
                  color: active ? "var(--color-heat-peak)" : "var(--color-faint)",
                  background: active && pct != null
                    ? `linear-gradient(90deg, color-mix(in srgb, var(--color-heat-hot) 20%, transparent) ${pct}%, transparent ${pct}%)`
                    : undefined,
                }}
              >
                {Icon && <Icon className="h-3 w-3" />}
                {t(`stage.${s}`)}
                {active && pct != null && ` ${pct}%`}
              </span>
            );
          })}
        </div>
      )}

      {job.error && (
        <p className="flex items-center gap-1.5 text-xs" style={{ color: "var(--color-heat-hot)" }}>
          <TriangleAlert className="h-3.5 w-3.5" />
          {job.error}
        </p>
      )}
    </div>
  );
}
