import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { fmtScore } from "../format";
import { PillarCards } from "./Scoreboard";

const SOLUTION_LABEL: Record<string, string> = {
  nash_bargaining: "Nash bargaining",
  kalai_smorodinsky: "Kalai–Smorodinsky",
  utilitarian: "Utilitarian (max total)",
  egalitarian: "Egalitarian (max worst-off)",
};

export default function AgentsPanel() {
  const meta = useStore((s) => s.meta)!;
  const neg = useStore((s) => s.negotiation);
  const setNeg = useStore((s) => s.setNegotiation);
  const setPreview = useStore((s) => s.setPreview);
  const applyChanges = useStore((s) => s.applyChanges);
  const notify = useStore((s) => s.notify);
  const [area, setArea] = useState("cd:103");
  const [busy, setBusy] = useState(false);
  const [shown, setShown] = useState(0);
  const [poa, setPoa] = useState<null | { price_of_anarchy: number | null; welfare_fragmented: number; welfare_cooperative: number }>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const agents = Object.fromEntries(meta.stakeholders.map((s) => [s.key, s]));

  const start = async () => {
    setBusy(true);
    setShown(0);
    setNeg(undefined);
    setPoa(null);
    try {
      const r = await api.negotiate({ scope: area, changes: useStore.getState().changes() });
      setNeg(r);
    } catch (e) {
      notify(String(e), "bad");
    } finally {
      setBusy(false);
    }
  };

  // Reveal the transcript line by line, like a live negotiation.
  useEffect(() => {
    if (!neg) return;
    if (shown >= neg.transcript.length) return;
    const t = window.setTimeout(() => setShown((n) => n + 1), shown < 5 ? 260 : 120);
    return () => window.clearTimeout(t);
  }, [neg, shown]);
  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [shown]);

  const done = neg && shown >= neg.transcript.length;
  const agreed = neg?.plans.find((p) => p.id === neg.agreed_plan);
  return (
    <div className="panel-pad">
      <h3>Stakeholder negotiation</h3>
      <p className="muted small">
        Five AI agents, each with its own priorities, bargain over candidate plans built by the optimizer. They use
        Zeuthen's concession protocol and never accept less than the status quo. The outcome is compared with
        cooperative game-theory solutions.
      </p>
      <div className="agents">
        {meta.stakeholders.map((s) => {
          const u = neg && done ? neg.utilities[s.key] : null;
          return (
            <div key={s.key} className="agent" style={{ borderColor: s.color }} title={s.blurb}>
              <div className="agent-icon">{s.icon}</div>
              <div className="agent-name">{s.name}</div>
              {u !== null ? (
                <div className={`agent-u ${u >= 0 ? "good" : "bad"}`}>{fmtScore(u)}</div>
              ) : (
                <div className="agent-w muted">
                  {Object.entries(s.weights)
                    .filter(([, w]) => w > 0)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 2)
                    .map(([k]) => meta.indicators.find((i) => i.key === k)?.label.split(" ")[0])
                    .join(" · ")}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <label className="field">
        <span>Negotiate over</span>
        <select value={area} onChange={(e) => setArea(e.target.value)}>
          {Object.entries(meta.levels).map(([cd, name]) => (
            <option key={cd} value={`cd:${cd}`}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <button className="primary wide" onClick={start} disabled={busy}>
        {busy ? "Agents are drafting plans…" : "🤝 Start negotiation"}
      </button>

      {neg && (
        <div className="chat" ref={chatRef}>
          {neg.transcript.slice(0, shown).map((m, k) => {
            const a = agents[m.agent];
            return (
              <div key={k} className={`msg ${m.kind} ${a ? "" : "moderator"}`}>
                <span className="msg-icon" style={{ background: a?.color ?? "#555" }}>
                  {a?.icon ?? "⚖️"}
                </span>
                <div className="msg-body">
                  <div className="msg-who">
                    {a?.name ?? "Mediator"} <span className="muted">· round {m.round}</span>
                  </div>
                  {m.text}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {neg && done && agreed && (
        <div className="card mt agreed">
          <div className="eyebrow">
            Agreement after {neg.rounds} rounds {neg.agreed_by_protocol ? "(reached by the agents)" : "(mediated)"}
          </div>
          <div className="agreed-title">{agreed.title}</div>
          <PillarCards ev={neg.plan_evaluations[agreed.id]} />
          <table className="solutions">
            <tbody>
              {Object.entries(SOLUTION_LABEL).map(([k, label]) => {
                const s = neg.solutions[k] as { plan: string } | null;
                const plan = s ? neg.plans.find((p) => p.id === s.plan) : null;
                return (
                  <tr key={k} className={s?.plan === agreed.id ? "match" : ""}>
                    <td>{label}</td>
                    <td>{plan ? plan.title : "no plan everyone gains from"}</td>
                    <td>{s?.plan === agreed.id ? "✓" : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="row gap">
            <button
              className="primary"
              onClick={() => {
                applyChanges(neg.plan_changes[agreed.id], true);
                setPreview(undefined);
                notify("Negotiated plan applied", "good");
              }}
            >
              Apply agreed plan
            </button>
            <button onClick={() => setPreview({ label: agreed.title, changes: neg.plan_changes[agreed.id] })}>Preview</button>
            <button
              onClick={async () => {
                setPoa(await api.priceOfAnarchy(area));
              }}
            >
              Price of anarchy
            </button>
          </div>
          {poa && (
            <div className="poa">
              If each stakeholder controlled its own parcels and acted alone, total welfare would be{" "}
              <b>{poa.welfare_fragmented.toFixed(1)}</b>, against <b>{poa.welfare_cooperative.toFixed(1)}</b> when
              cooperating. <b>Price of anarchy: {poa.price_of_anarchy ? poa.price_of_anarchy.toFixed(2) : "n/a"}</b>.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
