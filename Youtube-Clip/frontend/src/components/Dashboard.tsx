import { useCallback, useEffect, useRef, useState } from "react";
import {
  History as HistoryIcon,
  Languages,
  Radar,
  Scissors,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { api, type JobRecord, type Preview, type Segment } from "../api";
import { translate, type Lang } from "../i18n";
import { defaultForm, type ClipForm } from "../types";
import { useJobStream } from "../useJobStream";
import BrandMark from "./BrandMark";
import UrlBar from "./UrlBar";
import Controls from "./Controls";
import SegmentList from "./SegmentList";
import Progress from "./Progress";
import Results from "./Results";
import History from "./History";

type Tab = "create" | "history";

const segKey = (s: Segment) => `${Math.round(s.start * 1000)}:${Math.round(s.duration * 1000)}`;

function NavItem({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all duration-200"
      style={{
        background: active ? "var(--color-surface-2)" : "transparent",
        color: active ? "var(--color-ink)" : "var(--color-muted)",
        boxShadow: active ? "inset 0 0 0 1px var(--color-line)" : "none",
      }}
    >
      <span
        className="grid h-7 w-7 place-items-center rounded-lg transition-colors"
        style={{
          background: active
            ? "linear-gradient(135deg, var(--color-heat-hot), var(--color-heat-peak))"
            : "var(--color-surface-2)",
          color: active ? "#140a04" : "var(--color-faint)",
        }}
      >
        <Icon className="h-4 w-4" />
      </span>
      {label}
    </button>
  );
}

export default function Dashboard({
  lang,
  setLang,
  onHome,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  onHome: () => void;
}) {
  const t = (k: string, v?: Record<string, string | number>) => translate(lang, k, v);

  const [tab, setTab] = useState<Tab>("create");

  const [form, setForm] = useState<ClipForm>(defaultForm);
  const set = (patch: Partial<ClipForm>) => setForm((f) => ({ ...f, ...patch }));

  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [duration, setDuration] = useState<number | null>(null);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [error, setError] = useState<string>("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [viewJob, setViewJob] = useState<JobRecord | null>(null);
  const [histKey, setHistKey] = useState(0);
  const job = useJobStream(jobId);

  // when a job finishes, refresh history list
  useEffect(() => {
    if (job.status === "done" || job.status === "error") setHistKey((k) => k + 1);
  }, [job.status]);

  // debounced preview on url change
  const debTimer = useRef<number | undefined>(undefined);
  useEffect(() => {
    window.clearTimeout(debTimer.current);
    const url = form.url.trim();
    if (!url) {
      setPreview(null);
      return;
    }
    setPreviewLoading(true);
    debTimer.current = window.setTimeout(async () => {
      try {
        const r = await api.preview(url);
        setPreview(r.preview);
      } catch {
        setPreview(null);
      } finally {
        setPreviewLoading(false);
      }
    }, 500);
    return () => window.clearTimeout(debTimer.current);
  }, [form.url]);

  const busy = scanning || job.status === "running";

  async function scan() {
    setError("");
    setScanning(true);
    setScanned(false);
    setSegments([]);
    setSelected(new Set());
    try {
      const r = await api.scan(form.url.trim());
      setSegments(r.segments);
      setDuration(r.duration);
      setVideoId(r.video_id);
      setScanned(true);
      if (r.segments.length === 0) setError(t("seg.no_heatmap"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setScanning(false);
    }
  }

  const startJob = useCallback(
    async (segs?: Segment[]) => {
      setError("");
      setViewJob(null);
      try {
        const payload: Record<string, unknown> = {
          ...form,
        };
        if (segs && segs.length) payload.segments = segs;
        const r = await api.clip(payload);
        setJobId(r.job_id);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [form],
  );

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  function createSelected() {
    const chosen = segments.filter((s) => selected.has(segKey(s)));
    startJob(chosen);
  }

  const activeOutputs = viewJob ? viewJob.outputs : job.outputs;
  const activeJobId = viewJob ? viewJob.id : jobId;

  return (
    <div className="min-h-screen">
      {/* ---------- Mobile top bar ---------- */}
      <div className="sticky top-0 z-30 w-full border-b border-line bg-void/80 backdrop-blur-xl md:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <button onClick={onHome} className="flex items-center gap-2">
            <BrandMark className="h-8 w-8" />
            <span className="font-display text-sm font-extrabold tracking-tight">
              Heatmap<span className="grad-text">Clipper</span>
            </span>
          </button>
          <div className="flex rounded-xl border border-line bg-surface/80 p-0.5">
            {(["id", "en"] as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className="rounded-lg px-2 py-1 text-[11px] font-bold uppercase transition-all duration-200"
                style={{
                  background: lang === l ? "var(--color-surface-2)" : "transparent",
                  color: lang === l ? "var(--color-ink)" : "var(--color-faint)",
                }}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1 px-3 pb-3">
          {(["create", "history"] as Tab[]).map((tb) => (
            <button
              key={tb}
              onClick={() => setTab(tb)}
              className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-200"
              style={{
                background: tab === tb ? "var(--color-surface-2)" : "transparent",
                color: tab === tb ? "var(--color-ink)" : "var(--color-faint)",
                boxShadow: tab === tb ? "inset 0 0 0 1px var(--color-line)" : "none",
              }}
            >
              {tb === "create" ? (
                <Scissors className="h-3.5 w-3.5" />
              ) : (
                <HistoryIcon className="h-3.5 w-3.5" />
              )}
              {t(`nav.${tb}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-h-screen">
        {/* ---------- Sidebar (desktop) ---------- */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface/40 backdrop-blur-xl md:flex">
        <button onClick={onHome} className="flex items-center gap-2.5 px-5 pb-5 pt-6 text-left">
          <BrandMark className="h-9 w-9" />
          <span className="leading-tight">
            <span className="block font-display text-sm font-extrabold tracking-tight">
              Heatmap<span className="grad-text">Clipper</span>
            </span>
            <span className="block text-[10px] text-faint">Most Replayed → Shorts</span>
          </span>
        </button>
        <nav className="flex flex-col gap-1 px-3">
          <NavItem
            icon={Scissors}
            label={t("nav.create")}
            active={tab === "create"}
            onClick={() => setTab("create")}
          />
          <NavItem
            icon={HistoryIcon}
            label={t("nav.history")}
            active={tab === "history"}
            onClick={() => setTab("history")}
          />
        </nav>
        <div className="mt-auto p-4">
          <div className="flex rounded-xl border border-line bg-surface/80 p-1">
            <Languages className="mr-1 self-center text-faint" />
            {(["id", "en"] as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className="flex-1 rounded-lg px-2 py-1.5 text-[11px] font-bold uppercase transition-all duration-200"
                style={{
                  background: lang === l ? "var(--color-surface-2)" : "transparent",
                  color: lang === l ? "var(--color-ink)" : "var(--color-faint)",
                }}
              >
                {l}
              </button>
            ))}
          </div>
          <p className="mt-4 text-center text-[11px] text-faint">Heatmap Clipper v2.0</p>
        </div>
      </aside>

      {/* ---------- Main ---------- */}
      <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8 xl:px-10">
        {error && (
          <div
            role="alert"
            className="mb-5 flex items-start gap-3 rounded-xl border border-heat-hot/40 bg-heat-hot/10 px-4 py-3 text-sm text-heat-hot"
          >
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {tab === "create" ? (
          <div className="grid gap-5">
            <div>
              <h1 className="font-display text-2xl font-extrabold tracking-tight">{t("nav.create")}</h1>
              <p className="mt-1 text-sm text-muted">{t("app.tagline")}</p>
            </div>

            {/* Source */}
            <section
              className="card p-5 sm:p-6"
              style={{ animation: "fade-up 0.5s var(--ease-snap) both" }}
            >
              <UrlBar
                lang={lang}
                url={form.url}
                onUrl={(v) => set({ url: v })}
                preview={preview}
                loading={previewLoading}
              />
              <div className="mt-5 flex flex-wrap gap-3">
                {form.mode === "heatmap" && (
                  <button className="btn btn-ghost" onClick={scan} disabled={busy || !form.url.trim()}>
                    <Radar className="h-4 w-4" />
                    {scanning ? t("btn.scanning") : t("btn.scan")}
                  </button>
                )}
                <button
                  className="btn btn-heat"
                  onClick={() => startJob()}
                  disabled={busy || !form.url.trim()}
                >
                  <Scissors className="h-4 w-4" />
                  {t("btn.clip")}
                </button>
              </div>
            </section>

            {/* Settings + Segments */}
            <div className="grid items-start gap-5 xl:grid-cols-2">
              <section
                className="card p-5 sm:p-6"
                style={{ animation: "fade-up 0.5s var(--ease-snap) both" }}
              >
                <Controls lang={lang} form={form} set={set} />
              </section>

              {form.mode === "heatmap" ? (
                <SegmentList
                  lang={lang}
                  segments={segments}
                  duration={duration}
                  videoId={videoId}
                  selected={selected}
                  toggle={toggle}
                  selectAll={() => setSelected(new Set(segments.map(segKey)))}
                  clear={() => setSelected(new Set())}
                  onCreate={createSelected}
                  busy={busy}
                  scanning={scanning}
                  scanned={scanned}
                />
              ) : (
                <section
                  className="card p-5 sm:p-6"
                  style={{ animation: "fade-up 0.5s var(--ease-snap) both" }}
                >
                  <h2 className="label">{t("mode.custom")}</h2>
                  <p className="text-sm leading-relaxed text-muted">
                    {t("seg.no_heatmap")}
                  </p>
                  <div className="mt-4 grid gap-2 rounded-xl border border-line bg-surface-2/40 p-4 font-mono text-xs text-faint">
                    <div className="flex justify-between">
                      <span>{t("start.label")}</span>
                      <span className="text-ink">{form.start || "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("end.label")}</span>
                      <span className="text-ink">{form.end || "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("ratio.label")}</span>
                      <span className="text-ink">{form.ratio}</span>
                    </div>
                  </div>
                </section>
              )}
            </div>

            {/* Progress */}
            {(job.status !== "idle" || viewJob) && (
              <section
                className="card p-5 sm:p-6"
                style={{ animation: "fade-up 0.5s var(--ease-snap) both" }}
              >
                <Progress lang={lang} job={job} />
              </section>
            )}

            {/* Results */}
            {activeJobId && <Results lang={lang} jobId={activeJobId} outputs={activeOutputs} />}
          </div>
        ) : (
          <div className="grid gap-5">
            <div>
              <h1 className="font-display text-2xl font-extrabold tracking-tight">{t("nav.history")}</h1>
              <p className="mt-1 text-sm text-muted">{t("hist.empty")}</p>
            </div>
            <History
              lang={lang}
              reloadKey={histKey}
              onOpen={(j) => {
                setViewJob(j);
                setJobId(null);
                setTab("create");
              }}
            />
          </div>
        )}
      </main>
      </div>
    </div>
  );
}
