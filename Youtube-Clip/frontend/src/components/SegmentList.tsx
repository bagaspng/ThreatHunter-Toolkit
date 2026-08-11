import { Check, ExternalLink, ListChecks, Loader2, Scissors, X } from "lucide-react";
import { fmtTime, type Segment } from "../api";
import { heatColor } from "../heat";
import { translate, type Lang } from "../i18n";

export default function SegmentList({
  lang,
  segments,
  duration,
  videoId,
  selected,
  toggle,
  selectAll,
  clear,
  onCreate,
  busy,
  scanning,
  scanned,
}: {
  lang: Lang;
  segments: Segment[];
  duration: number | null;
  videoId: string | null;
  selected: Set<string>;
  toggle: (key: string) => void;
  selectAll: () => void;
  clear: () => void;
  onCreate: () => void;
  busy: boolean;
  scanning: boolean;
  scanned: boolean;
}) {
  const t = (k: string, v?: Record<string, string | number>) => translate(lang, k, v);
  const key = (s: Segment) => `${Math.round(s.start * 1000)}:${Math.round(s.duration * 1000)}`;
  const total = duration || (segments.length ? Math.max(...segments.map((s) => s.start + s.duration)) : 1);

  return (
    <section
      className="card p-6 sm:p-7"
      style={{ animation: "fade-up 0.5s var(--ease-snap) both" }}
    >
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-muted">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{
              background: heatColor(0.9),
              boxShadow: `0 0 10px ${heatColor(0.9)}`,
              animation: "pulse-glow 2.4s ease-in-out infinite",
            }}
          />
          {t("seg.title")}
        </h2>
        {segments.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="mr-1 font-mono text-xs text-muted">
              {t("seg.selected", { count: selected.size })}
            </span>
            <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={selectAll} disabled={busy}>
              <ListChecks className="h-3.5 w-3.5" />
              {t("seg.selectall")}
            </button>
            <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={clear} disabled={busy}>
              <X className="h-3.5 w-3.5" />
              {t("seg.clear")}
            </button>
            <button
              className="btn btn-heat px-3 py-1.5 text-xs"
              onClick={onCreate}
              disabled={busy || selected.size === 0}
            >
              <Scissors className="h-3.5 w-3.5" />
              {t("seg.create")}
            </button>
          </div>
        )}
      </header>

      {scanning ? (
        <div className="flex flex-col items-center gap-3 py-10">
          <Loader2 className="h-6 w-6 animate-spin text-heat-hot" />
          <p className="text-center text-sm text-muted">{t("seg.scanning")}</p>
        </div>
      ) : segments.length === 0 ? (
        <p className="py-8 text-center text-sm text-faint">
          {scanned ? t("seg.no_heatmap") : t("seg.empty")}
        </p>
      ) : (
        <>
          {/* timeline heat ribbon — the signature */}
          <div className="relative mb-5 h-10 overflow-hidden rounded-lg border border-line bg-void">
            {segments.map((s) => {
              const left = (s.start / total) * 100;
              const width = Math.max(0.6, (s.duration / total) * 100);
              return (
                <div
                  key={key(s)}
                  title={`${fmtTime(s.start)} · ${Math.round(s.score * 100)}%`}
                  className="absolute top-0 h-full cursor-pointer transition-opacity hover:opacity-100"
                  style={{
                    left: `${left}%`,
                    width: `${width}%`,
                    background: heatColor(s.score),
                    opacity: selected.has(key(s)) ? 1 : 0.35 + s.score * 0.4,
                    boxShadow: `0 0 ${6 + s.score * 14}px ${heatColor(s.score)}`,
                  }}
                  onClick={() => toggle(key(s))}
                />
              );
            })}
          </div>

          <ul className="grid gap-2">
            {segments.map((s, i) => {
              const k = key(s);
              const on = selected.has(k);
              const col = heatColor(s.score);
              return (
                <li key={k}>
                  <div
                    className="card-hover flex items-center gap-3 rounded-xl border p-3 transition-colors"
                    style={{
                      borderColor: on ? col : "var(--color-line)",
                      background: on
                        ? "color-mix(in srgb, " + col + " 10%, transparent)"
                        : "color-mix(in srgb, var(--color-surface) 60%, transparent)",
                    }}
                  >
                    <button
                      role="checkbox"
                      aria-checked={on}
                      onClick={() => toggle(k)}
                      className="grid h-6 w-6 shrink-0 place-items-center rounded-md border transition-all duration-150"
                      style={{
                        borderColor: on ? col : "var(--color-faint)",
                        background: on ? col : "transparent",
                        boxShadow: on ? `0 0 12px ${col}` : "none",
                      }}
                    >
                      {on && <Check className="h-3.5 w-3.5 text-[#140a04]" strokeWidth={3} />}
                    </button>
                    <span className="w-6 text-center font-mono text-xs text-faint">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-sm">
                        {fmtTime(s.start)} <span className="text-faint">→</span>{" "}
                        {fmtTime(s.start + s.duration)}
                      </div>
                      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
                        <div className="h-full rounded-full" style={{ width: `${s.score * 100}%`, background: col }} />
                      </div>
                    </div>
                    <span className="shrink-0 font-mono text-xs" style={{ color: col }}>
                      {Math.round(s.score * 100)}%
                    </span>
                    {videoId && (
                      <a
                        className="icon-btn h-8 w-8"
                        href={`https://www.youtube.com/watch?v=${videoId}&t=${Math.floor(s.start)}s`}
                        target="_blank"
                        rel="noreferrer"
                        title={t("seg.preview")}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
