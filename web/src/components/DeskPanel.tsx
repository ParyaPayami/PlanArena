import { useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { compact } from "../format";

export default function DeskPanel() {
  const meta = useStore((s) => s.meta)!;
  const selected = useStore((s) => s.selected);
  const highlight = useStore((s) => s.highlight);
  const setHighlight = useStore((s) => s.setHighlight);
  const selectMany = useStore((s) => s.selectMany);
  const notify = useStore((s) => s.notify);
  const negotiation = useStore((s) => s.negotiation);
  const ev = useStore((s) => s.evaluation);
  const [feet, setFeet] = useState(500);
  const [notice, setNotice] = useState<{ count: number; feet: number; parcels: { i: number; bbl: number; address: string; use: string | null }[] } | null>(null);
  const [title, setTitle] = useState("Land-use study");
  const [busy, setBusy] = useState(false);
  const cap = meta.capacity_city;

  const runRadius = async () => {
    if (!selected.size) return notify("Select the project parcels first", "bad");
    setBusy(true);
    try {
      const r = await api.radius([...selected], feet);
      setNotice(r);
      setHighlight({ key: `radius-${Date.now()}`, parcels: new Set(r.parcels.map((p) => p.i)), color: [255, 196, 0], label: `${feet} ft notice radius` });
    } finally {
      setBusy(false);
    }
  };

  const exportNotice = () => {
    if (!notice) return;
    const rows = ["bbl,address,land_use", ...notice.parcels.map((p) => `${p.bbl},"${p.address.replace(/"/g, '""')}",${p.use ?? ""}`)];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv" }));
    a.download = `notice-radius-${notice.feet}ft.csv`;
    a.click();
  };

  const toggleSoft = async () => {
    if (highlight?.label.startsWith("Soft sites")) return setHighlight(undefined);
    const r = await api.softSites();
    setHighlight({ key: "soft", parcels: new Set(r.parcels), color: [0, 220, 200], label: "Soft sites" });
    notify(`${r.parcels.length} soft sites: ${r.rule}`, "info");
  };

  return (
    <div className="panel-pad">
      <h3>Planner's desk</h3>
      <p className="muted small">
        Everyday planning tasks: development capacity, soft-site inventory, public-notice radius, and a draft staff
        report.
      </p>

      <div className="card">
        <div className="eyebrow">City development capacity (current zoning)</div>
        <div className="kv">
          <span>Zoning capacity</span>
          <b>{compact(cap.zoning_capacity_sqft)} sq ft</b>
          <span>Built</span>
          <b>{compact(cap.built_sqft)} sq ft</b>
          <span>Unused capacity</span>
          <b>{compact(cap.unused_capacity_sqft)} sq ft</b>
          <span>Soft sites</span>
          <b>{cap.soft_sites.toLocaleString()}</b>
        </div>
        <button className="wide" onClick={toggleSoft}>
          {highlight?.label.startsWith("Soft sites") ? "Hide soft sites" : "Show soft sites on the map"}
        </button>
        <div className="muted small">{cap.soft_site_rule}. A screening rule, not a development forecast.</div>
      </div>

      <div className="card mt">
        <div className="eyebrow">Public notice radius</div>
        <div className="far-row">
          <input type="range" min={100} max={2640} step={50} value={feet} onChange={(e) => setFeet(Number(e.target.value))} />
          <span className="nowrap">{feet} ft</span>
        </div>
        <button className="wide" disabled={busy || !selected.size} onClick={runRadius}>
          {selected.size ? `Find parcels within ${feet} ft of ${selected.size} selected` : "Select project parcels first"}
        </button>
        {notice && (
          <>
            <div className="small mt">
              <b>{notice.count.toLocaleString()}</b> parcels to notify. They are highlighted on the map.
            </div>
            <div className="row gap">
              <button onClick={exportNotice}>Export mailing list (CSV)</button>
              <button onClick={() => selectMany(notice.parcels.map((p) => p.i), false)}>Select them</button>
              <button onClick={() => { setNotice(null); setHighlight(undefined); }}>Clear</button>
            </div>
            <div className="muted small">
              Lists BBL and address. Add owner-of-record names from the assessor roll when you send notices.
            </div>
          </>
        )}
      </div>

      <div className="card mt">
        <div className="eyebrow">Staff report draft</div>
        <input className="text" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
        <button
          className="primary wide"
          disabled={!ev?.n_changed}
          onClick={() => api.openReport(useStore.getState().changes(), title, "", negotiation ?? undefined)}
        >
          Open printable staff report
        </button>
        <div className="muted small">
          Built only from engine outputs: impacts with sensitivity ranges, capacity, screening flags, negotiation
          outcome, and data provenance. Print it to PDF from the browser.
        </div>
      </div>
    </div>
  );
}
