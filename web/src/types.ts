export type Pillar = "social" | "economic" | "environmental";

export interface LandUse {
  key: string;
  label: string;
  color: string;
  built: boolean;
}

export interface IndicatorMeta {
  key: string;
  label: string;
  unit: string;
  pillar: Pillar;
  direction: number;
  kind: "total" | "share";
  provisional: boolean;
}

export interface Stakeholder {
  key: string;
  name: string;
  icon: string;
  color: string;
  blurb: string;
  weights: Record<string, number>;
}

export interface Meta {
  city: string;
  source: string;
  n_parcels: number;
  bbox: [number, number, number, number];
  levels: Record<string, string>;
  land_uses: LandUse[];
  indicators: IndicatorMeta[];
  baseline_city: Record<string, number>;
  stakeholders: Stakeholder[];
  derived: Record<string, unknown>;
  provenance: Record<string, { status: string; source?: string }>;
  zoning_rules: string;
  models: { gnn: boolean; cv_summary?: Record<string, Record<string, { mean: number; sd: number }>> };
}

export interface IndicatorResult extends IndicatorMeta {
  baseline: number;
  scenario: number;
  delta: number;
  pct: number;
  score: number;
  city_baseline: number;
  city_scenario: number;
  city_delta: number;
}

export interface ByUse {
  use: string;
  label: string;
  color: string;
  parcels: number;
  acres: number;
  homes: number;
  jobs: number;
  value: number;
  ghg: number;
  runoff: number;
  green_space: number;
}

export interface Warning {
  type: string;
  count: number;
  parcels: number[];
  message: string;
}

export interface Evaluation {
  scope: string;
  scope_parcels: number;
  n_changed: number;
  indicators: IndicatorResult[];
  pillars: Record<Pillar, number>;
  overall: number;
  by_use: ByUse[];
  warnings: Warning[];
  ms?: number;
  upload?: { rows: number; matched: number; unmatched: number; unmatched_examples: unknown[]; unknown_uses: string[] };
  changes?: Record<string, string>;
}

export interface TranscriptLine {
  round: number;
  agent: string;
  kind: "propose" | "concede" | "object" | "mediate" | "agree";
  plan: string | null;
  text: string;
}

export interface Negotiation {
  agreed_plan: string;
  agreed_by_protocol: boolean;
  rounds: number;
  utilities: Record<string, number>;
  transcript: TranscriptLine[];
  solutions: Record<string, { plan: string; utilities: number[]; welfare: number } | null | string[]>;
  plans: { id: string; title: string; origin: string; n_changed: number; pillars: Record<Pillar, number>; overall: number }[];
  plan_changes: Record<string, Record<string, string>>;
  plan_evaluations: Record<string, Evaluation>;
  utility_matrix: number[][];
  plan_ids: string[];
  ms: number;
}

export interface ParcelInfo {
  i: number;
  bbl: number;
  address: string;
  cd: number;
  zone: string;
  overlay: string;
  special_district: string;
  use: string | null;
  lot_area_sqft: number;
  bldg_area_sqft: number;
  floors: number;
  units: number;
  assessed_value: number;
  year_built: number;
  landmark: boolean;
  historic_district: boolean;
  allowed_uses: string[];
  per_use: Record<string, Record<string, number>>;
  suitability?: Record<string, number>;
}
