import { Captions, Quote, ScanFace, type LucideIcon } from "lucide-react";
import { translate, type Lang } from "../i18n";
import { SUBTITLE_PRESETS, type ClipForm, type SubtitlePreset } from "../types";

export default function Controls({
  lang,
  form,
  set,
}: {
  lang: Lang;
  form: ClipForm;
  set: (patch: Partial<ClipForm>) => void;
}) {
  const t = (k: string, v?: Record<string, string | number>) => translate(lang, k, v);
  const st = form.subtitle_style;

  return (
    <div className="grid gap-5">
      {/* mode + ratio */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Row label={t("mode.label")}>
          <select
            className="field"
            value={form.mode}
            onChange={(e) => set({ mode: e.target.value as ClipForm["mode"] })}
          >
            <option value="heatmap">{t("mode.heatmap")}</option>
            <option value="custom">{t("mode.custom")}</option>
          </select>
        </Row>
        <Row label={t("ratio.label")}>
          <select
            className="field"
            value={form.ratio}
            onChange={(e) => set({ ratio: e.target.value as ClipForm["ratio"] })}
          >
            <option value="9:16">9:16 · Shorts</option>
            <option value="1:1">1:1</option>
            <option value="16:9">16:9</option>
            <option value="original">Original</option>
          </select>
        </Row>
      </div>

      {/* custom time inputs */}
      {form.mode === "custom" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Row label={t("start.label")}>
            <input
              className="field font-mono"
              placeholder="689 / 11:29"
              value={form.start}
              onChange={(e) => set({ start: e.target.value })}
            />
          </Row>
          <Row label={t("end.label")}>
            <input
              className="field font-mono"
              placeholder="742 / 12:22"
              value={form.end}
              onChange={(e) => set({ end: e.target.value })}
            />
          </Row>
        </div>
      )}

      {/* crop / padding / max */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Row label={t("crop.label")}>
          <select
            className="field"
            value={form.crop}
            onChange={(e) => set({ crop: e.target.value as ClipForm["crop"] })}
          >
            <option value="default">{t("crop.default")}</option>
            <option value="split_left">{t("crop.split_left")}</option>
            <option value="split_right">{t("crop.split_right")}</option>
          </select>
        </Row>
        <Row label={t("padding.label")}>
          <input
            type="number"
            min={0}
            className="field font-mono"
            value={form.padding}
            onChange={(e) => set({ padding: Number(e.target.value) })}
          />
        </Row>
        <Row label={t("maxclips.label")}>
          <input
            type="number"
            min={1}
            max={50}
            className="field font-mono"
            value={form.max_clips}
            onChange={(e) => set({ max_clips: Number(e.target.value) })}
          />
        </Row>
      </div>

      {/* smart crop + hook text */}
      <div className="grid gap-4 sm:grid-cols-2">
        <ToggleCard
          icon={ScanFace}
          title={t("smart_crop.label")}
          desc={form.smart_crop ? t("smart_crop.on") : t("smart_crop.off")}
          on={form.smart_crop}
          onToggle={() => set({ smart_crop: !form.smart_crop })}
        />
        <ToggleCard
          icon={Quote}
          title={t("hook.label")}
          desc={form.hook_text ? t("hook.on") : t("hook.off")}
          on={!!form.hook_text}
          onToggle={() => set({ hook_text: form.hook_text ? "" : "auto" })}
        />
      </div>

      {/* subtitle toggle */}
      <ToggleCard
        icon={Captions}
        title={t("sub.label")}
        desc={form.subtitle ? t("sub.on") : t("sub.off")}
        on={form.subtitle}
        onToggle={() => set({ subtitle: !form.subtitle })}
      >
        {form.subtitle && (
          <div className="mt-5 grid gap-4">
            <Row label={t("sub.preset")}>
              <select
                className="field"
                value={presetKey(st)}
                onChange={(e) =>
                  set({ subtitle_style: { ...SUBTITLE_PRESETS[e.target.value as SubtitlePreset].style } })
                }
              >
                {(Object.keys(SUBTITLE_PRESETS) as SubtitlePreset[]).map((p) => (
                  <option key={p} value={p}>
                    {t(SUBTITLE_PRESETS[p].label)}
                  </option>
                ))}
              </select>
            </Row>
            <SubtitlePreview lang={lang} style={st} />
          </div>
        )}
      </ToggleCard>
    </div>
  );
}

function presetKey(style: ClipForm["subtitle_style"]): SubtitlePreset {
  for (const p of Object.keys(SUBTITLE_PRESETS) as SubtitlePreset[]) {
    const s = SUBTITLE_PRESETS[p].style;
    if (
      s.font === style.font &&
      s.size === style.size &&
      s.primary_color === style.primary_color &&
      s.outline_color === style.outline_color &&
      s.outline === style.outline &&
      s.location === style.location
    )
      return p;
  }
  return "standard";
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <span className="label">{label}</span>
      {children}
    </div>
  );
}

function ToggleCard({
  icon: Icon,
  title,
  desc,
  on,
  onToggle,
  children,
}: {
  icon: LucideIcon;
  title: string;
  desc: string;
  on: boolean;
  onToggle: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface-2/50 p-4 transition-colors duration-200 hover:border-faint/60">
      <label className="flex cursor-pointer items-center justify-between gap-3">
        <span className="flex items-start gap-3">
          <span
            className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-surface/70 text-muted"
            style={on ? { color: "var(--color-heat-peak)" } : undefined}
          >
            <Icon className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-sm font-semibold">{title}</span>
            <span className="mt-0.5 block text-xs text-faint">{desc}</span>
          </span>
        </span>
        <Toggle on={on} onClick={onToggle} />
      </label>
      {children}
    </div>
  );
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className="switch"
    />
  );
}

function SubtitlePreview({ lang, style }: { lang: Lang; style: ClipForm["subtitle_style"] }) {
  const shadow = `${style.outline}px 0 ${style.outline_color}, -${style.outline}px 0 ${style.outline_color}, 0 ${style.outline}px ${style.outline_color}, 0 -${style.outline}px ${style.outline_color}`;
  return (
    <div>
      <span className="label">{translate(lang, "sub.preview")}</span>
      <div
        className="relative flex h-28 items-center justify-center overflow-hidden rounded-xl border border-line"
        style={{
          background:
            "repeating-linear-gradient(45deg, #10131c, #10131c 12px, #141824 12px, #141824 24px)",
        }}
      >
        <div
          className="absolute px-3 text-center"
          style={{
            fontFamily: `"${style.font}", sans-serif`,
            fontSize: `${style.size * 1.6}px`,
            fontWeight: 700,
            color: style.primary_color,
            textShadow: shadow,
            top: style.location === "center" ? "50%" : "auto",
            bottom: style.location === "bottom" ? "12px" : "auto",
            transform: style.location === "center" ? "translateY(-50%)" : "none",
          }}
        >
          {lang === "id" ? "Momen paling seru" : "The hottest moment"}
        </div>
      </div>
    </div>
  );
}
