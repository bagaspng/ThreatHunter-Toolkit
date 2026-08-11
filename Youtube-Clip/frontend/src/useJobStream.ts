import { useEffect, useRef, useState } from "react";
import type { JobOutput } from "./api";

export interface JobStreamState {
  status: string;          // idle | running | done | error
  phase: "download" | "clips" | "";  // download = before clip loop, clips = per-clip processing
  total: number;
  currentIndex: number;
  success: number;
  stage: string;
  stagePct: number | null;
  speedKb: number | null;
  outputs: JobOutput[];
  error?: string;
}

const initial: JobStreamState = {
  status: "idle",
  phase: "",
  total: 0,
  currentIndex: 0,
  success: 0,
  stage: "",
  stagePct: null,
  speedKb: null,
  outputs: [],
};

/** Subscribe to /api/jobs/{id}/events (SSE). Pass null to reset/stop. */
export function useJobStream(jobId: string | null): JobStreamState {
  const [state, setState] = useState<JobStreamState>(initial);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    esRef.current?.close();
    if (!jobId) {
      setState(initial);
      return;
    }
    setState({ ...initial, status: "running" });
    const es = new EventSource(`/api/jobs/${jobId}/events`);
    esRef.current = es;

    es.onmessage = (ev) => {
      const d = JSON.parse(ev.data);
      setState((prev) => {
        switch (d.type) {
          case "total":
            return { ...prev, total: d.total };
          case "clip_start":
            return { ...prev, phase: "clips", currentIndex: d.index, total: d.total, stage: "", stagePct: null, speedKb: null };
          case "stage":
            return {
              ...prev,
              // if download stage fires before clip_start, set phase
              phase: prev.phase === "" && d.stage === "download" ? "download" : prev.phase,
              stage: d.stage,
              stagePct: d.pct ?? null,
              speedKb: d.speed_kb ?? null,
            };
          case "clip_done":
            return { ...prev, success: d.success, outputs: d.outputs ?? prev.outputs };
          case "status":
            return {
              ...prev,
              status: d.status,
              outputs: d.outputs ?? prev.outputs,
              success: d.success ?? prev.success,
              error: d.error,
            };
          default:
            return prev;
        }
      });
      if (d.type === "end") es.close();
    };
    es.onerror = () => es.close();

    return () => es.close();
  }, [jobId]);

  return state;
}
