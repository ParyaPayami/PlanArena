import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Certificate } from "../api";
import { useStore } from "../store";
import { PillarCards } from "./Scoreboard";
import ParetoExplorer from "./ParetoExplorer";
import TradeoffTriangle, { type PillarWeights } from "./TradeoffTriangle";
import type { ChangeValue, Evaluation } from "../types";

const EQUAL: PillarWeights = { social: 1 / 3, economic: 1 / 3, environmental: 1 / 3 };

function certificateText(c: Certificate | null | undefined): { text: string; tone: string } | null {
  if (!c) return null;
  const fast = c.fast_objective !== undefined && c.objective && c.objective > 1e-9
    ? ` The fast plan shown first reached ${Math.round((100 * Math.max(0, c.fast_objective)) / c.objective)}% of it.`
    : "";
  if (c.status === "optimal") return { text: `✓ Optimal: certified, no feasible plan scores higher.${fast}`, tone: "good" };
  if (c.status === "gap" && c.rel_gap !== undefined && Number.isFinite(c.rel_gap))
    return { text: `Within ${(100 * c.rel_gap).toFixed(1)}% of the optimum (certified bound).${fast}`, tone: "info" };
  return { text: `Best plan found, not certified${c.reason ? `: ${c.reason}` : ""}`, tone: "muted" };
}

interface Props {
  suitOverlay: boolean;
  setSuitOverlay: (b: boolean) => void;
}

