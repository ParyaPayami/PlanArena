import { useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { ImportReview } from "../types";

const ISSUE_LABEL: Record<string, string> = {
  unmatched: "Parcel id not found",
  duplicates: "Duplicate parcel",
  unknown_uses: "Unknown land use",
  far_issues: "FAR not between 0 and 30",
};

export default function DataPanel() {
  const applyChanges = useStore((s) => s.applyChanges);
  const notify = useStore((s) => s.notify);
  const meta = useStore((s) => s.meta)!;
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<ImportReview | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const handle = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setReview(null);
    try {
      setReview(await api.importPlan(file));
    } catch (e) {
      notify(`Could not read the plan: ${e instanceof Error ? e.message : e}`, "bad");
    } finally {
      setBusy(false);
    }
  };

  const changes = () => useStore.getState().changes();
  const nChanges = Object.keys(changes()).length;

  return (
    <div className="panel-pad">
      <h3>Import a plan</h3>
      <p className="muted small">
        Bring in a proposed land-use plan. The tool first checks it against the authoritative parcel register, and you
        review the result before anything is applied. Imported geometry never replaces parcel boundaries.
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
        <div>{busy ? "Checking…" : "Drop CSV, GeoJSON, Shapefile (.zip) or GeoPackage, or click to browse"}</div>
        <input ref={input} type="file" accept=".csv,.geojson,.json,.zip,.gpkg" hidden onChange={(e) => handle(e.target.files?.[0])} />
      </div>
      <div className="muted small mt">
        Columns: <code>bbl</code> (or <code>i</code>), <code>land_use</code> (a key such as{" "}
        {meta.land_uses.slice(0, 3).map((u) => u.key).join(", ")}…, a label, or a MapPLUTO code 01–11), and an optional{" "}
        <code>far</code>.
      </div>
      <a className="button mt" href="/api/sample-plan.csv">
        Download a sample plan
      </a>

      {review && (
        <div className="card mt review">
          <div className="eyebrow">Review: {review.filename}</div>
          <div className="kv">
            <span>Rows read</span>
            <b>{review.rows.toLocaleString()}</b>
            <span>Valid changes</span>
            <b className="good">{review.valid_changes.toLocaleString()}</b>
            <span>Same as today</span>
            <b>{review.unchanged_rows.toLocaleString()}</b>
            {(["unmatched", "duplicates", "unknown_uses", "far_issues"] as const).map((k) => (
              <span key={k} style={{ display: "contents" }}>
                <span>{ISSUE_LABEL[k]}</span>
                <b className={review[k] ? "bad" : ""}>{review[k].toLocaleString()}</b>
              </span>
            ))}
          </div>
          {Object.entries(review.issues).some(([, v]) => v.length) && (
            <details>
              <summary className="small">Show issue rows</summary>
              <ul className="history">
                {Object.entries(review.issues).flatMap(([k, v]) =>
                  v.slice(0, 12).map((it, j) => (
                    <li key={`${k}${j}`}>
                      row {it.row}: {ISSUE_LABEL[k]} {String(it.id ?? it.value ?? "")}
                    </li>
                  )),
                )}
              </ul>
            </details>
          )}
          <div className="row gap">
            <button
              className="primary"
              disabled={!review.valid_changes}
              onClick={() => {
                applyChanges(review.changes, true);
                useStore.getState().setTab("impact");
                notify(`Applied ${review.valid_changes} changes from ${review.filename}`, "good");
                setReview(null);
              }}
            >
              Apply {review.valid_changes.toLocaleString()} changes
            </button>
            <button onClick={() => setReview(null)}>Discard</button>
          </div>
        </div>
      )}

      <h3 className="mt">Export</h3>
      <div className="muted small">{nChanges ? `${nChanges} changed parcels in the current plan.` : "The current plan has no changes."}</div>
      <div className="row gap">
        <button disabled={!nChanges} onClick={() => api.exportFile("csv", changes())}>CSV</button>
        <button disabled={!nChanges} onClick={() => api.exportFile("geojson", changes())}>GeoJSON</button>
        <button disabled={!nChanges} onClick={() => api.exportFile("provenance", changes())}>Report + provenance (JSON)</button>
        <button disabled={!nChanges} onClick={() => api.openReport(changes(), "PlanArena study")}>Printable report</button>
      </div>
      <div className="muted small mt">
        Every export records the source file's SHA-256, the coefficient register and the engine version.
      </div>
    </div>
  );
}
