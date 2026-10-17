import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { compact } from "../format";
import type { ParcelInfo } from "../types";

export default function ParcelInspector() {
  const selected = useStore((s) => s.selected);
  const meta = useStore((s) => s.meta);
  const version = useStore((s) => s.version);
  const [info, setInfo] = useState<ParcelInfo | null>(null);
  const [open, setOpen] = useState(true);
  const only = selected.size === 1 ? [...selected][0] : null;

  useEffect(() => {
    if (only === null) {
      setInfo(null);
      return;
    }
    let live = true;
    api.parcel(only).then((p) => live && setInfo(p)).catch(() => live && setInfo(null));
    return () => {
      live = false;
    };
  }, [only]);

  if (!info || !meta) return null;
  const lu = Object.fromEntries(meta.land_uses.map((u) => [u.key, u]));
  const cur = useStore.getState().use[info.i];
  const curKey = cur >= 0 ? meta.land_uses[cur].key : null;
  const suit = info.suitability
    ? Object.entries(info.suitability).sort((a, b) => b[1] - a[1]).slice(0, 4)
    : [];
  void version;
  return (
    <div className={`inspector ${open ? "" : "closed"}`}>
      <div className="inspector-head" onClick={() => setOpen(!open)}>
        <div>
          <div className="eyebrow">Parcel · BBL {info.bbl}</div>
          <div className="inspector-title">{info.address || "No address"}</div>
        </div>
        <span className="muted">{open ? "▾" : "▸"}</span>
      </div>
      {open && (
        <>
          <div className="kv">
            <span>Zoning</span>
            <b>
              {info.zone}
              {info.overlay ? ` / ${info.overlay}` : ""}
              {info.special_district ? ` · ${info.special_district}` : ""}
            </b>
            <span>Lot</span>
            <b>{compact(info.lot_area_sqft)} sq ft</b>
            <span>Building</span>
            <b>
              {compact(info.bldg_area_sqft)} sq ft · {info.floors || 0} fl
            </b>
            <span>Homes</span>
            <b>{info.units.toLocaleString()}</b>
            <span title="Assessed value, including tax-exempt property; not tax revenue">Assessed value</span>
            <b>${compact(info.assessed_value)}</b>
            {info.year_built > 0 && (
              <>
                <span>Built</span>
                <b>{info.year_built}</b>
              </>
            )}
          </div>
          {info.redevelopment && (
            <div className="redev" title="Transition model trained on observed 2015-2025 redevelopment (see Methods)">
              <span>Chance of redevelopment, next 5 years</span>
              <b>
                {(info.redevelopment.p * 100).toFixed(1)}%{" "}
                <span className="muted">
                  (higher than {Math.round(info.redevelopment.percentile * 100)}% of lots) · likely{" "}
                  {lu[info.redevelopment.likely_use]?.label.split(" ")[0] ?? info.redevelopment.likely_use}
                </span>
              </b>
            </div>
          )}
          {(info.landmark || info.historic_district) && (
            <div className="tag-row">
              {info.landmark && <span className="tag warn">Landmark</span>}
              {info.historic_district && <span className="tag warn">Historic district</span>}
            </div>
          )}
          <div className="eyebrow mt">Zoning allows</div>
          <div className="tag-row">
            {info.allowed_uses.map((k) => (
              <span key={k} className="tag" style={{ borderColor: lu[k]?.color }}>
                {lu[k]?.label}
              </span>
            ))}
          </div>
          {suit.length > 0 && (
            <>
              <div className="eyebrow mt">AI neighbourhood fit (GNN)</div>
              {suit.map(([k, p]) => (
                <div className="fit-row" key={k}>
                  <span className="swatch" style={{ background: lu[k].color }} />
                  <span className="fit-label">{lu[k].label}</span>
                  <div className="fit-bar">
                    <div style={{ width: `${p * 100}%`, background: lu[k].color }} />
                  </div>
                  <span className="fit-p">{Math.round(p * 100)}%</span>
                </div>
              ))}
            </>
          )}
          {curKey && (
            <>
              <div className="eyebrow mt">If this parcel became…</div>
              <table className="whatif">
                <thead>
                  <tr>
                    <th />
                    <th>Homes</th>
                    <th>Jobs</th>
                    <th title="Assessed value, including tax-exempt property; not tax revenue">Assessed value</th>
                  </tr>
                </thead>
                <tbody>
                  {meta.land_uses.map((u) => {
                    const v = info.per_use[u.key];
                    return (
                      <tr key={u.key} className={u.key === curKey ? "cur" : ""}>
                        <td>
                          <span className="swatch" style={{ background: u.color }} /> {u.label.split(" ")[0]}
                        </td>
                        <td>{Math.round(v.homes).toLocaleString()}</td>
                        <td>{Math.round(v.jobs).toLocaleString()}</td>
                        <td>${compact(v.value)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </div>
  );
}
