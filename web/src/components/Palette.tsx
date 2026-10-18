import { useEffect, useState } from "react";
import { api, type ZoningSummary } from "../api";
import { useStore } from "../store";

export default function Palette({ compact = false }: { compact?: boolean }) {
  const meta = useStore((s) => s.meta);
  const selected = useStore((s) => s.selected);
  const paint = useStore((s) => s.paint);
  const setFar = useStore((s) => s.setFar);
  const clear = useStore((s) => s.clearSelection);
  const use = useStore((s) => s.use);
  const farArr = useStore((s) => s.far);
  const [farMode, setFarMode] = useState<"keep" | "set">("keep");
  const [farValue, setFarValue] = useState(6);
  const [zoning, setZoning] = useState<ZoningSummary | null>(null);
  // What zoning allows on the selection, shown next to the FAR control (usability finding F9)
  useEffect(() => {
    setZoning(null);
    if (!selected.size || farMode !== "set") return;
    const t = window.setTimeout(() => api.zoningSummary([...selected]).then(setZoning).catch(() => undefined), 250);
    return () => window.clearTimeout(t);
  }, [selected, farMode]);
  if (!meta) return null;
  const n = selected.size;
  const currentUses = new Set<number>();
  selected.forEach((i) => currentUses.add(use[i]));
  const only = n === 1 ? [...selected][0] : null;
  const onlyFar = only !== null && !Number.isNaN(farArr[only]) ? farArr[only] : null;
  return (
    <div className={`palette ${compact ? "compact" : ""}`}>
      <div className="palette-head">
        <div className="eyebrow">{n ? `${n.toLocaleString()} parcel${n > 1 ? "s" : ""} selected` : "Land uses"}</div>
        {n > 0 && (
          <button className="link" onClick={clear}>
            clear
          </button>
        )}
      </div>
      {!n && (
        <div className="muted small palette-hint">
          Click a parcel (Shift-click to add) or use box, lasso, block or search. Then pick a new use. Keys 1–9 also
          work.
        </div>
      )}
      <div className="palette-grid">
        {meta.land_uses.map((u, k) => {
          const isCurrent = n > 0 && currentUses.size === 1 && currentUses.has(k);
          return (
            <button
              key={u.key}
              className={`use-btn ${isCurrent ? "current" : ""}`}
              disabled={!n}
              onClick={() => paint(u.key, undefined, u.built && farMode === "set" ? farValue : null)}
              title={n ? `Change ${n} parcel(s) to ${u.label}` : u.label}
            >
              <span className="swatch lg" style={{ background: u.color }} />
              <span className="use-label">{u.label}</span>
              {!compact && <span className="use-count">{countUse(use, k).toLocaleString()}</span>}
            </button>
          );
        })}
      </div>
      {!compact && (
        <div className="density card">
          <div className="eyebrow">Density for built uses</div>
          <label className="check">
            <input type="radio" checked={farMode === "keep"} onChange={() => setFarMode("keep")} /> Keep existing building
            (or zoning default if empty)
          </label>
          <label className="check">
            <input type="radio" checked={farMode === "set"} onChange={() => setFarMode("set")} /> Set floor area ratio
          </label>
          {farMode === "set" && (
            <div className="far-row">
              <input
                type="range"
                min={0}
                max={15}
                step={0.5}
                value={farValue}
                onChange={(e) => setFarValue(Number(e.target.value))}
              />
              <input
                type="number"
                min={0}
                max={30}
                step={0.1}
                value={farValue}
                onChange={(e) => setFarValue(Math.max(0, Math.min(30, Number(e.target.value))))}
              />
            </div>
          )}
          {n > 0 && farMode === "set" && zoning && (
            <div className="muted small zoning-note">
              {zoning.has_zoning ? (
                <>
                  Zoning allows up to FAR <b>{fmtRange(zoning.max_far)}</b> here (built now: median{" "}
                  {zoning.built_far.median.toFixed(1)})
                  {Object.keys(zoning.districts).length > 0 && <> · {Object.keys(zoning.districts).slice(0, 3).join(", ")}</>}.
                  {farValue > zoning.max_far.max + 1e-9 && (
                    <div className="bad">FAR {farValue} is above the zoning maximum on every selected parcel.</div>
                  )}
                  {farValue > zoning.max_far.min + 1e-9 && farValue <= zoning.max_far.max + 1e-9 && (
                    <div className="warn">FAR {farValue} is above the zoning maximum on some selected parcels.</div>
                  )}
                </>
              ) : (
                <>
                  No zoning data in this city: capacity uses the built density of nearby lots (up to{" "}
                  {fmtRange(zoning.max_far)} here; built now: median {zoning.built_far.median.toFixed(1)}).
                </>
              )}
            </div>
          )}
          {n > 0 && farMode === "set" && (
            <button className="wide" onClick={() => setFar(farValue)}>
              Apply FAR {farValue} to selection
            </button>
          )}
          {onlyFar !== null && <div className="muted small">This parcel has a proposed FAR of {onlyFar.toFixed(1)}.</div>}
        </div>
      )}
    </div>
  );
}

function fmtRange(r: { min: number; max: number }) {
  return r.min === r.max ? r.max.toFixed(1) : `${r.min.toFixed(1)}–${r.max.toFixed(1)}`;
}

const cache = new WeakMap<Int16Array, Map<number, number>>();
function countUse(use: Int16Array, k: number) {
  let m = cache.get(use);
  if (!m) {
    m = new Map();
    for (let i = 0; i < use.length; i++) m.set(use[i], (m.get(use[i]) ?? 0) + 1);
    cache.set(use, m);
  }
  return m.get(k) ?? 0;
}
