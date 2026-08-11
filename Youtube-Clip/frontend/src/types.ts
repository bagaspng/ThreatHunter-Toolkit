export interface SubtitleStyle {
  font: string;
  size: number;
  primary_color: string;
  outline_color: string;
  outline: number;
  location: "bottom" | "center";
}

export type SubtitlePreset = "standard" | "bold" | "karaoke" | "minimal";

interface SubtitlePresetDef {
  label: string; // i18n key
  style: SubtitleStyle;
}

export const SUBTITLE_PRESETS: Record<SubtitlePreset, SubtitlePresetDef> = {
  standard: {
    label: "sub.preset.standard",
    style: { font: "Plus Jakarta Sans", size: 12, primary_color: "#FFFFFF", outline_color: "#000000", outline: 2, location: "bottom" },
  },
  bold: {
    label: "sub.preset.bold",
    style: { font: "Montserrat", size: 16, primary_color: "#FFFFFF", outline_color: "#000000", outline: 4, location: "bottom" },
  },
  karaoke: {
    label: "sub.preset.karaoke",
    style: { font: "Plus Jakarta Sans", size: 18, primary_color: "#FFE600", outline_color: "#000000", outline: 3, location: "center" },
  },
  minimal: {
    label: "sub.preset.minimal",
    style: { font: "Arial", size: 10, primary_color: "#FFFFFF", outline_color: "#000000", outline: 1, location: "bottom" },
  },
};

export interface ClipForm {
  url: string;
  mode: "heatmap" | "custom";
  ratio: "9:16" | "1:1" | "16:9" | "original";
  crop: "default" | "split_left" | "split_right";
  padding: number;
  max_clips: number;
  subtitle: boolean;
  subtitle_style: SubtitleStyle;
  smart_crop: boolean;
  hook_text: string; // empty=off, "auto"=pick from transcript
  start: string;
  end: string;
}

export const defaultForm: ClipForm = {
  url: "",
  mode: "heatmap",
  ratio: "9:16",
  crop: "default",
  padding: 10,
  max_clips: 6,
  subtitle: false,
  subtitle_style: { ...SUBTITLE_PRESETS.standard.style },
  smart_crop: true,
  hook_text: "auto",
  start: "",
  end: "",
};
