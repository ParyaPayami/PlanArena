import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";

const fmt = (v: unknown) => (typeof v === "number" ? String(Number(v.toPrecision(4))) : String(v));

type Coef = { value?: number; low?: number; high?: number; status?: string; source?: string; [k: string]: unknown };

export default function MethodsDialog() {
  const open = useStore((s) => s.methodsOpen);
  const setOpen = useStore((s) => s.setMethodsOpen);
  const meta = useStore((s) => s.meta);
  const [audit, setAudit] = useState<{ valid: boolean; rows: number } | null>(null);
  useEffect(() => {
    if (open) api.audit().then((a) => setAudit(a.verify));
  }, [open]);
  if (!open || !meta) return null;
  const coef = meta.coefficients as Record<string, Coef | Record<string, Coef>>;
  const rows: { group: string; key: string; c: Coef; status?: string; source?: string }[] = [];
  for (const [group, v] of Object.entries(coef)) {
    if (group === "version" || group === "derived" || typeof v !== "object" || v === null) continue;
    const g = v as Record<string, unknown>;
    if ("value" in g) rows.push({ group, key: "", c: g as Coef, status: g.status as string, source: g.source as string });
    else
      for (const [k, c] of Object.entries(g)) {
        if (c && typeof c === "object" && "value" in (c as object))
          rows.push({ group, key: k, c: c as Coef, status: (g.status as string) ?? (c as Coef).status, source: (g.source as string) ?? (c as Coef).source });
      }
  }
  const cv = meta.models.cv_summary;
  const ev = meta.models.emissions_validation;
  return (
    <div className="modal-back" onClick={() => setOpen(false)}>
      <div className="modal methods" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Data and methods">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Data &amp; methods</h2>
          <button onClick={() => setOpen(false)} aria-label="Close">✕</button>
        </div>
        <h4>Source</h4>
        <div className="kv">
          <span>Dataset</span>
          <b>{meta.source}</b>
          <span>SHA-256</span>
          <b className="mono">{meta.source_sha256}</b>
          <span>Parcels</span>
          <b>{meta.n_parcels.toLocaleString()}</b>
          {Object.entries(meta.data_quality ?? {}).map(([k, v]) => (
            <span key={k} style={{ display: "contents" }}>
              <span>{k.replace(/_/g, " ")}</span>
              <b>{v.toLocaleString()}</b>
            </span>
          ))}
          <span>Audit log</span>
          <b className={audit?.valid ? "good" : "bad"}>
            {audit ? (audit.valid ? `chain verified · ${audit.rows} events` : "chain broken") : "…"}
          </b>
        </div>
        <h4>Method</h4>
        <ul className="small">
          <li>Baseline = observed MapPLUTO values. Only changed parcels are modelled, so undoing a change restores the baseline exactly.</li>
          <li>
            A change of use keeps the existing building; an empty lot is built to the zoning FAR × {String((meta.coefficients as Record<string, Record<string, Coef>>).assumptions?.buildout_utilization?.value ?? 0.8)}. A proposed FAR overrides both.
          </li>
          <li>Access indicators use a 50 m grid convolved with 400 m and 800 m walk disks.</li>
          <li>
            Ranges are a <i>sensitivity envelope</i> from low and high coefficient variants (empirical Q25/Q75 or published ranges).
            They are not calibrated prediction intervals.
          </li>
          <li>Zoning is a simplified rules-as-code screen ({meta.zoning_rules}). It is not a legal compliance determination.</li>
          <li>The AI agents decide through an auditable game-theory engine. No language model makes a decision.</li>
        </ul>
        <h4>Coefficient register</h4>
        <table className="coef">
          <thead>
            <tr>
              <th>Coefficient</th>
              <th>Value</th>
              <th>Range</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.group + r.key} title={r.source}>
                <td>
                  {r.group.replace(/_/g, " ")}
                  {r.key ? ` · ${r.key.replace(/_/g, " ")}` : ""}
                </td>
                <td>{fmt(r.c.value)}</td>
                <td>{r.c.low !== undefined ? `${fmt(r.c.low)} – ${fmt(r.c.high)}` : ""}</td>
                <td className={r.status === "provisional" ? "warn" : ""}>{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <h4>Derived from the city's data</h4>
        <pre className="derived">{JSON.stringify(meta.derived, null, 1)}</pre>
        {cv && (
          <>
            <h4>Model validation (spatial-block cross-validation)</h4>
            <ul className="small">
              {Object.entries(cv).map(([k, m]) => (
                <li key={k}>
                  {k.replace(/_/g, " ")}:{" "}
                  {Object.entries(m)
                    .map(([mk, v]) => `${mk} ${v.mean.toFixed(3)} ± ${v.sd.toFixed(3)}`)
                    .join(", ")}
                </li>
              ))}
            </ul>
          </>
        )}
        {ev && (
          <>
            <h4>Emissions check against metered buildings (LL84 2024)</h4>
            <ul className="small">
              <li>
                {Number(ev.n_buildings).toLocaleString()} buildings matched by BBL · log–log r {ev.log_log_r} · median
                absolute error {Math.round(Number(ev.median_abs_pct_error) * 100)}%
              </li>
              <li>
                Total: modelled {ev.modelled_mt} Mt vs metered {ev.observed_mt} Mt (ratio {ev.aggregate_ratio_modelled_to_observed})
              </li>
              <li className="muted">{String(ev.note)}</li>
            </ul>
          </>
        )}
        <div className="muted small">
          Version {meta.version}. Source page:{" "}
          <a href={meta.source_url} target="_blank" rel="noreferrer">
            NYC DCP MapPLUTO
          </a>
          .
        </div>
      </div>
    </div>
  );
}
