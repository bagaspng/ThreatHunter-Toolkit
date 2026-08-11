import { Link, Loader2, Play, User } from "lucide-react";
import { fmtTime, type Preview } from "../api";
import { translate, type Lang } from "../i18n";

export default function UrlBar({
  lang,
  url,
  onUrl,
  preview,
  loading,
}: {
  lang: Lang;
  url: string;
  onUrl: (v: string) => void;
  preview: Preview | null;
  loading: boolean;
}) {
  const t = (k: string) => translate(lang, k);
  return (
    <div className="grid gap-4">
      <div>
        <label className="label" htmlFor="url">
          {t("url.label")}
        </label>
        <div className="relative">
          <Link className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            id="url"
            className="field text-base pl-10!"
            placeholder={t("url.ph")}
            value={url}
            onChange={(e) => onUrl(e.target.value)}
          />
        </div>
        <p className="hint">{t("url.hint")}</p>
      </div>

      {(loading || preview) && (
        <div className="flex items-center gap-4 rounded-xl border border-line bg-surface-2/40 p-3">
          {preview?.thumbnail ? (
            <div className="relative h-16 w-28 shrink-0 overflow-hidden rounded-lg">
              <img src={preview.thumbnail} alt="" className="h-full w-full object-cover" />
              {preview.duration != null && (
                <span className="absolute bottom-1 right-1 rounded bg-black/75 px-1 py-px font-mono text-[10px] text-white">
                  {fmtTime(preview.duration)}
                </span>
              )}
            </div>
          ) : (
            <div className="skeleton h-16 w-28 shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            {loading && !preview ? (
              <div className="flex items-center gap-2 text-sm text-faint">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {t("preview.loading")}
              </div>
            ) : (
              <>
                <div className="flex items-center gap-1.5">
                  <Play className="h-3.5 w-3.5 shrink-0 fill-current text-heat-hot" />
                  <span className="truncate text-sm font-semibold">{preview?.title}</span>
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
                  <User className="h-3 w-3 shrink-0" />
                  <span className="truncate">{preview?.uploader}</span>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
