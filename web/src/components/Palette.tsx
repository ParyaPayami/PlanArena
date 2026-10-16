import { useStore } from "../store";

export default function Palette({ compact = false }: { compact?: boolean }) {
  const meta = useStore((s) => s.meta);
  const selected = useStore((s) => s.selected);
  const paint = useStore((s) => s.paint);
  const clear = useStore((s) => s.clearSelection);
  const data = useStore((s) => s.data);
  if (!meta) return null;
  const n = selected.size;
  const currentUses = new Set<number>();
  const use = useStore.getState().use;
  selected.forEach((i) => currentUses.add(use[i]));
  return (
    <div className={`palette ${compact ? "compact" : ""}`}>
      <div className="palette-head">
        <div className="eyebrow">{n ? `${n} parcel${n > 1 ? "s" : ""} selected` : "Land uses"}</div>
        {n > 0 && (
          <button className="link" onClick={clear}>
            clear
          </button>
        )}
      </div>
      {!n && (
        <div className="muted small palette-hint">
          Click a parcel (Shift-click to add more, or use box select), then pick a new use.
        </div>
      )}
      <div className="palette-grid">
        {meta.land_uses.map((u, k) => {
          const isCurrent = n > 0 && currentUses.size === 1 && currentUses.has(k);
          const count = data ? countUse(use, k) : 0;
          return (
            <button
              key={u.key}
              className={`use-btn ${isCurrent ? "current" : ""}`}
              disabled={!n}
              onClick={() => paint(u.key)}
              title={n ? `Change ${n} parcel(s) to ${u.label}` : u.label}
            >
              <span className="swatch lg" style={{ background: u.color }} />
              <span className="use-label">{u.label}</span>
              {!compact && <span className="use-count">{count.toLocaleString()}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
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
