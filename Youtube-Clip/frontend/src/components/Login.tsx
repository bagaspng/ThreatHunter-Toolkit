import { useState } from "react";
import { ArrowLeft, Loader2, Lock, LogIn, TriangleAlert } from "lucide-react";
import { api } from "../api";
import { translate, type Lang } from "../i18n";
import BrandMark from "./BrandMark";

export default function Login({
  lang,
  onDone,
  onBack,
}: {
  lang: Lang;
  onDone: () => void;
  onBack?: () => void;
}) {
  const t = (k: string) => translate(lang, k);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(false);
    try {
      await api.login(pw);
      onDone();
    } catch {
      setErr(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative z-10 grid min-h-screen place-items-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <BrandMark className="h-14 w-14" />
          <div className="font-display text-xl font-extrabold tracking-tight">
            Heatmap<span className="grad-text">Clipper</span>
          </div>
        </div>

        <form onSubmit={submit} className="glass p-8 shadow-[var(--shadow-card)]">
          <div className="mb-1 text-lg font-bold">{t("login.title")}</div>
          <p className="mb-6 text-sm text-muted">{t("login.desc")}</p>
          <label className="label" htmlFor="pw">
            {t("login.password")}
          </label>
          <div className="relative">
            <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              id="pw"
              type="password"
              className="field pl-10!"
              value={pw}
              autoFocus
              onChange={(e) => setPw(e.target.value)}
            />
          </div>
          {err && (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs leading-relaxed text-heat-hot">
              <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
              {t("login.error")}
            </p>
          )}
          <button className="btn btn-heat mt-5 w-full" disabled={busy || !pw}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
            {t("login.submit")}
          </button>
        </form>
        {onBack && (
          <button
            onClick={onBack}
            className="mx-auto mt-5 flex items-center gap-1.5 text-xs text-faint transition-colors hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t("login.back")}
          </button>
        )}
      </div>
    </div>
  );
}
