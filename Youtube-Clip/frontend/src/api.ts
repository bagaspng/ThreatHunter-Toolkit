export interface Preview {
  title?: string;
  thumbnail?: string;
  uploader?: string;
  duration?: number;
  id?: string;
  webpage_url?: string;
}

export interface Segment {
  start: number;
  duration: number;
  score: number;
}

export interface JobOutput {
  name: string;
  size: number;
}

export interface JobRecord {
  id: string;
  created_at: number;
  finished_at?: number;
  status: string;
  title?: string;
  request: Record<string, unknown>;
  outputs: JobOutput[];
  error?: string;
}

async function req<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail || `HTTP ${res.status}`);
  return data as T;
}

export const api = {
  health: () => req<{ ok: boolean; ffmpeg: boolean; auth: boolean }>("/api/health"),
  login: (password: string) =>
    req<{ ok: boolean }>("/api/login", { method: "POST", body: JSON.stringify({ password }) }),
  preview: (url: string) =>
    req<{ preview: Preview }>("/api/preview", { method: "POST", body: JSON.stringify({ url }) }),
  scan: (url: string) =>
    req<{ segments: Segment[]; duration: number | null; video_id: string }>("/api/scan", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  clip: (payload: Record<string, unknown>) =>
    req<{ job_id: string }>("/api/clip", { method: "POST", body: JSON.stringify(payload) }),
  jobs: () => req<{ jobs: JobRecord[] }>("/api/jobs"),
  job: (id: string) => req<{ job: JobRecord }>(`/api/jobs/${id}`),
  deleteJob: (id: string) => req<{ ok: boolean }>(`/api/jobs/${id}`, { method: "DELETE" }),
  zipUrl: (id: string) => `/api/jobs/${id}/download.zip`,
  clipUrl: (jobId: string, name: string) => `/clips/${jobId}/${name}`,
  clipSourceUrl: (jobId: string, clipIndex: number) => `/api/clip/${jobId}/${clipIndex}/source`,
  editUrl: () => `/api/clip/edit`,
};

export function fmtTime(sec?: number): string {
  if (sec == null) return "";
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(r)}` : `${pad(m)}:${pad(r)}`;
}
