import { useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Evaluation } from "../types";

export default function UploadPanel() {
  const applyChanges = useStore((s) => s.applyChanges);
  const notify = useStore((s) => s.notify);
  const meta = useStore((s) => s.meta)!;
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Evaluation | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const handle = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    try {
      const r = await api.upload(file);
      setReport(r);
      if (r.changes) applyChanges(r.changes, true);
      notify(`Plan loaded: ${r.upload?.matched ?? 0} parcels changed`, "good");
    } catch (e) {
      notify(`Upload failed: ${e}`, "bad");
    } finally {
      setBusy(false);
    }
  };

  const exportPlan = () => {
    const changes = useStore.getState().changes();
    const rows = ["i,land_use", ...Object.entries(changes).map(([i, u]) => `${i},${u}`)];
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "planarena-plan.csv";
    a.click();
  };

  return (
    <div className="panel-pad">
      <h3>Evaluate a plan</h3>
      <p className="muted small">
        Upload a proposed land-use plan. It is applied to the city's digital twin and scored on social, economic and
        environmental outcomes.
      </p>
      <div
        className={`dropzone ${drag ? "drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handle(e.dataTransfer.files[0]);
        }}
        onClick={() => input.current?.click()}
      >
        <div className="drop-icon">⬆︎</div>
        <div>{busy ? "Evaluating…" : "Drop a .csv or .geojson here, or click to browse"}</div>
        <input ref={input} type="file" accept=".csv,.geojson,.json" hidden onChange={(e) => handle(e.target.files?.[0])} />
      </div>
      <div className="muted small mt">
        Each row or feature needs a parcel id (<code>bbl</code> or <code>i</code>) and a <code>land_use</code>. The
        land use can be a PlanArena key ({meta.land_uses.map((u) => u.key).join(", ")}), a full label, or a MapPLUTO
        LandUse code (01–11).
      </div>
      <div className="row gap mt">
        <a className="button" href="/api/sample-plan.csv">
          Download sample plan
        </a>
        <button onClick={exportPlan}>Export current plan</button>
      </div>
      {report?.upload && (
        <div className="card mt">
          <div className="eyebrow">Upload report</div>
          <div className="kv">
            <span>Rows read</span>
            <b>{report.upload.rows}</b>
            <span>Parcels changed</span>
            <b>{report.upload.matched}</b>
            <span>Unmatched ids</span>
            <b className={report.upload.unmatched ? "bad" : ""}>{report.upload.unmatched}</b>
            <span>Unknown uses</span>
            <b className={report.upload.unknown_uses.length ? "bad" : ""}>
              {report.upload.unknown_uses.join(", ") || "none"}
            </b>
          </div>
          <div className="muted small">The scoreboard on the Impact tab now shows this plan.</div>
        </div>
      )}
    </div>
  );
}
