import type { ChangeValue, Evaluation, ImportReview, Meta, Negotiation, ParcelInfo, ParetoResult, Study, Vote } from "./types";

/** The city this page works on (?city=<id>; Manhattan by default). Every API call carries it in a header. */
export const CITY = new URLSearchParams(window.location.search).get("city") || "manhattan";
const CITY_HEADER = { "X-PlanArena-City": CITY };
/** Map layers of the current city. */
export const cityDataUrl = (path: string) => (CITY === "manhattan" ? `/data/${path}` : `/city-data/${CITY}/${path}`);
/** Same page, another city. */
export const cityHref = (id: string, page = window.location.pathname) => (id === "manhattan" ? page : `${page}?city=${id}`);

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...CITY_HEADER },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: CITY_HEADER });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json() as Promise<T>;
}

export type Changes = Record<string, ChangeValue>;

async function send<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json", ...CITY_HEADER } : CITY_HEADER,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function download(url: string, body: unknown, filename: string) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", ...CITY_HEADER }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(await r.text());
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export interface ZoningSummary {
  n: number; has_zoning: boolean; zoning_rules: string;
  max_far: { min: number; median: number; max: number }; built_far: { min: number; median: number; max: number };
  districts: Record<string, number>; allowed_on_all: string[];
}
export interface CityEntry { id: string; label: string; built?: boolean; status?: string; tier?: string; source?: string; parcels?: number }

/** The exact optimizer's certificate: the plan's score, an upper bound on any feasible plan's score, and the gap. */
export interface Certificate {
  status: "optimal" | "gap" | "not certified";
  objective?: number;
  bound?: number;
  gap?: number;
  rel_gap?: number;
  seconds?: number;
  reason?: string;
  /** the exact score of the fast plan shown first, for "the preview reached x% of the optimum" */
  fast_objective?: number;
}

/** The exact trade-off front: optimal plans for a grid of pillar weights, the balanced plan and trade-off rates. */
export interface ExactFront {
  front: { pillars: Record<string, number>; n_changed: number; balanced: boolean; changes: Changes }[];
  balanced: { pillars: Record<string, number>; status: string; rel_gap: number; efficiency_gap: number };
  rates: Record<string, Record<string, number | Record<string, number>>[]>;
  certified_share: number;
  robust_share?: number;
  seconds: number;
  grid_points: number;
}

export const api = {
  cities: () => get<CityEntry[]>("/api/cities"),
  zoningSummary: (parcels: number[]) => post<ZoningSummary>("/api/zoning-summary", { parcels }),
  /** existing use, adopted plan and zoning class of every parcel (int16 each, -1 = none) */
  layers: async () => {
    const r = await fetch("/api/layers", { headers: CITY_HEADER });
    if (!r.ok) throw new Error(`/api/layers: ${r.status}`);
    const b = await r.arrayBuffer();
    const n = b.byteLength / 6;
    return { existing: new Int16Array(b, 0, n), plan: new Int16Array(b, 2 * n, n), zoning: new Int16Array(b, 4 * n, n) };
  },
  points: async () => {
    const r = await fetch("/api/points", { headers: CITY_HEADER });
    if (!r.ok) throw new Error(`/api/points: ${r.status}`);
    return r.arrayBuffer();
  },
  meta: () => get<Meta>("/api/meta"),
  parcel: (i: number) => get<ParcelInfo>(`/api/parcel/${i}`),
  suitability: () => get<{ top: number[]; p: number[] }>("/api/suitability"),
  redevelopment: () => get<{ p: number[]; rank: number[]; top: number[]; meta: Record<string, number | string> }>("/api/redevelopment"),
  evaluate: (changes: Changes, scope: string) => post<Evaluation>("/api/evaluate", { changes, scope }),
  suggest: (body: {
    scope: string;
    mode: string;
    pillar_weights?: Record<string, number>;
    changes?: Changes;
    parcels?: number[];
    max_change_share?: number;
    respect_zoning?: boolean;
    method?: "fast" | "exact";
    time_limit?: number;
    polish?: number;
  }) =>
    post<{ changes: Changes; evaluation: Evaluation; history: unknown[]; budget: number; ms: number; certificate?: Certificate | null }>(
      "/api/suggest",
      body,
    ),
  negotiate: (body: { scope: string; changes?: Changes; parcels?: number[]; max_change_share?: number }) =>
    post<Negotiation>("/api/negotiate", body),
  vote: (body: {
    scope: string;
    changes?: Changes;
    max_change_share?: number;
    seats?: Record<string, number>;
    residents?: boolean;
    parcel_ballot?: boolean;
    samples?: number;
    plans?: Record<string, { title: string; changes: Changes }>;
  }) => post<Vote>("/api/vote", body),
  rezoningTest: (changes: Changes) =>
    post<{ rezoned_parcels: number; sites: number[]; n_sites: number; homes_increment: number;
      homes_increment_at_utilisation: number; utilisation: number; floor_area_increment_sqft: number; criteria: string;
      min_far_increase: number }>("/api/rezoning-test", { changes }),
  priceOfAnarchy: (scope: string) =>
    post<{ welfare_fragmented: number; welfare_cooperative: number; price_of_anarchy: number | null }>(
      "/api/price-of-anarchy",
      { scope },
    ),
  importPlan: async (file: File): Promise<ImportReview> => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`/api/import`, { method: "POST", body: fd, headers: CITY_HEADER });
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
  policy: (parcels: number[], pillar_weights: Record<string, number>, max_change_share = 0.05) =>
    post<{ changes: Changes; evaluation: Evaluation; ms: number }>("/api/policy", { parcels, pillar_weights, max_change_share }),
  frontier: (parcels: number[], changes: Changes, max_change_share = 0.05) =>
    post<ExactFront>("/api/frontier", { parcels, changes, max_change_share }),
  studies: () => get<Study[]>("/api/scenarios"),
  createStudy: (body: { name: string; description: string; study_area: string; changes: Changes }) =>
    send<Study>("POST", "/api/scenarios", body),
  patchStudy: (id: string, body: Partial<Study>) => send<Study>("PATCH", `/api/scenarios/${id}`, body),
  deleteStudy: (id: string) => send<{ deleted: string }>("DELETE", `/api/scenarios/${id}`),
  studyHistory: (id: string) => get<{ id: number; timestamp: string; action: string; body: unknown }[]>(`/api/scenarios/${id}/history`),
  audit: () => get<{ verify: { valid: boolean; rows: number; head?: string }; rows: { id: number; timestamp: string; action: string; body: unknown }[] }>("/api/audit?limit=60"),
  exportFile: (fmt: "csv" | "geojson" | "provenance", changes: Changes, title = "PlanArena study") =>
    download(`/api/export/${fmt}`, { changes, title }, fmt === "provenance" ? "planarena-report.json" : `planarena-plan.${fmt}`),
  openReport: async (changes: Changes, title: string, description = "", vote?: Vote) => {
    const summary = vote && {
      decision: vote.decision,
      n_candidates: vote.candidates.length,
      rules: Object.fromEntries(
        Object.values(vote.council.rules).map((r) => [r.label, vote.candidates.find((c) => c.id === r.winner)?.title ?? r.winner]),
      ),
    };
    const r = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...CITY_HEADER },
      body: JSON.stringify({ changes, title, description, vote: summary }),
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
