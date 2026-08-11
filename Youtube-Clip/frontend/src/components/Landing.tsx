import {
  ArrowRight,
  Captions,
  Check,
  Flame,
  Languages,
  Magnet,
  Package,
  Play,
  Radar,
  ScanFace,
  Scissors,
  type LucideIcon,
} from "lucide-react";
import { heatColor } from "../heat";
import { translate, type Lang } from "../i18n";
import BrandMark from "./BrandMark";

const FEATURES: { icon: LucideIcon; title: string; desc: string }[] = [
  { icon: Radar, title: "land.f.heat.title", desc: "land.f.heat.desc" },
  { icon: ScanFace, title: "land.f.crop.title", desc: "land.f.crop.desc" },
  { icon: Captions, title: "land.f.sub.title", desc: "land.f.sub.desc" },
  { icon: Magnet, title: "land.f.hook.title", desc: "land.f.hook.desc" },
  { icon: Scissors, title: "land.f.trim.title", desc: "land.f.trim.desc" },
  { icon: Package, title: "land.f.export.title", desc: "land.f.export.desc" },
];

const STEPS = ["land.how.1", "land.how.2", "land.how.3"] as const;

function PhoneMockup() {
  const bars = [0.3, 0.8, 0.5, 0.95, 0.7, 0.4, 0.9, 0.6];
  return (
    <div className="relative mx-auto w-[250px]">
      <div className="rounded-[2.2rem] border border-white/15 bg-surface p-2 shadow-[var(--shadow-lift)]">
        <div className="relative aspect-[9/19] overflow-hidden rounded-[1.7rem] bg-black">
          <div className="absolute inset-0 bg-gradient-to-br from-heat-cool/50 via-heat-warm/40 to-heat-hot/50" />
          <div className="absolute inset-x-3 top-3 h-5 w-24 rounded-md bg-white/10 backdrop-blur" />
          <div className="absolute inset-0 grid place-items-center">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-white/20 text-white backdrop-blur-sm">
              <Play className="ml-0.5 h-5 w-5 fill-current" />
            </span>
          </div>
          <div className="absolute inset-x-3 bottom-12 flex h-9 items-end gap-1 rounded-lg bg-black/45 p-1.5 backdrop-blur-sm">
            {bars.map((b, i) => (
              <div
                key={i}
                className="flex-1 rounded-sm transition-all"
                style={{ height: `${b * 100}%`, background: heatColor(b), boxShadow: `0 0 8px ${heatColor(b)}` }}
              />
            ))}
          </div>
          <div className="absolute inset-x-3 bottom-2.5 text-center">
            <span className="rounded-md bg-black/65 px-2 py-1 text-[10px] font-semibold text-white backdrop-blur">
              momen paling seru 🔥
            </span>
          </div>
        </div>
      </div>
      <div className="chip absolute -left-10 top-10">
        <Flame className="h-3.5 w-3.5" style={{ color: "var(--color-heat-hot)" }} /> 92%
      </div>
      <div className="chip absolute -right-8 bottom-24">
        <Check className="h-3.5 w-3.5" style={{ color: "var(--color-heat-peak)" }} /> Smart Crop
      </div>
    </div>
  );
}

export default function Landing({
  lang,
  setLang,
  onEnter,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  onEnter: () => void;
}) {
  const t = (k: string) => translate(lang, k);

  return (
    <div className="relative z-10">
      {/* nav */}
      <header className="glass sticky top-3 z-30 mx-3 flex items-center justify-between rounded-2xl px-4 py-2.5 sm:mx-6">
        <div className="flex items-center gap-2.5">
          <BrandMark className="h-9 w-9" />
          <span className="hidden font-display text-sm font-extrabold tracking-tight sm:block">
            Heatmap<span className="grad-text">Clipper</span>
          </span>
        </div>
        <nav className="hidden items-center gap-1 text-sm text-muted md:flex">
          <a href="#fitur" className="rounded-lg px-3 py-1.5 transition-colors hover:bg-surface-2/60 hover:text-ink">
            {t("land.nav.features")}
          </a>
          <a href="#cara" className="rounded-lg px-3 py-1.5 transition-colors hover:bg-surface-2/60 hover:text-ink">
            {t("land.nav.how")}
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <div className="flex rounded-xl border border-line bg-surface/80 p-0.5">
            <Languages className="mr-0.5 self-center text-faint" />
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
          <button className="btn btn-heat px-3.5 py-2 text-xs sm:px-4 sm:text-sm" onClick={onEnter}>
            {t("land.cta")}
          </button>
        </div>
      </header>

      {/* hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 pb-16 pt-12 sm:pt-16 lg:grid-cols-2 lg:gap-8">
        <div>
          <span className="chip mb-5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-heat-hot" style={{ animation: "pulse-glow 2.4s ease-in-out infinite" }} />
            {t("land.hero.badge")}
          </span>
          <h1 className="font-display text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl lg:text-[3.4rem]">
            {t("land.hero.t1")}
            <br />
            <span className="grad-text">{t("land.hero.t2")}</span>
          </h1>
          <p className="mt-5 max-w-lg text-sm leading-relaxed text-muted sm:text-base">
            {t("land.hero.desc")}
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <button className="btn btn-heat" onClick={onEnter}>
              <Scissors className="h-4 w-4" />
              {t("land.cta")}
              <ArrowRight className="h-4 w-4" />
            </button>
            <a href="#cara" className="btn btn-ghost">
              {t("land.hero.cta2")}
            </a>
          </div>
          <div className="mt-7 flex flex-wrap gap-2">
            {["land.trust.1", "land.trust.2", "land.trust.3"].map((k) => (
              <span key={k} className="chip">
                <Check className="h-3.5 w-3.5 text-heat-peak" />
                {t(k)}
              </span>
            ))}
          </div>
        </div>
        <PhoneMockup />
      </section>

      {/* features */}
      <section id="fitur" className="scroll-mt-20 border-t border-line/60 bg-surface/20 py-16 sm:py-20">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">{t("land.features.title")}</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted">{t("land.features.desc")}</p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="card card-hover p-5">
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-heat-warm/25 to-heat-hot/25 text-heat-hot ring-1 ring-heat-hot/25">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-sm font-bold">{t(title)}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-muted">{t(desc)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* how it works */}
      <section id="cara" className="scroll-mt-20 py-16 sm:py-20">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">{t("land.how.title")}</h2>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <div key={s} className="card p-6">
                <span className="font-display text-4xl font-extrabold text-line">{String(i + 1).padStart(2, "0")}</span>
                <h3 className="mt-3 text-sm font-bold">{t(`${s}.title`)}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-muted">{t(`${s}.desc`)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <div className="relative overflow-hidden rounded-3xl border border-line p-10 text-center sm:p-14">
          <div className="absolute -top-24 left-1/2 h-64 w-[36rem] -translate-x-1/2 rounded-full bg-heat-hot/20 blur-3xl" />
          <div className="relative">
            <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">{t("land.cta.title")}</h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-muted">{t("land.cta.desc")}</p>
            <button className="btn btn-heat mt-7 px-6 py-3" onClick={onEnter}>
              <Flame className="h-4 w-4" />
              {t("land.cta.btn")}
            </button>
          </div>
        </div>
      </section>

      <footer className="border-t border-line/60 py-8 text-center">
        <p className="text-xs text-faint">Heatmap Clipper · Most Replayed → Shorts</p>
      </footer>
    </div>
  );
}
