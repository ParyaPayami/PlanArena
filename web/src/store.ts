import { create } from "zustand";
import { api, type Changes } from "./api";
import type { Evaluation, Meta, Negotiation } from "./types";

export interface CityData {
  features: GeoJSON.Feature[];
  n: number;
  baseUse: Int16Array;
  lon: Float32Array;
  lat: Float32Array;
  cd: Int16Array;
}

export type Tab = "impact" | "ai" | "agents" | "studies" | "desk" | "data";

interface Preview {
  label: string;
  changes: Changes;
  evaluation?: Evaluation;
}

interface Snapshot {
  use: Int16Array;
  far: Float32Array;
}

export interface Highlight {
  key: string;
  parcels: Set<number>;
  color: [number, number, number];
  label: string;
}

interface State {
  meta?: Meta;
  data?: CityData;
  useKeys: string[];
  use: Int16Array;
  far: Float32Array; // NaN = keep the existing / zoning-default floor area
  version: number;
  selected: Set<number>;
  selVersion: number;
  past: Snapshot[];
  future: Snapshot[];
  evaluation?: Evaluation;
  evaluating: boolean;
  scope: string;
  preview?: Preview;
  negotiation?: Negotiation;
  highlight?: Highlight;
  focus?: { lon: number; lat: number; zoom: number; id: number };
  view3d: boolean;
  tab: Tab;
  methodsOpen: boolean;
  toast?: { text: string; tone: "good" | "bad" | "info"; id: number };
  init: (meta: Meta, data: CityData) => void;
  select: (i: number, additive: boolean) => void;
  selectMany: (idx: number[], additive: boolean) => void;
  clearSelection: () => void;
  paint: (useKey: string, idx?: number[], far?: number | null) => void;
  setFar: (far: number | null, idx?: number[]) => void;
  applyChanges: (changes: Changes, replace?: boolean) => void;
  undo: () => void;
  redo: () => void;
  reset: () => void;
  setScope: (s: string) => void;
  setPreview: (p?: Preview) => void;
  setNegotiation: (n?: Negotiation) => void;
  setHighlight: (h?: Highlight) => void;
  flyTo: (lon: number, lat: number, zoom?: number) => void;
  setTab: (t: Tab) => void;
  toggle3d: () => void;
  setMethodsOpen: (b: boolean) => void;
  notify: (text: string, tone?: "good" | "bad" | "info") => void;
  changes: () => Changes;
}

const snap = (s: { use: Int16Array; far: Float32Array }): Snapshot => ({ use: s.use, far: s.far });

export const useStore = create<State>((set, get) => ({
  useKeys: [],
  use: new Int16Array(0),
  far: new Float32Array(0),
  version: 0,
  selected: new Set(),
  selVersion: 0,
  past: [],
  future: [],
  evaluating: false,
  scope: "affected",
  view3d: false,
  tab: "impact",
  methodsOpen: false,

  init: (meta, data) =>
    set({
      meta,
      data,
      useKeys: meta.land_uses.map((u) => u.key),
      use: data.baseUse.slice(),
      far: new Float32Array(data.n).fill(NaN),
      version: 1,
    }),

  select: (i, additive) =>
    set((s) => {
      const sel = additive ? new Set(s.selected) : new Set<number>();
      if (additive && sel.has(i)) sel.delete(i);
      else sel.add(i);
      return { selected: sel, selVersion: s.selVersion + 1 };
    }),

  selectMany: (idx, additive) =>
    set((s) => {
      const sel = additive ? new Set(s.selected) : new Set<number>();
      idx.forEach((i) => sel.add(i));
      return { selected: sel, selVersion: s.selVersion + 1 };
    }),

  clearSelection: () => set((s) => ({ selected: new Set(), selVersion: s.selVersion + 1 })),

  paint: (useKey, idx, far) => {
    const s = get();
    const code = s.useKeys.indexOf(useKey);
    const targets = idx ?? [...s.selected];
    if (code < 0 || !targets.length) return;
    const nextUse = s.use.slice();
    const nextFar = s.far.slice();
    let n = 0;
    for (const i of targets) {
      const f = far === undefined ? nextFar[i] : far === null ? NaN : far;
      if (nextUse[i] !== code || !Object.is(nextFar[i], f)) {
        nextUse[i] = code;
        nextFar[i] = f;
        n++;
      }
    }
    if (!n) return;
    set({ past: [...s.past.slice(-60), snap(s)], future: [], use: nextUse, far: nextFar, version: s.version + 1 });
  },

  setFar: (far, idx) => {
    const s = get();
    const targets = idx ?? [...s.selected];
    if (!targets.length) return;
    const nextFar = s.far.slice();
    for (const i of targets) nextFar[i] = far === null ? NaN : far;
    set({ past: [...s.past.slice(-60), snap(s)], future: [], far: nextFar, version: s.version + 1 });
  },

  applyChanges: (changes, replace = false) => {
    const s = get();
    if (!s.data) return;
    const use = replace ? s.data.baseUse.slice() : s.use.slice();
    const far = replace ? new Float32Array(s.data.n).fill(NaN) : s.far.slice();
    for (const [k, v] of Object.entries(changes)) {
      const key = typeof v === "string" ? v : v.use;
      const code = s.useKeys.indexOf(key);
      if (code < 0) continue;
      use[Number(k)] = code;
      far[Number(k)] = typeof v === "string" ? NaN : v.far;
    }
    set({ past: [...s.past.slice(-60), snap(s)], future: [], use, far, version: s.version + 1 });
  },

  undo: () => {
    const s = get();
    if (!s.past.length) return;
    const prev = s.past[s.past.length - 1];
    set({ past: s.past.slice(0, -1), future: [snap(s), ...s.future], use: prev.use, far: prev.far, version: s.version + 1 });
  },

  redo: () => {
    const s = get();
    if (!s.future.length) return;
    const [nxt, ...rest] = s.future;
    set({ past: [...s.past, snap(s)], future: rest, use: nxt.use, far: nxt.far, version: s.version + 1 });
  },

  reset: () => {
    const s = get();
    if (!s.data) return;
    set({
      past: [...s.past, snap(s)], future: [], use: s.data.baseUse.slice(),
      far: new Float32Array(s.data.n).fill(NaN), version: s.version + 1, preview: undefined,
    });
  },

  setScope: (scope) => set({ scope }),
  setPreview: (preview) => set((s) => ({ preview, version: s.version + 1 })),
  setNegotiation: (negotiation) => set({ negotiation }),
  setHighlight: (highlight) => set((s) => ({ highlight, selVersion: s.selVersion + 1 })),
  flyTo: (lon, lat, zoom = 17) => set({ focus: { lon, lat, zoom, id: Date.now() } }),
  setTab: (tab) => set({ tab }),
  toggle3d: () => set((s) => ({ view3d: !s.view3d })),
  setMethodsOpen: (methodsOpen) => set({ methodsOpen }),
  notify: (text, tone = "info") => set({ toast: { text, tone, id: Date.now() } }),

  changes: () => {
    const s = get();
    const out: Changes = {};
    if (!s.data) return out;
    const base = s.data.baseUse;
    for (let i = 0; i < s.use.length; i++) {
      const hasFar = !Number.isNaN(s.far[i]);
      if ((s.use[i] !== base[i] || hasFar) && s.use[i] >= 0) {
        out[i] = hasFar ? { use: s.useKeys[s.use[i]], far: Math.round(s.far[i] * 100) / 100 } : s.useKeys[s.use[i]];
      }
    }
    return out;
  },
}));