export default function AIPanel({ suitOverlay, setSuitOverlay }: Props) {
  const meta = useStore((s) => s.meta)!;
  const selected = useStore((s) => s.selected);
  const preview = useStore((s) => s.preview);
  const setPreview = useStore((s) => s.setPreview);
  const applyChanges = useStore((s) => s.applyChanges);
  const notify = useStore((s) => s.notify);
  const [area, setArea] = useState("cd:103");
  const [mode, setMode] = useState("balanced");
  const [budget, setBudget] = useState(5);
  const [zoning, setZoning] = useState(true);
  const [busy, setBusy] = useState(false);
  const [certifying, setCertifying] = useState(false);
  const [result, setResult] = useState<{ changes: Record<string, ChangeValue>; evaluation: Evaluation; ms: number; certificate?: Certificate | null } | null>(null);
  const [startPlan, setStartPlan] = useState<Record<string, ChangeValue>>({});
  const [custom, setCustom] = useState<PillarWeights | null>(null);
  const seq = useRef(0);
  const dragBusy = useRef(false);
  const dragNext = useRef<PillarWeights | null>(null);
  const optimizeRequest = useStore((s) => s.optimizeRequest);

  // The triangle shows the weights in use: the custom trade-off, or each stakeholder's pillar mix.
  const shown = useMemo<PillarWeights>(() => {
    if (custom) return custom;
    const sh = meta.stakeholders.find((x) => x.key === mode);
    if (!sh) return EQUAL;
    const pw: PillarWeights = { social: 0, economic: 0, environmental: 0 };
    for (const ind of meta.indicators) pw[ind.pillar as keyof PillarWeights] += sh.weights[ind.key] ?? 0;
    return pw;
  }, [custom, mode, meta]);

  const request = (areaKey: string, w: PillarWeights | null) => {
    const sel = areaKey === "selection" ? [...useStore.getState().selected] : undefined;
    const start = useStore.getState().changes();
    return {
      start,
      body: {
        scope: areaKey === "selection" ? "affected" : areaKey, mode: w ? "balanced" : mode,
        pillar_weights: w ?? undefined, changes: start, parcels: sel,
        max_change_share: budget / 100, respect_zoning: zoning,
      },
    };
  };

  /** Fast plan first (shown at once), then the exact search, which certifies it or finds a better one. */
  const run = async (areaKey = area, w: PillarWeights | null = custom) => {
    const id = ++seq.current;
    setBusy(true);
    try {
      const { start, body } = request(areaKey, w);
      setStartPlan(start);
      const r = await api.suggest({ ...body, method: "fast" });
      if (id !== seq.current) return;
      setResult({ ...r, certificate: undefined });
      setPreview({ label: "Recommended plan", changes: r.changes, evaluation: r.evaluation });
      setBusy(false);
      if (areaKey === "city" || mode === "consensus") {
        setResult({ ...r, certificate: { status: "not certified", reason: areaKey === "city" ? "the whole city is too large to certify" : "consensus mode" } });
        return;
      }
      setCertifying(true);
      const x = await api.suggest({ ...body, method: "exact", time_limit: 20 });
      if (id !== seq.current) return;
      setResult(x);
      setPreview({ label: x.certificate?.status === "optimal" ? "Optimal plan" : "Recommended plan", changes: x.changes, evaluation: x.evaluation });
      const n = Object.keys(x.changes).filter((k) => JSON.stringify(start[k]) !== JSON.stringify(x.changes[k])).length;
      notify(`${x.certificate?.status === "optimal" ? "Optimal plan" : "Recommended plan"}: ${n} changes`, "good");
    } catch (e) {
      if (id === seq.current) notify(String(e), "bad");
    } finally {
      if (id === seq.current) {
        setBusy(false);
        setCertifying(false);
      }
    }
  };

  /** While the handle is dragged: fast plans only, newest weights first; a release runs the exact search. */
  const drag = async (w: PillarWeights) => {
    setCustom(w);
    if (dragBusy.current) {
      dragNext.current = w;
      return;
    }
    dragBusy.current = true;
    const id = ++seq.current;
    try {
      let cur: PillarWeights | null = w;
      while (cur) {
        dragNext.current = null;
        const { start, body } = request(area, cur);
        // a selection: the GNN policy's plan (milliseconds); otherwise the fast search without polishing
        const r = area === "selection" && !Object.keys(start).length
          ? await api.policy(body.parcels ?? [], cur, body.max_change_share).catch(() => api.suggest({ ...body, method: "fast", polish: 0 }))
          : await api.suggest({ ...body, method: "fast", polish: 0 });
        if (id !== seq.current) break;
        setStartPlan(start);
        setResult({ ...r, certificate: undefined });
        setPreview({ label: "Trade-off preview", changes: r.changes, evaluation: r.evaluation });
        cur = dragNext.current;
      }
    } catch (e) {
      notify(String(e), "bad");
    } finally {
      dragBusy.current = false;
    }
  };

  // "Optimize this area" on the map: optimize the selected parcels
  useEffect(() => {
    if (!optimizeRequest || !selected.size) return;
    setArea("selection");
    run("selection");
  }, [optimizeRequest]);

  // The optimizer starts from the current plan, so its result includes the planner's own edits.
  const userChanges = result ? startPlan : {};
  const aiOnly = result
    ? Object.fromEntries(Object.entries(result.changes).filter(([k, v]) => JSON.stringify(userChanges[k]) !== JSON.stringify(v)))
    : {};
  const transitions = (() => {
    if (!result) return [];
    const cur = useStore.getState().use;
    const m = new Map<string, number>();
    for (const [k, v] of Object.entries(aiOnly)) {
      const b = cur[Number(k)];
      const key = `${b >= 0 ? meta.land_uses[b].key : "unk"}→${typeof v === "string" ? v : v.use}`;
      m.set(key, (m.get(key) ?? 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  })();
  const lu = Object.fromEntries(meta.land_uses.map((u) => [u.key, u]));
  const cv = meta.models.cv_summary;
  const rd = meta.models.redevelopment;
  const overlay = useStore((s) => s.overlay);
  const setOverlay = useStore((s) => s.setOverlay);
  const toggleRedev = async (on: boolean) => {
    if (!on) return setOverlay(null);
    try {
      const r = await api.redevelopment();
      setSuitOverlay(false);
      // Brightness by rank: probabilities are small, so the rank shows the gradient across the city.
      setOverlay({ top: r.top, p: r.rank.map((x) => x ** 4), label: "Redevelopment likelihood (5 yr): colour = likely new use, brightness = likelihood rank" });
    } catch (e) {
      notify(String(e), "bad");
    }
  };

  return (
    <div className="panel-pad">
      <h3>Recommended plan</h3>
      <p className="muted small">
        A fast search shows a plan at once; an exact search (branch-and-bound) then proves it optimal for the impact
        engine’s score, or bounds how far it can be from the optimum. Optimal for the score is not a forecast: the
        score’s untested indicators are marked in the Impact tab. Zoning, landmarks, parks, public facilities and
        existing homes are protected, and conversions with no precedent are skipped.
      </p>
      <label className="field">
        <span>Area</span>
        <select value={area} onChange={(e) => setArea(e.target.value)}>
          <option value="selection" disabled={!selected.size}>
            Selected parcels ({selected.size})
          </option>
          {Object.entries(meta.levels).map(([cd, name]) => (
            <option key={cd} value={`cd:${cd}`}>
              {name}
            </option>
          ))}
          <option value="city">Whole city</option>
        </select>
      </label>
      <label className="field">
        <span>Priorities</span>
        <select value={custom ? "custom" : mode} onChange={(e) => { setCustom(null); setMode(e.target.value === "custom" ? "balanced" : e.target.value); }}>
          {custom && <option value="custom">Custom trade-off (drag the triangle)</option>}
          <option value="balanced">Balanced: equal social, economic and environmental weight</option>
          <option value="consensus">Consensus: only changes every stakeholder gains from</option>
          {meta.stakeholders.map((s) => (
            <option key={s.key} value={s.key}>
              {s.icon} {s.name}'s priorities
            </option>
          ))}
        </select>
      </label>
      <div className="field">
        <span>Trade-off: drag the handle; the map follows, and releasing it finds the optimum</span>
        <TradeoffTriangle
          weights={shown}
          disabled={mode === "consensus"}
          onDrag={drag}
          onRelease={(w) => { setCustom(w); run(area, w); }}
        />
      </div>
      <label className="field">
        <span>Change up to {budget}% of parcels</span>
        <input type="range" min={1} max={15} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
      </label>
      <label className="check">
        <input type="checkbox" checked={zoning} onChange={(e) => setZoning(e.target.checked)} /> Respect current zoning
      </label>
      <button className="primary wide" onClick={() => run()} disabled={busy || certifying}>
        {busy ? "Searching…" : certifying ? "Certifying the optimum…" : "✨ Find the optimal plan"}
      </button>

      {result && (
        <div className="card mt">
          <div className="eyebrow">
            AI plan · {Object.keys(aiOnly).length} AI change{Object.keys(aiOnly).length === 1 ? "" : "s"}
            {Object.keys(userChanges).length ? ` on top of your ${Object.keys(userChanges).length}` : ""} ·{" "}
            {(result.ms / 1000).toFixed(1)} s
          </div>
          {certifying && <div className="cert info">Proving optimality…</div>}
          {!certifying && certificateText(result.certificate) && (
            <div className={`cert ${certificateText(result.certificate)!.tone}`}>{certificateText(result.certificate)!.text}</div>
          )}
          <PillarCards ev={result.evaluation} />
          <div className="transitions">
            {transitions.map(([k, n]) => {
              const [a, b] = k.split("→");
              return (
                <div key={k} className="trans">
                  <span className="swatch" style={{ background: lu[a]?.color ?? "#555" }} />
                  {lu[a]?.label.split(" ")[0] ?? "?"} → <span className="swatch" style={{ background: lu[b].color }} />
                  {lu[b].label.split(" ")[0]} <b>×{n}</b>
                </div>
              );
            })}
          </div>
          <div className="row gap">
            <button
              className="primary"
              onClick={() => {
                applyChanges(result.changes, true);
                setPreview(undefined);
                notify("AI plan applied. Keep editing, or undo.", "good");
              }}
            >
              Apply plan
            </button>
            <button
              onClick={() =>
                preview ? setPreview(undefined) : setPreview({ label: "Recommended plan", changes: result.changes })
              }
            >
              {preview ? "Hide preview" : "Preview on map"}
            </button>
          </div>
        </div>
      )}

      <ParetoExplorer />

      <div className="card mt">
        <label className="check">
          <input type="checkbox" checked={suitOverlay} onChange={(e) => setSuitOverlay(e.target.checked)} />
          Show the pattern-consistent use for every parcel (LightGBM with a GNN embedding)
        </label>
        <div className="muted small">The use most consistent with each parcel’s surroundings today. It describes existing patterns, not what is desirable.</div>
        <label className="check mt">
          <input type="checkbox" checked={!!overlay && overlay.label.startsWith("Redevelopment")} onChange={(e) => toggleRedev(e.target.checked)} />
          Show where redevelopment is likely (next 5 years)
        </label>
        {rd && (
          <div className="muted small">
            Transition model trained on what was actually rebuilt in 2015–2025. On 2020–2025, which it never saw, its
            top 1% of lots were rebuilt {Math.round(Number(rd.test_precision_top1pct) * 100)}% of the time, against a{" "}
            {(Number(rd.test_base_rate) * 100).toFixed(1)}% base rate (AUC {rd.test_auc}). Colour = most likely new use.
          </div>
        )}
      </div>

      {cv && (
        <div className="card mt model-card">
          <div className="eyebrow">Model card: spatial cross-validation (5 folds, 600 m tiles)</div>
          <table>
            <thead>
              <tr>
                <th>Land-use fit</th>
                <th>Accuracy</th>
                <th>Log loss</th>
              </tr>
            </thead>
            <tbody>
              {[["suit_gnn", "Graph neural net"], ["suit_lightgbm", "LightGBM + neighbours"], ["suit_zoning_majority", "Zoning majority"]].map(([k, l]) =>
                cv[k] ? (
                  <tr key={k}>
                    <td>{l}</td>
                    <td>{cv[k].accuracy.mean.toFixed(3)}</td>
                    <td>{cv[k].log_loss.mean.toFixed(3)}</td>
                  </tr>
                ) : null,
              )}
            </tbody>
          </table>
          <table>
            <thead>
              <tr>
                <th>Tax-base value</th>
                <th>R²</th>
                <th>MAE (log)</th>
              </tr>
            </thead>
            <tbody>
              {[["value_gnn", "Graph neural net"], ["value_lightgbm", "LightGBM"], ["value_median_use_cd", "Median by use & district"]].map(([k, l]) =>
                cv[k] ? (
                  <tr key={k}>
                    <td>{l}</td>
                    <td>{cv[k].r2.mean.toFixed(3)}</td>
                    <td>{cv[k].mae_log.mean.toFixed(3)}</td>
                  </tr>
                ) : null,
              )}
            </tbody>
          </table>
          <div className="muted small">
            Each whole test area is hidden from the model, as when replanning a district. The GNN beats the simple
            baselines; tuned LightGBM is still slightly stronger.
          </div>
        </div>
      )}
    </div>
  );
}
