import { useRef, useState } from "react";
import { api, type ExactFront } from "../api";
import { useStore } from "../store";
import { fmtScore, PILLAR_COLOR } from "../format";
import type { ParetoResult } from "../types";

/** NSGA-III trade-off explorer for the selected parcels. Plot: social (x) × environmental (y), colour = economic. */
export default function ParetoExplorer() {
  const selected = useStore((s) => s.selected);
  const setPreview = useStore((s) => s.setPreview);
  const applyChanges = useStore((s) => s.applyChanges);
  const notify = useStore((s) => s.notify);
  const [res, setRes] = useState<ParetoResult | null>(null);
  const [pick, setPick] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [seed, setSeed] = useState(42);
  const [exact, setExact] = useState<ExactFront | null>(null);
  const [busyExact, setBusyExact] = useState(false);
  const dragging = useRef(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const runExact = async () => {
    if (!selected.size) return notify("Select up to 300 parcels first", "bad");
    if (selected.size > 300) return notify("The exact front handles up to 300 parcels", "bad");
    setBusyExact(true);
    try {
      const x = await api.frontier([...selected], useStore.getState().changes());
      setExact(x);
      // show the exact front in the same plot, with the balanced plan and each pillar's best plan as presets
      const front = x.front.map((f) => ({ ...f, changes: f.changes }));
      const best = (p: string) => front.reduce((bi, f, i) => (f.pillars[p] > front[bi].pillars[p] ? i : bi), 0);
      const bal = Math.max(0, front.findIndex((f) => f.balanced));
      const presets = [
        { name: "Balanced (knee)", weights: {}, index: bal },
        { name: "Best social", weights: {}, index: best("social") },
        { name: "Best economic", weights: {}, index: best("economic") },
        { name: "Best environmental", weights: {}, index: best("environmental") },
      ];
      setRes({ algorithm: "exact", seed: 0, generations: 0, n_parcels: selected.size, n_free: 0, front: front as never, presets,
               note: `Exact: ${Math.round(100 * x.certified_share)}% of the optimal plans certified, ${x.seconds.toFixed(0)} s.` });
      setPick(bal);
      if (front.length) setPreview({ label: "Balanced plan (exact)", changes: front[bal].changes });
    } catch (e) {
      notify(String(e), "bad");
    } finally {
      setBusyExact(false);
    }
  };

  const run = async () => {
    if (!selected.size) return notify("Select up to 300 parcels first", "bad");
    if (selected.size > 300) return notify("The Pareto explorer handles up to 300 parcels", "bad");
    setBusy(true);
    try {
      const r = await api.pareto([...selected], useStore.getState().changes(), seed);
      setExact(null);
      setRes(r);
      setPick(r.presets[0]?.index ?? 0);
      if (r.front.length) setPreview({ label: "Pareto plan", changes: r.front[r.presets[0]?.index ?? 0].changes });
    } catch (e) {
      notify(String(e), "bad");
    } finally {
      setBusy(false);
    }
  };

  const choose = (k: number) => {
    if (!res) return;
    setPick(k);
    setPreview({ label: "Pareto plan", changes: res.front[k].changes });
  };

  const W = 340, H = 210, P = 30;
  let plot = null;
  if (res && res.front.length) {
    const xs = res.front.map((f) => f.pillars.social);
    const ys = res.front.map((f) => f.pillars.environmental);
    const es = res.front.map((f) => f.pillars.economic);
    const [x0, x1] = [Math.min(0, ...xs), Math.max(0.01, ...xs)];
    const [y0, y1] = [Math.min(0, ...ys), Math.max(0.01, ...ys)];
    const [e0, e1] = [Math.min(...es), Math.max(...es)];
    const sx = (v: number) => P + ((v - x0) / (x1 - x0 || 1)) * (W - P * 1.5);
    const sy = (v: number) => H - P - ((v - y0) / (y1 - y0 || 1)) * (H - P * 1.6);
    plot = (
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="pareto-plot"
        role="img"
        aria-label="Pareto front: drag across it to move between optimal plans"
        onPointerDown={() => (dragging.current = true)}
        onPointerUp={() => (dragging.current = false)}
        onPointerLeave={() => (dragging.current = false)}
        onPointerMove={(ev) => {
          if (!dragging.current || !svgRef.current) return;
          const r = svgRef.current.getBoundingClientRect();
          const mx = ((ev.clientX - r.left) / r.width) * W, my = ((ev.clientY - r.top) / r.height) * H;
          let bk = 0, bd = Infinity;
          res.front.forEach((f, k) => {
            const dx = sx(f.pillars.social) - mx, dy = sy(f.pillars.environmental) - my;
            if (dx * dx + dy * dy < bd) { bd = dx * dx + dy * dy; bk = k; }
          });
          if (bk !== pick) choose(bk);
        }}
      >
        <line x1={sx(0)} x2={sx(0)} y1={P / 2} y2={H - P} className="axis0" />
        <line y1={sy(0)} y2={sy(0)} x1={P} x2={W - P / 2} className="axis0" />
        <text x={W / 2} y={H - 6} className="axis-label" fill={PILLAR_COLOR.social}>Social score →</text>
        <text x={10} y={H / 2} className="axis-label" fill={PILLAR_COLOR.environmental} transform={`rotate(-90 10 ${H / 2})`}>Environmental →</text>
        {res.front.map((f, k) => {
          const t = (f.pillars.economic - e0) / (e1 - e0 || 1);
          return (
            <circle
              key={k}
              cx={sx(f.pillars.social)}
              cy={sy(f.pillars.environmental)}
              r={pick === k ? 8 : 5.5}
              fill={`rgba(245, ${Math.round(120 + 100 * t)}, 0, ${0.35 + 0.65 * t})`}
              stroke={pick === k ? "#fff" : "rgba(255,255,255,.35)"}
              strokeWidth={pick === k ? 2 : 1}
              onClick={() => choose(k)}
              style={{ cursor: "pointer" }}
            >
              <title>{`Social ${fmtScore(f.pillars.social)} · Economic ${fmtScore(f.pillars.economic)} · Environmental ${fmtScore(f.pillars.environmental)} · ${f.n_changed} changes`}</title>
            </circle>
          );
        })}
      </svg>
    );
  }
  const sel = res && pick !== null ? res.front[pick] : null;
  return (
    <div className="card mt">
      <div className="eyebrow">Trade-off explorer {res?.algorithm === "exact" ? "(exact)" : "(NSGA-III)"}</div>
      <div className="muted small">
        The Pareto front of plans for the selected parcels: no plan on it can improve one pillar without losing
        another. NSGA-III explores it in seconds; the exact front solves each point to a certified optimum. Drag
        across the chart to move between plans.
      </div>
      <div className="row gap">
        <button className="primary" disabled={busy || !selected.size} onClick={run}>
          {busy ? "Evolving…" : `Explore trade-offs for ${selected.size || 0} parcels`}
        </button>
        <label className="small muted">
          seed <input className="seed" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
        </label>
      </div>
      <button className="wide mt" disabled={busyExact || !selected.size} onClick={runExact}>
        {busyExact ? "Solving each point exactly…" : "Exact front and trade-off rates (about a minute)"}
      </button>
      {exact && (
        <div className="small mt">
          {exact.balanced.efficiency_gap > 0.005 ? (
            <>
              Every pillar can rise by <b>{exact.balanced.efficiency_gap.toFixed(2)}</b> points at once over today’s land
              use (the balanced plan: how far today sits inside the front).
            </>
          ) : (
            <>No plan raises every pillar at once here: today’s land use is already on the front for at least one pillar.</>
          )}{" "}
          {Object.entries(exact.rates).map(([k, steps]) => {
            if (!steps.length) return null;
            const [a, b] = k.split("-");
            const v = Number(Object.entries(steps[0]).find(([kk]) => kk.includes("_per_"))?.[1] ?? NaN);
            return Number.isFinite(v) ? (
              <span key={k} className="muted">
                {" "}· from the best {a} plan, giving up one {a} point gains {Math.abs(v).toFixed(2)} {b}
              </span>
            ) : null;
          })}
          {exact.robust_share !== undefined && (
            <span className="muted"> · {Math.round(100 * exact.robust_share)}% of the front stays non-dominated under the low and high coefficients.</span>
          )}
        </div>
      )}
      {res?.note && <div className="muted small">{res.note}</div>}
      {plot}
      {res && res.front.length > 0 && (
        <>
          <div className="presets">
            {res.presets.map((p) => (
              <button key={p.name} className={`chip ${pick === p.index ? "on" : ""}`} onClick={() => choose(p.index)}>
                {p.name}
              </button>
            ))}
          </div>
          {sel && (
            <div className="small">
              {sel.n_changed} changes · social <b>{fmtScore(sel.pillars.social)}</b> · economic{" "}
              <b>{fmtScore(sel.pillars.economic)}</b> · environmental <b>{fmtScore(sel.pillars.environmental)}</b>
            </div>
          )}
          <div className="row gap">
            <button
              className="primary"
              onClick={() => {
                if (!sel) return;
                applyChanges(sel.changes);
                setPreview(undefined);
                notify("Pareto plan applied", "good");
              }}
            >
              Apply this plan
            </button>
            <button onClick={() => setPreview(undefined)}>Hide preview</button>
          </div>
          <div className="muted small">
            {res.front.length} non-dominated plans · {res.n_free} of {res.n_parcels} parcels could change · seed {res.seed} ·{" "}
            {res.generations} generations · study area {res.study_area_parcels?.toLocaleString()} parcels
          </div>
        </>
      )}
    </div>
  );
}
