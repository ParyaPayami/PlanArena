import { useEffect, useMemo, useState } from "react";
import CityMap, { type MapMode } from "../components/CityMap";
import Scoreboard from "../components/Scoreboard";
import Palette from "../components/Palette";
import ParcelInspector from "../components/ParcelInspector";
import AIPanel from "../components/AIPanel";
import AgentsPanel from "../components/AgentsPanel";
import UploadPanel from "../components/UploadPanel";
import Toast from "../components/Toast";
import { api } from "../api";
import { useStore, type Tab } from "../store";

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "impact", label: "Impact", icon: "📊" },
  { key: "ai", label: "AI optimizer", icon: "✨" },
  { key: "agents", label: "Stakeholders", icon: "🤝" },
  { key: "upload", label: "Upload plan", icon: "⬆︎" },
];

export default function Studio() {
  const s = useStore();
  const [mode, setMode] = useState<MapMode>("select");
  const [suitOverlay, setSuitOverlay] = useState(false);
  const [suit, setSuit] = useState<{ top: number[]; p: number[] } | null>(null);
  const meta = s.meta!;
  const data = s.data!;

  useEffect(() => {
    if (suitOverlay && !suit) api.suitability().then(setSuit).catch(() => s.notify("GNN not trained yet", "bad"));
  }, [suitOverlay, suit]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT" || (e.target as HTMLElement)?.tagName === "SELECT") return;
      if ((e.metaKey || e.ctrlKey) && e.key === "z") {
        e.preventDefault();
        e.shiftKey ? s.redo() : s.undo();
      } else if (e.key === "Escape") s.clearSelection();
      else if (e.key === "b") setMode((m) => (m === "box" ? "select" : "box"));
      else if (/^[1-9]$/.test(e.key) && s.selected.size) s.paint(meta.land_uses[Number(e.key) - 1].key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [s.selected, s.undo, s.redo]);

  const preview = useMemo(() => {
    if (!s.preview) return undefined;
    const m = new Map<number, number>();
    for (const [k, v] of Object.entries(s.preview.changes)) m.set(Number(k), s.useKeys.indexOf(v));
    return m;
  }, [s.preview, s.useKeys]);

  const [w, so, ea, no] = meta.bbox;
  const initialViewState = useMemo(
    () => ({ longitude: (w + ea) / 2 + 0.012, latitude: (so + no) / 2 - 0.035, zoom: 12.4, pitch: 0, bearing: -29 }),
    [],
  );

  return (
    <div className="studio">
      <header className="topbar">
        <div className="brand">
          <span className="logo" />
          <div>
            <div className="brand-name">PlanArena</div>
            <div className="brand-sub">{meta.city} · digital twin · {meta.n_parcels.toLocaleString()} parcels</div>
          </div>
        </div>
        <div className="tools">
          <div className="seg">
            <button className={mode === "select" ? "on" : ""} onClick={() => setMode("select")} title="Click to select (Shift adds)">
              👆 Select
            </button>
            <button className={mode === "box" ? "on" : ""} onClick={() => setMode("box")} title="Drag a box to select (B)">
              ▭ Box
            </button>
          </div>
          <button onClick={s.undo} disabled={!s.past.length} title="Undo (⌘Z)">
            ↶
          </button>
          <button onClick={s.redo} disabled={!s.future.length} title="Redo (⇧⌘Z)">
            ↷
          </button>
          <button onClick={s.reset} title="Back to the current land-use map">
            Reset
          </button>
          <button className={s.view3d ? "on" : ""} onClick={s.toggle3d} title="3D digital twin">
            {s.view3d ? "3D" : "2D"}
          </button>
          <a className="button ghost" href="/play">
            📱 Play mode
          </a>
        </div>
      </header>
      <aside className="left">
        <Palette />
        {s.preview && (
          <div className="preview-banner">
            Previewing <b>{s.preview.label}</b>
            <button className="link" onClick={() => s.setPreview(undefined)}>
              close
            </button>
          </div>
        )}
        <div className="sources muted small">
          Data: {meta.source}. Zoning rules simplified. Indicators marked ≈ use provisional coefficients.
        </div>
      </aside>
      <main className="center">
        <CityMap
          data={data}
          landUses={meta.land_uses}
          use={s.use}
          version={s.version}
          selected={s.selected}
          selVersion={s.selVersion}
          preview={preview}
          view3d={s.view3d}
          mode={mode}
          initialViewState={initialViewState}
          onPick={(i, add) => (i < 0 ? s.clearSelection() : s.select(i, add))}
          onBox={(idx, add) => {
            s.selectMany(idx, add);
            setMode("select");
          }}
          suggestionOverlay={suitOverlay ? suit : null}
        />
        <ParcelInspector />
      </main>
      <section className="right">
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.key} className={s.tab === t.key ? "on" : ""} onClick={() => s.setTab(t.key)}>
              <span>{t.icon}</span> {t.label}
            </button>
          ))}
        </nav>
        <div className="tab-body">
          {s.tab === "impact" && <Scoreboard />}
          {s.tab === "ai" && <AIPanel suitOverlay={suitOverlay} setSuitOverlay={setSuitOverlay} />}
          {s.tab === "agents" && <AgentsPanel />}
          {s.tab === "upload" && <UploadPanel />}
        </div>
      </section>
      <Toast />
    </div>
  );
}
