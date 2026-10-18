import { useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { PillarCards } from "./Scoreboard";
import ParetoExplorer from "./ParetoExplorer";
import type { ChangeValue, Evaluation } from "../types";

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
  const [result, setResult] = useState<{ changes: Record<string, ChangeValue>; evaluation: Evaluation; ms: number } | null>(null);
  const [startPlan, setStartPlan] = useState<Record<string, ChangeValue>>({});

  const run = async () => {
    setBusy(true);
    try {
      const sel = area === "selection" ? [...selected] : undefined;
      const scope = area === "selection" ? "affected" : area;
      const start = useStore.getState().changes();
      setStartPlan(start);
      const r = await api.suggest({
        scope, mode, changes: start, parcels: sel,
        max_change_share: budget / 100, respect_zoning: zoning,
      });
      setResult(r);
      setPreview({ label: "Recommended plan", changes: r.changes, evaluation: r.evaluation });
      notify(`AI suggests ${Object.keys(r.changes).filter((k) => JSON.stringify(start[k]) !== JSON.stringify(r.changes[k])).length} changes`, "good");
    } catch (e) {
      notify(String(e), "bad");
    } finally {
      setBusy(false);
    }
  };

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
        A search over land-use changes that scores each candidate with the impact engine and returns the best plan it
        finds. It is a recommendation for discussion, not a proven optimum. Zoning, landmarks, parks, public facilities
        and existing homes are protected, and conversions with no precedent are skipped.
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
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="balanced">Balanced: equal social, economic and environmental weight</option>
          <option value="consensus">Consensus: only changes every stakeholder gains from</option>
          {meta.stakeholders.map((s) => (
            <option key={s.key} value={s.key}>
              {s.icon} {s.name}'s priorities
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Change up to {budget}% of parcels</span>
        <input type="range" min={1} max={15} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
      </label>
      <label className="check">
        <input type="checkbox" checked={zoning} onChange={(e) => setZoning(e.target.checked)} /> Respect current zoning
      </label>
      <button className="primary wide" onClick={run} disabled={busy}>
        {busy ? "Searching…" : "✨ Find a recommended plan"}
      </button>

      {result && (
        <div className="card mt">
          <div className="eyebrow">
            AI plan · {Object.keys(aiOnly).length} AI change{Object.keys(aiOnly).length === 1 ? "" : "s"}
            {Object.keys(userChanges).length ? ` on top of your ${Object.keys(userChanges).length}` : ""} ·{" "}
            {(result.ms / 1000).toFixed(1)} s
          </div>
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
