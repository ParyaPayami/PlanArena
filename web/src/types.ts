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
  version: string;
  source_sha256: string;
  source_url: string;
  data_quality: Record<string, number>;
  capacity_city: Capacity;
  coefficients: Record<string, unknown>;
  statuses: string[];
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
  models: {
    gnn: boolean;
    cv_summary?: Record<string, Record<string, { mean: number; sd: number }>>;
    emissions_validation?: Record<string, number | string>;
  };
}

export interface Capacity {
  zoning_capacity_sqft: number;
  built_sqft: number;
  unused_capacity_sqft: number;
  soft_sites: number;
  soft_site_rule: string;
  plan_added_capacity_sqft: number;
  plan_added_capacity_homes: number;
}

export interface IndicatorResult extends IndicatorMeta {
  range?: [number, number];
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
  capacity?: { baseline: Capacity; scenario: Capacity };
  ms?: number;
  changes?: Record<string, ChangeValue>;
}

export type ChangeValue = string | { use: string; far: number };

export interface ImportReview {
  filename: string;
  rows: number;
  valid_changes: number;
  unchanged_rows: number;
  unmatched: number;
  duplicates: number;
  unknown_uses: number;
  far_issues: number;
  issues: Record<string, { row: number; id?: unknown; value?: unknown; first_row?: number }[]>;
  changes: Record<string, ChangeValue>;
}

export interface Study {
  id: string;
  name: string;
  description: string;
  status: string;
  hearing_date: string | null;
  study_area: string;
  changes: Record<string, ChangeValue>;
  checklist: { label: string; done: boolean }[];
  summary?: { overall: number; pillars: Record<Pillar, number>; n_changed: number };
  created_at: string;
  updated_at: string;
  source_sha256: string;
}

export interface ParetoPlan {
  changes: Record<string, string>;
  n_changed: number;
  pillars: Record<Pillar, number>;
  overall: number;
  estimated: number[];
}

export interface ParetoResult {
  algorithm: string;
  seed: number;
  generations: number;
  n_parcels: number;
  n_free: number;
  front: ParetoPlan[];
  presets: { name: string; weights: Record<string, number>; index: number }[];
  study_area_parcels?: number;
  note?: string;
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
  block: number;
  bldg_class: string;
  built_far: number;
  max_far: number;
  resid_far: number;
  comm_far: number;
  facil_far: number;
  soft_site: boolean;
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