let evalTimer: number | undefined;
let evalSeq = 0;

function scheduleEvaluate() {
  window.clearTimeout(evalTimer);
  evalTimer = window.setTimeout(async () => {
    const seq = ++evalSeq;
    useStore.setState({ evaluating: true });
    try {
      const st = useStore.getState();
      const ev = await api.evaluate(st.changes(), st.scope);
      if (seq === evalSeq) useStore.setState({ evaluation: ev, evaluating: false });
    } catch (e) {
      if (seq === evalSeq) useStore.setState({ evaluating: false });
      useStore.getState().notify(String(e), "bad");
    }
  }, 120);
}

let autoStarted = false;
let lastVersion = -1;
let lastScope = "";
let lastData: CityData | undefined;
/** Re-evaluate whenever the plan or the scope changes (debounced; only the latest request wins). */
export function startAutoEvaluate() {
  if (!autoStarted) {
    autoStarted = true;
    useStore.subscribe((s) => {
      if (!s.data || (s.version === lastVersion && s.scope === lastScope && s.data === lastData)) return;
      lastVersion = s.version;
      lastScope = s.scope;
      lastData = s.data;
      scheduleEvaluate();
    });
  }
  const s = useStore.getState();
  lastVersion = s.version;
  lastScope = s.scope;
  lastData = s.data;
  if (s.data) scheduleEvaluate();
}

export async function loadCity(url = "/data/parcels.geojson", onProgress?: (p: number) => void) {
  const [meta, geo] = await Promise.all([api.meta(), fetchWithProgress(url, onProgress)]);
  const features = (geo as GeoJSON.FeatureCollection).features;
  const n = meta.n_parcels;
  const baseUse = new Int16Array(n).fill(-1);
  const lon = new Float32Array(n);
  const lat = new Float32Array(n);
  const cd = new Int16Array(n);
  for (const f of features) {
    const p = f.properties as { i: number; u: number; cd: number };
    baseUse[p.i] = p.u;
    cd[p.i] = p.cd;
    const c = centroidOf(f.geometry);
    lon[p.i] = c[0];
    lat[p.i] = c[1];
  }
  return { meta, data: { features, n, baseUse, lon, lat, cd } as CityData };
}

function centroidOf(g: GeoJSON.Geometry): [number, number] {
  // Vertex mean of the outer ring, or of every vertex for any other geometry type.
  let pts: number[][] = [];
  if (g.type === "Polygon") pts = g.coordinates[0];
  else if (g.type === "MultiPolygon") pts = g.coordinates[0][0];
  else if (g.type === "LineString" || g.type === "MultiPoint") pts = g.coordinates;
  else if (g.type === "Point") pts = [g.coordinates];
  else if (g.type === "MultiLineString") pts = g.coordinates.flat();
  else if (g.type === "GeometryCollection") pts = g.geometries.map(centroidOf);
  if (!pts.length) return [NaN, NaN];
  let x = 0,
    y = 0;
  for (const p of pts) {
    x += p[0];
    y += p[1];
  }
  return [x / pts.length, y / pts.length];
}

async function fetchWithProgress(url: string, onProgress?: (p: number) => void) {
  const r = await fetch(url);
  const total = Number(r.headers.get("Content-Length")) || 0;
  if (!r.body || !total || !onProgress) return r.json();
  const reader = r.body.getReader();
  const chunks: Uint8Array[] = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    onProgress(Math.min(got / total, 1));
  }
  const buf = new Uint8Array(got);
  let o = 0;
  for (const c of chunks) {
    buf.set(c, o);
    o += c.length;
  }
  return JSON.parse(new TextDecoder().decode(buf));
}
