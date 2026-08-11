import { useState } from "react";
import { Archive, Download, Film, Pencil } from "lucide-react";
import { api, type JobOutput } from "../api";
import { translate, type Lang } from "../i18n";
import ClipEditor from "./ClipEditor";

export default function Results({
  lang,
  jobId,
  outputs,
}: {
  lang: Lang;
  jobId: string;
  outputs: JobOutput[];
}) {
  const t = (k: string) => translate(lang, k);
  const [editing, setEditing] = useState<string | null>(null);
  const [edited, setEdited] = useState<string[]>([]);
  if (outputs.length === 0) return null;

  const clipIndex = (name: string) => parseInt(name.split("_")[1] ?? "1", 10);
  const all = Array.from(new Set([...outputs.map((o) => o.name), ...edited]));
  const editingIndex = editing ? clipIndex(editing) : 1;

  return (
    <section
      className="card p-6 sm:p-7"
      style={{ animation: "fade-up 0.5s var(--ease-snap) both" }}
    >
      <header className="mb-5 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-muted">
          <Film className="h-4 w-4 text-heat-hot" />
          {t("result.title")}
        </h2>
        {outputs.length > 1 && (
          <a className="btn btn-heat px-3 py-1.5 text-xs" href={api.zipUrl(jobId)}>
            <Archive className="h-3.5 w-3.5" />
            {t("result.zip")}
          </a>
        )}
      </header>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {all.map((name) => (
          <figure
            key={name}
            className="card-hover group overflow-hidden rounded-xl border border-line bg-void"
          >
            <div className="relative">
              <video
                className="aspect-[9/16] w-full bg-black object-contain transition-transform duration-300 group-hover:scale-[1.01]"
                src={api.clipUrl(jobId, name)}
                controls
                playsInline
                preload="metadata"
              />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-end gap-1.5 bg-gradient-to-t from-black/85 to-transparent p-2 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                <button
                  className="icon-btn bg-black/50"
                  onClick={() => setEditing(name)}
                  title={t("result.edit")}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <a
                  className="icon-btn bg-black/50"
                  href={api.clipUrl(jobId, name)}
                  download
                  title={t("result.download")}
                >
                  <Download className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>
            <figcaption className="flex items-center justify-between gap-2 p-2.5">
              <span className="truncate font-mono text-xs text-muted">{name}</span>
              <span className="flex shrink-0 gap-1">
                <button
                  className="icon-btn h-7 w-7"
                  onClick={() => setEditing(name)}
                  title={t("result.edit")}
                >
                  <Pencil className="h-3 w-3" />
                </button>
                <a
                  className="icon-btn h-7 w-7"
                  href={api.clipUrl(jobId, name)}
                  download
                  title={t("result.download")}
                >
                  <Download className="h-3 w-3" />
                </a>
              </span>
            </figcaption>
          </figure>
        ))}
      </div>

      {editing && (
        <ClipEditor
          lang={lang}
          jobId={jobId}
          clipName={editing}
          clipIndex={editingIndex}
          onClose={() => setEditing(null)}
          onSaved={() => {
            const editedName = `clip_${editingIndex}_edited.mp4`;
            setEdited((prev) => (prev.includes(editedName) ? prev : [...prev, editedName]));
            setEditing(null);
          }}
        />
      )}
    </section>
  );
}
