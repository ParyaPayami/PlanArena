import type { Evaluation, Meta, Negotiation, ParcelInfo } from "./types";

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

export type Changes = Record<string, string>;

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
  upload: async (file: File, scope = "affected"): Promise<Evaluation> => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`/api/upload?scope=${scope}`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};
