import { useEffect, useMemo, useState } from "react";
import CityMap, { type MapMode } from "../components/CityMap";
import Scoreboard from "../components/Scoreboard";
import Palette from "../components/Palette";
import ParcelInspector from "../components/ParcelInspector";
import AIPanel from "../components/AIPanel";
import AgentsPanel from "../components/AgentsPanel";
import StudiesPanel from "../components/StudiesPanel";
import DeskPanel from "../components/DeskPanel";
import DataPanel from "../components/DataPanel";
import MethodsDialog from "../components/MethodsDialog";
import SearchBox from "../components/SearchBox";
import Toast from "../components/Toast";
import { api } from "../api";
import { useStore, type Tab } from "../store";

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "impact", label: "Impact", icon: "📊" },
  { key: "ai", label: "Optimize", icon: "✨" },
  { key: "agents", label: "Negotiate", icon: "🤝" },
  { key: "studies", label: "Studies", icon: "🗂" },
  { key: "desk", label: "Desk", icon: "🧭" },
  { key: "data", label: "Import/Export", icon: "⇅" },
];

const TOOLS: { key: MapMode; label: string; icon: string; tip: string }[] = [
  { key: "select", label: "Select", icon: "👆", tip: "Click to select; Shift-click adds (S)" },
  { key: "box", label: "Box", icon: "▭", tip: "Drag a rectangle (B)" },
  { key: "lasso", label: "Lasso", icon: "➰", tip: "Draw around parcels (L)" },
  { key: "block", label: "Block", icon: "▦", tip: "Click to select a whole tax block (K)" },
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
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if ((e.metaKey || e.ctrlKey) && e.key === "z") {
        e.preventDefault();
        if (e.shiftKey) s.redo();
        else s.undo();
      } else if (e.key === "Escape") {
        s.clearSelection();
        setMode("select");
      } else if (e.key === "b") setMode("box");
      else if (e.key === "l") setMode("lasso");
      else if (e.key === "k") setMode("block");
      else if (e.key === "s") setMode("select");
      else if (/^[1-9]$/.test(e.key) && s.selected.size) s.paint(meta.land_uses[Number(e.key) - 1].key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [s.selected, s.undo, s.redo]);

  const preview = useMemo(() => {
    if (!s.preview) return undefined;
    const m = new Map<number, number>();
    for (const [k, v] of Object.entries(s.preview.changes)) m.set(Number(k), s.useKeys.indexOf(typeof v === "string" ? v : v.use));
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
            <div className="brand-sub">
              {meta.city} · digital twin · {meta.n_parcels.toLocaleString()} parcels
            </div>
          </div>
        </div>
        <SearchBox />
        <div className="tools">
          <div className="seg" role="group" aria-label="Selection tool">
            {TOOLS.map((t) => (
              <button key={t.key} className={mode === t.key ? "on" : ""} onClick={() => setMode(t.key)} title={t.tip}>
                {t.icon} <span className="tool-label">{t.label}</span>
              </button>
            ))}
          </div>
          <button onClick={s.undo} disabled={!s.past.length} title="Undo (⌘Z)" aria-label="Undo">
            ↶
          </button>
          <button onClick={s.redo} disabled={!s.future.length} title="Redo (⇧⌘Z)" aria-label="Redo">
            ↷
          </button>
          <button onClick={s.reset} title="Back to the current land-use map">
            Reset
          </button>
          <button className={s.view3d ? "on" : ""} onClick={s.toggle3d} title="3D digital twin">
            {s.view3d ? "3D" : "2D"}
          </button>
          <button onClick={() => s.setMethodsOpen(true)} title="Data, methods and provenance" aria-label="Data and methods">
            ⓘ
          </button>
          <a className="button ghost" href="/play">
            📱 Play
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
          Data: {meta.source}. Zoning rules are simplified. Every coefficient has a source and a range.{" "}
          <button className="link" onClick={() => s.setMethodsOpen(true)}>
            Methods
          </button>
        </div>
      </aside>
      <main className="center">
        <CityMap
          data={data}
          landUses={meta.land_uses}
          use={s.use}
          far={s.far}
          version={s.version}
          selected={s.selected}
          selVersion={s.selVersion}
          preview={preview}
          highlight={s.highlight}
          focus={s.focus}
          view3d={s.view3d}
          mode={mode}
          initialViewState={initialViewState}
          onPick={(i, add) => (i < 0 ? s.clearSelection() : s.select(i, add))}
          onBox={(idx, add) => {
            s.selectMany(idx, add);
            setMode("select");
          }}
          onBlock={async (i, add) => {
            const b = await api.block(i);
            s.selectMany(b.parcels, add);
            s.notify(`Tax block ${b.block}: ${b.parcels.length} parcels`, "info");
          }}
          suggestionOverlay={suitOverlay ? suit : null}
        />
        <ParcelInspector />
      </main>
      <section className="right">
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.key} role="tab" aria-selected={s.tab === t.key} className={s.tab === t.key ? "on" : ""} onClick={() => s.setTab(t.key)}>
              <span>{t.icon}</span> {t.label}
            </button>
          ))}
        </nav>
        <div className="tab-body">
          {s.tab === "impact" && <Scoreboard />}
          {s.tab === "ai" && <AIPanel suitOverlay={suitOverlay} setSuitOverlay={setSuitOverlay} />}
          {s.tab === "agents" && <AgentsPanel />}
          {s.tab === "studies" && <StudiesPanel />}
          {s.tab === "desk" && <DeskPanel />}
          {s.tab === "data" && <DataPanel />}
        </div>
      </section>
      <MethodsDialog />
      <Toast />
    </div>
  );
}
