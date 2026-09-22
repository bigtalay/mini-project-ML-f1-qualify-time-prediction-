import { useEffect, useState } from "react";
import type { components } from "./api";
export type Schema = components["schemas"];
export type Event = Schema["Event"];
export type Lap = Schema["Lap"];
export type Overview = Schema["Overview"];
export type PredictionRow = Schema["PredictionRow"];
export const time = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(value)) return "—";
  const milliseconds = Math.round(value * 1000);
  return `${Math.floor(milliseconds / 60000)}:${((milliseconds % 60000) / 1000).toFixed(3).padStart(6, "0")}`;
};
export const number = (value: number | null | undefined, digits = 3) =>
  value == null ? "—" : value.toFixed(digits);
export const delta = (value: number | null | undefined) =>
  value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(3)}s`;
export const teamColor = (team: string | null | undefined) => {
  const name = (team || "").toLowerCase();
  if (name.includes("red bull")) return "#7d9bfa";
  if (name.includes("mercedes")) return "#60d0bd";
  if (name.includes("ferrari")) return "#f66b73";
  if (name.includes("mclaren")) return "#f5a15b";
  if (name.includes("aston")) return "#72b7a3";
  if (name.includes("alpine")) return "#e497c7";
  if (name.includes("williams")) return "#77bde7";
  if (name.includes("alfa")) return "#ca8292";
  if (name.includes("tauri")) return "#b3c5dd";
  return "#c5c9d0";
};
export const reasonText: Record<string, string> = {
  kept: "ผ่านการตรวจ",
  duplicate: "แถวซ้ำ",
  missing_time_or_driver: "ไม่มีเวลา / นักขับ",
  nonpositive_time: "เวลาไม่เป็นบวก",
  deleted: "ถูกลบเวลา",
  inaccurate: "FastF1 ระบุว่าไม่แม่นยำ",
  generated: "FastF1 สร้างแถวขึ้น",
};
export async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : `โหลดข้อมูลไม่สำเร็จ (${response.status})`,
    );
  }
  return response.json();
}
export function useApi<T>(url: string | null) {
  const [state, set] = useState<{ data?: T; error?: string; loading: boolean }>(
    { loading: true },
  );
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!url) {
      set({ loading: false });
      return;
    }
    const controller = new AbortController();
    set({ loading: true });
    get<T>(url, controller.signal)
      .then((data) => set({ data, loading: false }))
      .catch((error) => {
        if (!controller.signal.aborted)
          set({ error: String(error.message), loading: false });
      });
    return () => controller.abort();
  }, [url, retry]);
  return { ...state, retry: () => setRetry((r) => r + 1) };
}
export function useQuery() {
  const [query, setQuery] = useState(
    () => new URLSearchParams(location.search),
  );
  useEffect(() => {
    const back = () => setQuery(new URLSearchParams(location.search));
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);
  const update = (patch: Record<string, string | null>, replace = false) => {
    const next = new URLSearchParams(location.search);
    Object.entries(patch).forEach(([key, value]) =>
      value == null || value === "" ? next.delete(key) : next.set(key, value),
    );
    history[replace ? "replaceState" : "pushState"]({}, "", `?${next}`);
    setQuery(next);
  };
  return { query, update };
}
