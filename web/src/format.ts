import type { IndicatorMeta } from "./types";

const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

export function compact(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e9) return `${nf1.format(v / 1e9)}B`;
  if (a >= 1e6) return `${nf1.format(v / 1e6)}M`;
  if (a >= 1e4) return `${nf1.format(v / 1e3)}k`;
  return nf0.format(v);
}

const sign = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "±");

export function fmtDelta(ind: Pick<IndicatorMeta, "key" | "kind" | "unit">, d: number): string {
  if (Math.abs(d) < 1e-9) return "no change";
  const a = Math.abs(d);
  if (ind.kind === "share") return a * 100 < 0.05 ? "no change" : `${sign(d)}${nf1.format(a * 100)} pts`;
  switch (ind.key) {
    case "value":
      return `${sign(d)}$${compact(a)}`;
    case "green_space":
    case "runoff":
      return `${sign(d)}${a < 10 ? nf1.format(a) : nf0.format(a)} ac`;
    case "ghg":
      return `${sign(d)}${compact(a)} t`;
    default:
      return `${sign(d)}${a < 10 ? nf1.format(a) : compact(a)}`;
  }
}

export function fmtValue(ind: Pick<IndicatorMeta, "key" | "kind" | "unit">, v: number): string {
  if (!Number.isFinite(v)) return "–";
  if (ind.kind === "share") return `${nf1.format(v * 100)}%`;
  switch (ind.key) {
    case "value":
      return `$${compact(v)}`;
    case "green_space":
    case "runoff":
      return `${nf0.format(v)} ac`;
    case "ghg":
      return `${compact(v)} t/yr`;
    default:
      return compact(v);
  }
}

const nf2 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function fmtScore(s: number): string {
  const a = Math.abs(s);
  if (a < 0.005) return "0.00";
  return `${s > 0 ? "+" : "−"}${a < 1 ? nf2.format(a) : nf1.format(a)}`;
}

export const PILLAR_COLOR: Record<string, string> = {
  social: "#4EA8FF",
  economic: "#F5B700",
  environmental: "#34C77B",
};

export const PILLAR_LABEL: Record<string, string> = {
  social: "Social",
  economic: "Economic",
  environmental: "Environmental",
};
