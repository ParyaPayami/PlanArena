import { useEffect, useMemo, useState } from "react";
import CityMap, { type MapMode } from "../components/CityMap";
import Scoreboard from "../components/Scoreboard";
import Palette from "../components/Palette";
import ParcelInspector from "../components/ParcelInspector";
import AIPanel from "../components/AIPanel";
import VotePanel from "../components/VotePanel";
import StudiesPanel from "../components/StudiesPanel";
import DeskPanel from "../components/DeskPanel";
import DataPanel from "../components/DataPanel";
import MethodsDialog from "../components/MethodsDialog";
import SearchBox from "../components/SearchBox";
import CityPicker from "../components/CityPicker";
import FirstPlan from "../components/FirstPlan";
import Toast from "../components/Toast";
import { api, cityHref } from "../api";
import { useStore, type MapLayer, type Tab } from "../store";

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "impact", label: "Impact", icon: "📊" },
  { key: "ai", label: "Optimize", icon: "✨" },
  { key: "agents", label: "Vote", icon: "🗳" },
  { key: "studies", label: "Studies", icon: "🗂" },
  { key: "desk", label: "Desk", icon: "🧭" },
  { key: "data", label: "Import/Export", icon: "⇅" },
];

const LAYERS: { key: MapLayer; label: string; tip: string }[] = [
  { key: "edit", label: "Plan you edit", tip: "Your scenario: the land use you paint" },
  { key: "existing", label: "Existing", tip: "Official existing land use (the baseline)" },
  { key: "plan", label: "Adopted plan", tip: "The city's adopted land-use plan (future land use)" },
  { key: "zoning", label: "Zoning", tip: "The use each zoning district is mapped for" },
];

const TOOLS: { key: MapMode; label: string; icon: string; tip: string }[] = [
  { key: "select", label: "Select", icon: "👆", tip: "Click to select; Shift-click adds (S)" },
  { key: "box", label: "Box", icon: "▭", tip: "Drag a rectangle (B)" },
  { key: "lasso", label: "Lasso", icon: "➰", tip: "Draw around parcels (L)" },
  { key: "block", label: "Block", icon: "▦", tip: "Click to select a whole tax block (K)" },
];

/** Opening view of a city other than Manhattan: centred on the middle 90% of its parcels, so outlying annexes
 * (an airport, say) do not pull the view off the city. */
function parcelView(data: { lon: Float32Array; lat: Float32Array; n: number }, bbox: number[]) {
  const q = (a: Float32Array, f: number) => {
    const s = Array.from(a).filter(Number.isFinite).sort((x, y) => x - y);
    return s.length ? s[Math.floor(f * (s.length - 1))] : NaN;
  };
  let [x0, y0, x1, y1] = [q(data.lon, 0.05), q(data.lat, 0.05), q(data.lon, 0.95), q(data.lat, 0.95)];
  if (![x0, y0, x1, y1].every(Number.isFinite)) [x0, y0, x1, y1] = bbox;
  const zoom = Math.min(15, Math.log2(360 / Math.max(x1 - x0, (y1 - y0) * 1.4, 1e-4)) + 0.5);
  return { longitude: (x0 + x1) / 2, latitude: (y0 + y1) / 2, zoom, pitch: 0, bearing: 0 };
}

export default function Studio() {
  const s = useStore();
  const [mode, setMode] = useState<MapMode>("select");
  const [suitOverlay, setSuitOverlay] = useState(false);
  const [suit, setSuit] = useState<{ top: number[]; p: number[] } | null>(null);
  const meta = s.meta!;
  const data = s.data!;

  useEffect(() => {
    if (suitOverlay && !suit) api.suitability().then(setSuit).catch(() => s.notify("No pattern model for this city", "bad"));
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
    () =>
      meta.city_id === "manhattan"
        ? { longitude: (w + ea) / 2 + 0.012, latitude: (so + no) / 2 - 0.035, zoom: 12.4, pitch: 0, bearing: -29 }
        : parcelView(data, [w, so, ea, no]),
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
              <CityPicker /> · {meta.n_parcels.toLocaleString()} parcels
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
          <div className="seg" role="group" aria-label="Map layer">
            {LAYERS.map((l) => {
              const has = l.key === "edit" || !!meta.layers?.[l.key as "existing" | "plan" | "zoning"];
              return (
                <button
                  key={l.key}
                  className={s.mapLayer === l.key ? "on" : ""}
                  disabled={!has}
                  onClick={() => s.setMapLayer(l.key)}
                  title={has ? l.tip : `${meta.city} publishes no ${l.label.toLowerCase()} layer`}
                >
                  {l.label}
                </button>
              );
            })}
          </div>
          <button className={s.view3d ? "on" : ""} onClick={s.toggle3d} title="3D digital twin">
            {s.view3d ? "3D" : "2D"}
          </button>
          <button onClick={() => s.setMethodsOpen(true)} title="Data, methods and provenance" aria-label="Data and methods">
            ⓘ
          </button>
          <a className="button ghost" href={cityHref(meta.city_id, "/play")}>
            📱 Play
          </a>
        </div>
      </header>
      <aside className="left">
        <FirstPlan />
        <Palette />
        {s.overlay && (
          <div className="preview-banner">
            {s.overlay.label}
            <button className="link" onClick={() => s.setOverlay(null)}>
              close
            </button>
          </div>
        )}
        {s.preview && (
          <div className="preview-banner">
            Previewing <b>{s.preview.label}</b>
            <button className="link" onClick={() => s.setPreview(undefined)}>
              close
            </button>
          </div>
        )}
        <div className="sources muted small">
          Data: {meta.source}.{" "}
          {meta.zoning_rules.startsWith("none")
            ? "No zoning data here: every use is allowed and capacity uses the built density of nearby lots."
            : "Zoning rules are simplified."}{" "}
          Every coefficient has a source and a range.{" "}
          <button className="link" onClick={() => s.setMethodsOpen(true)}>
            Methods
          </button>
        </div>
      </aside>
      <main className="center">
        <CityMap
          tileZoom={meta.tile_zoom}
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
          suggestionOverlay={s.overlay ?? (suitOverlay ? suit : null)}
          classView={
            s.mapLayer !== "edit" && s.classLayers && meta.classes
              ? { cls: s.classLayers[s.mapLayer], classes: meta.classes, name: LAYERS.find((l) => l.key === s.mapLayer)!.label }
              : null
          }
        />
        {s.mapLayer !== "edit" && meta.classes && (
          <div className="map-legend class-legend">
            <b>{LAYERS.find((l) => l.key === s.mapLayer)!.label}</b>
            {meta.classes.map((c) => (
              <span key={c.key} className="legend-item">
                <span className="swatch" style={{ background: c.color }} /> {c.label}
              </span>
            ))}
            <span className="legend-item muted small">Grey: no value. Painting edits the plan you edit.</span>
          </div>
        )}
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
          {s.tab === "agents" && <VotePanel />}
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
