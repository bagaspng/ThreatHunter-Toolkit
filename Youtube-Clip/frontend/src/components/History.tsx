import { useEffect, useState } from "react";
import { Archive, CheckCircle2, Clock, ExternalLink, History as HistoryIcon, Loader2, Trash2, XCircle } from "lucide-react";
import { api, fmtTime, type JobRecord } from "../api";
import { translate, type Lang } from "../i18n";

const STATUS_META: Record<string, { color: string; Icon: typeof Clock }> = {
  done: { color: "var(--color-heat-peak)", Icon: CheckCircle2 },
  running: { color: "var(--color-heat-cool)", Icon: Loader2 },
  error: { color: "var(--color-heat-hot)", Icon: XCircle },
  queued: { color: "var(--color-muted)", Icon: Clock },
};

export default function History({
  lang,
  onOpen,
  reloadKey,
}: {
  lang: Lang;
  onOpen: (job: JobRecord) => void;
  reloadKey: number;
}) {
  const t = (k: string) => translate(lang, k);
  const [jobs, setJobs] = useState<JobRecord[]>([]);

  const load = () => api.jobs().then((r) => setJobs(r.jobs)).catch(() => {});
  useEffect(() => {
    load();
  }, [reloadKey]);

  async function del(id: string) {
    await api.deleteJob(id);
    load();
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16">
        <div className="grid h-12 w-12 place-items-center rounded-2xl border border-line bg-surface-2/50">
          <HistoryIcon className="h-5 w-5 text-faint" />
        </div>
        <p className="text-sm text-faint">{t("hist.empty")}</p>
      </div>
    );
  }

  return (
    <ul className="grid gap-2.5">
      {jobs.map((j) => {
        const meta = STATUS_META[j.status] ?? STATUS_META.queued;
        const StatusIcon = meta.Icon;
        return (
          <li key={j.id} className="card card-hover flex items-center gap-4 p-4">
            <span className="relative shrink-0">
              <StatusIcon
                className={`h-4 w-4 ${j.status === "running" ? "animate-spin" : ""}`}
                style={{ color: meta.color, filter: `drop-shadow(0 0 6px ${meta.color})` }}
              />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold">{j.title || j.id}</div>
              <div className="mt-0.5 flex items-center gap-3 font-mono text-xs text-faint">
                <span>{new Date(j.created_at).toLocaleString()}</span>
                <span style={{ color: meta.color }}>{j.status}</span>
                <span>{j.outputs.length} clip</span>
              </div>
            </div>
            {j.outputs.length > 0 && (
              <>
                <a
                  className="icon-btn h-8 w-8"
                  href={api.zipUrl(j.id)}
                  title=".zip"
                  aria-label=".zip"
                >
                  <Archive className="h-3.5 w-3.5" />
                </a>
                <button
                  className="btn btn-ghost px-3 py-1.5 text-xs"
                  onClick={() => onOpen(j)}
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  {t("hist.open")}
                </button>
              </>
            )}
            <button
              className="icon-btn h-8 w-8"
              style={{ color: "var(--color-heat-hot)" }}
              onClick={() => del(j.id)}
              title={t("hist.delete")}
              aria-label={t("hist.delete")}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export { fmtTime };
