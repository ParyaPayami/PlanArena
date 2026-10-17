import type { ChangeValue, Evaluation, ImportReview, Meta, Negotiation, ParcelInfo, ParetoResult, Study } from "./types";

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json() as Promise<T>;
}

export type Changes = Record<string, ChangeValue>;

async function send<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function download(url: string, body: unknown, filename: string) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(await r.text());
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  parcel: (i: number) => get<ParcelInfo>(`/api/parcel/${i}`),
  suitability: () => get<{ top: number[]; p: number[] }>("/api/suitability"),
  evaluate: (changes: Changes, scope: string) => post<Evaluation>("/api/evaluate", { changes, scope }),
  suggest: (body: {
    scope: string;
    mode: string;
    changes?: Changes;
    parcels?: number[];
    max_change_share?: number;
    respect_zoning?: boolean;
  }) => post<{ changes: Changes; evaluation: Evaluation; history: unknown[]; budget: number; ms: number }>(
    "/api/suggest",
    body,
  ),
  negotiate: (body: { scope: string; changes?: Changes; parcels?: number[]; max_change_share?: number }) =>
    post<Negotiation>("/api/negotiate", body),
  priceOfAnarchy: (scope: string) =>
    post<{ welfare_fragmented: number; welfare_cooperative: number; price_of_anarchy: number | null }>(
      "/api/price-of-anarchy",
      { scope },
    ),
  importPlan: async (file: File): Promise<ImportReview> => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`/api/import`, { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail);
    return r.json();
  },
  search: (q: string) => get<{ i: number; bbl: number; address: string; lon: number; lat: number }[]>(`/api/search?q=${encodeURIComponent(q)}`),
  block: (i: number) => get<{ block: number; parcels: number[] }>(`/api/block/${i}`),
  softSites: () => get<{ parcels: number[]; rule: string }>("/api/soft-sites"),
  radius: (parcels: number[], feet: number) =>
    post<{ feet: number; count: number; parcels: { i: number; bbl: number; address: string; use: string | null }[] }>(
      "/api/radius",
      { parcels, feet },
    ),
  pareto: (parcels: number[], changes: Changes, seed = 42) => post<ParetoResult>("/api/pareto", { parcels, changes, seed }),
  studies: () => get<Study[]>("/api/scenarios"),
  createStudy: (body: { name: string; description: string; study_area: string; changes: Changes }) =>
    send<Study>("POST", "/api/scenarios", body),
  patchStudy: (id: string, body: Partial<Study>) => send<Study>("PATCH", `/api/scenarios/${id}`, body),
  deleteStudy: (id: string) => send<{ deleted: string }>("DELETE", `/api/scenarios/${id}`),
  studyHistory: (id: string) => get<{ id: number; timestamp: string; action: string; body: unknown }[]>(`/api/scenarios/${id}/history`),
  audit: () => get<{ verify: { valid: boolean; rows: number; head?: string }; rows: { id: number; timestamp: string; action: string; body: unknown }[] }>("/api/audit?limit=60"),
  exportFile: (fmt: "csv" | "geojson" | "provenance", changes: Changes, title = "PlanArena study") =>
    download(`/api/export/${fmt}`, { changes, title }, fmt === "provenance" ? "planarena-report.json" : `planarena-plan.${fmt}`),
  openReport: async (changes: Changes, title: string, description = "", negotiation?: unknown) => {
    const r = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ changes, title, description, negotiation }),
    });
    const html = await r.text();
    const w = window.open("", "_blank");
    if (w) {
      w.document.open();
      w.document.write(html);
      w.document.close();
    }
  },
};
