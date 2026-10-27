import { useStore } from "../store";
import { compact, fmtDelta, fmtScore, fmtValue, PILLAR_COLOR, PILLAR_LABEL } from "../format";
import type { Evaluation, Pillar } from "../types";

function Gauge({ value, color, size = 74 }: { value: number; color: string; size?: number }) {
  const v = Math.max(-25, Math.min(25, value)) / 25; // ±25 points fills the gauge
  const r = size / 2 - 6;
  const cx = size / 2, cy = size / 2;
  const angle = Math.PI * (1 - (v + 1) / 2);
  const x = cx + r * Math.cos(angle), y = cy - r * Math.sin(angle);
  const mid = { x: cx, y: cy - r };
  const large = 0;
  const sweep = v >= 0 ? 1 : 0;
  return (
    <svg width={size} height={size / 2 + 10} viewBox={`0 0 ${size} ${size / 2 + 10}`} aria-hidden>
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`} stroke="var(--line)" strokeWidth={7} fill="none" strokeLinecap="round" />
      {Math.abs(v) > 0.002 && (
        <path
          d={`M ${mid.x} ${mid.y} A ${r} ${r} 0 ${large} ${sweep} ${x} ${y}`}
          stroke={v >= 0 ? color : "var(--bad)"}
          strokeWidth={7}
          fill="none"
          strokeLinecap="round"
        />
      )}
      <line x1={cx} y1={cy - r - 5} x2={cx} y2={cy - r + 5} stroke="var(--muted)" strokeWidth={1.5} />
    </svg>
  );
}

export function PillarCards({ ev }: { ev: Evaluation }) {
  const pillars: Pillar[] = ["social", "economic", "environmental"];
  return (
    <div className="pillars">
      {pillars.map((p) => {
        const top = ev.indicators
          .filter((r) => r.pillar === p && Math.abs(r.score) > 0.05)
          .sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
          .slice(0, 2);
        return (
          <div className="pillar" key={p}>
            <div className="pillar-head" style={{ color: PILLAR_COLOR[p] }}>
              {PILLAR_LABEL[p]}
            </div>
            <Gauge value={ev.pillars[p]} color={PILLAR_COLOR[p]} />
            <div className={`pillar-score ${ev.pillars[p] > 0.05 ? "good" : ev.pillars[p] < -0.05 ? "bad" : ""}`}>
              {fmtScore(ev.pillars[p])}
            </div>
            <div className="pillar-top">
              {top.length ? top.map((r) => (
                <span key={r.key} className={r.score >= 0 ? "good" : "bad"}>
                  {r.label.split(" ")[0]} {r.score >= 0 ? "▲" : "▼"}
                </span>
              )) : <span className="muted">steady</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Scoreboard() {
  const ev = useStore((s) => s.evaluation);
  const evaluating = useStore((s) => s.evaluating);
  const scope = useStore((s) => s.scope);
  const setScope = useStore((s) => s.setScope);
  const meta = useStore((s) => s.meta);
  if (!ev || !meta) return <div className="panel-pad muted">Calculating baseline…</div>;
  const missing = meta.missing_indicators ?? [];
  const changed = ev.n_changed;
  const pillars: Pillar[] = ["social", "economic", "environmental"];
  return (
    <div className="scoreboard">
      <div className="overall">
        <div>
          <div className="eyebrow" title="Totals score as % change; shares (access, mix, green cover) as percentage points. Each pillar is the mean of its indicators; the plan score is the weighted mean of the pillars. Positive is better.">
            Plan score <span className="help">?</span> {evaluating && <span className="spinner" />}
          </div>
          <div className={`overall-num ${ev.overall > 0.05 ? "good" : ev.overall < -0.05 ? "bad" : ""}`}>
            {changed ? fmtScore(ev.overall) : "0.0"}
          </div>
          <div className="muted small">
            {changed ? `${changed.toLocaleString()} parcel${changed > 1 ? "s" : ""} changed` : "Paint parcels to start a plan"}
          </div>
        </div>
        <div className="scope-chips">
          {[["affected", "Affected area"], ["city", "Whole city"]].map(([k, l]) => (
            <button key={k} className={`chip ${scope === k ? "on" : ""}`} onClick={() => setScope(k)}>
              {l}
            </button>
          ))}
        </div>
      </div>
      <div className="muted small scope-note">
        Scores are changes within {ev.scope === "city" ? "the whole city" : `the ${ev.scope_parcels.toLocaleString()} parcels within a 10-minute walk of your changes`}. Positive is better.
      </div>
      <PillarCards ev={ev} />
      {missing.length > 0 && (
        <div className="muted small scope-note">
          No data in this city for: {ev.indicators.filter((r) => missing.includes(r.key)).map((r) => r.label).join(", ")}.
        </div>
      )}
      {pillars.map((p) => (
        <div key={p} className="ind-group">
          <div className="ind-group-head" style={{ color: PILLAR_COLOR[p] }}>
            {PILLAR_LABEL[p]}
          </div>
          {ev.indicators
            .filter((r) => r.pillar === p && !missing.includes(r.key))
            .map((r) => {
              const w = Math.min(Math.abs(r.score), 25) / 25;
              return (
                <div className="ind-row" key={r.key} title={`${r.label}: ${fmtValue(r, r.baseline)} → ${fmtValue(r, r.scenario)} (${r.unit})`}>
                  <div className="ind-label">
                    {r.label}
                    {r.provisional && <span className="prov" title="Depends on provisional coefficients (see Sources)">≈</span>}
                  </div>
                  <div className="ind-bar">
                    <div className="ind-bar-mid" />
                    {Math.abs(r.score) > 0.01 && (
                      <div
                        className={`ind-bar-fill ${r.score >= 0 ? "pos" : "neg"}`}
                        style={{ width: `${w * 50}%`, [r.score >= 0 ? "left" : "right"]: "50%" } as React.CSSProperties}
                      />
                    )}
                  </div>
                  <div className={`ind-delta ${r.score > 0.01 ? "good" : r.score < -0.01 ? "bad" : "muted"}`}>
                    {fmtDelta(r, r.delta)}
                    {r.range && Math.abs(r.range[1] - r.range[0]) > 1e-9 && (
                      <div className="ind-range" title="Sensitivity range from low/high coefficient variants">
                        {fmtDelta(r, r.range[0]).replace("no change", "0")} … {fmtDelta(r, r.range[1]).replace("no change", "0")}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      ))}
      {changed > 0 && <ByUseTable ev={ev} />}
      {ev.capacity && <CapacityCard ev={ev} />}
      {ev.warnings.length > 0 && (
        <div className="warnings">
          {ev.warnings.map((w) => (
            <div key={w.type} className={`warning w-${w.type}`}>
              {w.type === "zoning" ? "⚖️" : w.type === "protected" ? "🏛️" : "🏠"} {w.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CapacityCard({ ev }: { ev: Evaluation }) {
  const b = ev.capacity!.baseline;
  const s = ev.capacity!.scenario;
  const d = (x: number) => (Math.abs(x) < 0.5 ? "·" : `${x > 0 ? "+" : "−"}${compact(Math.abs(x))}`);
  return (
    <div className="byuse">
      <div className="ind-group-head">Development capacity (zoning)</div>
      <table>
        <tbody>
          <tr>
            <td>Built floor area</td>
            <td>{compact(s.built_sqft)} sq ft</td>
            <td className={s.built_sqft >= b.built_sqft ? "good" : "bad"}>{d(s.built_sqft - b.built_sqft)}</td>
          </tr>
          <tr>
            <td>Unused zoning capacity</td>
            <td>{compact(s.unused_capacity_sqft)} sq ft</td>
            <td>{d(s.unused_capacity_sqft - b.unused_capacity_sqft)}</td>
          </tr>
          <tr>
            <td title={s.soft_site_rule}>Soft sites</td>
            <td>{s.soft_sites.toLocaleString()}</td>
            <td>{d(s.soft_sites - b.soft_sites)}</td>
          </tr>
          {s.plan_added_capacity_sqft > 0 && (
            <tr>
              <td>Capacity added by upzoning</td>
              <td>{compact(s.plan_added_capacity_sqft)} sq ft</td>
              <td className="good">≈{Math.round(s.plan_added_capacity_homes).toLocaleString()} homes</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ByUseTable({ ev }: { ev: Evaluation }) {
  const rows = ev.by_use.filter((r) => r.parcels !== 0 || Math.abs(r.homes) > 0.5 || Math.abs(r.jobs) > 0.5);
  if (!rows.length) return null;
  const n = (v: number) => (Math.abs(v) < 0.5 ? "·" : `${v > 0 ? "+" : "−"}${Math.abs(Math.round(v)).toLocaleString()}`);
  return (
    <div className="byuse">
      <div className="ind-group-head">Gains &amp; losses by land use</div>
      <table>
        <thead>
          <tr>
            <th />
            <th>Parcels</th>
            <th>Acres</th>
            <th>Homes</th>
            <th>Jobs</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.use}>
              <td>
                <span className="swatch" style={{ background: r.color }} /> {r.label}
              </td>
              <td className={r.parcels > 0 ? "good" : r.parcels < 0 ? "bad" : ""}>{n(r.parcels)}</td>
              <td>{Math.abs(r.acres) < 0.05 ? "·" : `${r.acres > 0 ? "+" : "−"}${Math.abs(r.acres).toFixed(1)}`}</td>
              <td>{n(r.homes)}</td>
              <td>{n(r.jobs)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
