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

export type Tab = "impact" | "ai" | "agents" | "upload";

interface Preview {
  label: string;
  changes: Changes;
  evaluation?: Evaluation;
}

interface State {
  meta?: Meta;
  data?: CityData;
  useKeys: string[];
  use: Int16Array;
  version: number;
  selected: Set<number>;
  selVersion: number;
  past: Int16Array[];
  future: Int16Array[];
  evaluation?: Evaluation;
  evaluating: boolean;
  scope: string;
  preview?: Preview;
  negotiation?: Negotiation;
  view3d: boolean;
  tab: Tab;
  toast?: { text: string; tone: "good" | "bad" | "info"; id: number };
  init: (meta: Meta, data: CityData) => void;
  select: (i: number, additive: boolean) => void;
  selectMany: (idx: number[], additive: boolean) => void;
  clearSelection: () => void;
  paint: (useKey: string, idx?: number[]) => void;
  applyChanges: (changes: Changes, replace?: boolean) => void;
  undo: () => void;
  redo: () => void;
  reset: () => void;
  setScope: (s: string) => void;
  setPreview: (p?: Preview) => void;
  setNegotiation: (n?: Negotiation) => void;
  setTab: (t: Tab) => void;
  toggle3d: () => void;
  notify: (text: string, tone?: "good" | "bad" | "info") => void;
  changes: () => Changes;
}

export const useStore = create<State>((set, get) => ({
  useKeys: [],
  use: new Int16Array(0),
  version: 0,
  selected: new Set(),
  selVersion: 0,
  past: [],
  future: [],
  evaluating: false,
  scope: "affected",
  view3d: false,
  tab: "impact",

  init: (meta, data) =>
    set({
      meta,
      data,
      useKeys: meta.land_uses.map((u) => u.key),
      use: data.baseUse.slice(),
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

  paint: (useKey, idx) => {
    const s = get();
    const code = s.useKeys.indexOf(useKey);
    const targets = idx ?? [...s.selected];
    if (code < 0 || !targets.length) return;
    const next = s.use.slice();
    let n = 0;
    for (const i of targets) {
      if (s.data && s.data.baseUse[i] < 0 && code < 0) continue;
      if (next[i] !== code) {
        next[i] = code;
        n++;
      }
    }
    if (!n) return;
    set({ past: [...s.past.slice(-60), s.use], future: [], use: next, version: s.version + 1 });
  },

  applyChanges: (changes, replace = false) => {
    const s = get();
    if (!s.data) return;
    const next = replace ? s.data.baseUse.slice() : s.use.slice();
    for (const [k, v] of Object.entries(changes)) {
      const code = s.useKeys.indexOf(v);
      if (code >= 0) next[Number(k)] = code;
    }
    set({ past: [...s.past.slice(-60), s.use], future: [], use: next, version: s.version + 1 });
  },

  undo: () => {
    const s = get();
    if (!s.past.length) return;
    const prev = s.past[s.past.length - 1];
    set({ past: s.past.slice(0, -1), future: [s.use, ...s.future], use: prev, version: s.version + 1 });
  },

  redo: () => {
    const s = get();
    if (!s.future.length) return;
    const [nxt, ...rest] = s.future;
    set({ past: [...s.past, s.use], future: rest, use: nxt, version: s.version + 1 });
  },

  reset: () => {
    const s = get();
    if (!s.data) return;
    set({ past: [...s.past, s.use], future: [], use: s.data.baseUse.slice(), version: s.version + 1, preview: undefined });
  },

  setScope: (scope) => set({ scope }),
  setPreview: (preview) => set((s) => ({ preview, version: s.version + 1 })),
  setNegotiation: (negotiation) => set({ negotiation }),
  setTab: (tab) => set({ tab }),
  toggle3d: () => set((s) => ({ view3d: !s.view3d })),
  notify: (text, tone = "info") => set({ toast: { text, tone, id: Date.now() } }),

  changes: () => {
    const s = get();
    const out: Changes = {};
    if (!s.data) return out;
    const base = s.data.baseUse;
    for (let i = 0; i < s.use.length; i++) {
      if (s.use[i] !== base[i] && s.use[i] >= 0) out[i] = s.useKeys[s.use[i]];
    }
    return out;
  },
}));

let evalTimer: number | undefined;
let evalSeq = 0;

/** Re-evaluate whenever the plan or the scope changes (debounced; only the latest request wins). */
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
  let ring: number[][] = [];
  if (g.type === "Polygon") ring = g.coordinates[0];
  else if (g.type === "MultiPolygon") ring = g.coordinates[0][0];
  let x = 0, y = 0;
  for (const p of ring) {
    x += p[0];
    y += p[1];
  }
  const k = Math.max(ring.length, 1);
  return [x / k, y / k];
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
