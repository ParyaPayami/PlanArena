import { useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { PillarCards } from "./Scoreboard";
import type { Vote } from "../types";

const RULE_ORDER = ["schulze", "kemeny", "copeland", "borda", "irv", "plurality", "approval", "score", "majority_judgment"];
const BARGAIN_LABEL: Record<string, string> = {
  nash_bargaining: "Nash bargaining",
  kalai_smorodinsky: "Kalai–Smorodinsky",
  utilitarian: "Utilitarian (max total)",
  egalitarian: "Egalitarian (max worst-off)",
};

export default function VotePanel() {
  const meta = useStore((s) => s.meta)!;
  const vote = useStore((s) => s.vote);
  const setVote = useStore((s) => s.setVote);
  const overlay = useStore((s) => s.overlay);
  const setOverlay = useStore((s) => s.setOverlay);
  const setPreview = useStore((s) => s.setPreview);
  const applyChanges = useStore((s) => s.applyChanges);
  const notify = useStore((s) => s.notify);
  const [area, setArea] = useState("cd:103");
  const [budget, setBudget] = useState(5);
  const [seats, setSeats] = useState<Record<string, number>>(Object.fromEntries(meta.stakeholders.map((s) => [s.key, 1])));
  const [residents, setResidents] = useState(true);
  const [ballot, setBallot] = useState(true);
  const [busy, setBusy] = useState(false);
  const [poa, setPoa] = useState<null | { price_of_anarchy: number | null; welfare_fragmented: number; welfare_cooperative: number }>(null);
  const agents = Object.fromEntries(meta.stakeholders.map((s) => [s.key, s]));
  const nSeats = Object.values(seats).reduce((a, b) => a + b, 0);

  const short = (v: Vote, id: string) => {
    if (id === "status-quo") return "No change";
    if (id === "parcel-ballot") return "Parcel ballot";
    if (id === "user") return "Your plan";
    if (id === "balanced") return "Balanced";
    if (id === "consensus") return "Consensus";
    if (id.startsWith("ideal-")) return `${agents[id.slice(6)]?.icon ?? ""} ideal`;
    if (id.startsWith("blend-")) return id.slice(6).split("-").map((k) => agents[k]?.icon ?? k).join(" + ");
    return v.candidates.find((c) => c.id === id)?.title ?? id;
  };
  const title = (v: Vote, id: string) => v.candidates.find((c) => c.id === id)?.title ?? id;

  const run = async () => {
    setBusy(true);
    setVote(undefined);
    setOverlay(null);
    setPoa(null);
    try {
      const r = await api.vote({
        scope: area, changes: useStore.getState().changes(), max_change_share: budget / 100, seats,
        residents, parcel_ballot: ballot, samples: 200,
      });
      setVote(r);
      notify(`Vote held over ${r.candidates.length} plans in ${(r.ms / 1000).toFixed(1)} s`, "good");
    } catch (e) {
      notify(String(e), "bad");
    } finally {
      setBusy(false);
    }
  };

  const showBallotOnMap = (v: Vote) => {
    const pb = v.parcel_ballot;
    if (!pb) return;
    if (overlay) return setOverlay(null);
    const data = useStore.getState().data!;
    const keys = meta.land_uses.map((u) => u.key);
    const top = Array.from(data.baseUse, (u) => Math.max(u, 0));
    const p = new Array(data.n).fill(0);
    pb.parcels.forEach((i, k) => {
      top[i] = keys.indexOf(pb.winner[k]);
      p[i] = pb.support[k];
    });
    setOverlay({ top, p, label: "Parcel-by-parcel ballot: colour = winning use, brightness = share of seats in favour" });
    const n = pb.parcels.length;
    if (n) {
      const lon = pb.parcels.reduce((a, i) => a + data.lon[i], 0) / n;
      const lat = pb.parcels.reduce((a, i) => a + data.lat[i], 0) / n;
      useStore.getState().flyTo(lon, lat, 14.3);
    }
  };

  return (
    <div className="panel-pad">
      <h3>Simulated stakeholder scenario</h3>
      <p className="muted small">
        Five simulated stakeholders hold seats on a council. Each ranks every candidate plan from assumed priorities,
        and nine voting rules decide; simulated residents vote block by block. These are not real preferences: use the
        result to explore trade-offs, not as evidence of public support. Not represented: renters as a group,
        commuters, future residents, small landlords, people with disabilities.
      </p>
      <div className="agents">
        {meta.stakeholders.map((s) => {
          const first = vote?.council.ballots[s.key]?.[0];
          const gains = vote?.council.gains[s.key];
          return (
            <div key={s.key} className="agent" style={{ borderColor: s.color }} title={s.blurb}>
              <div className="agent-icon">{s.icon}</div>
              <div className="agent-name">{s.name}</div>
              <div className="seats" role="group" aria-label={`${s.name} seats`}>
                <button onClick={() => setSeats({ ...seats, [s.key]: Math.max(0, seats[s.key] - 1) })} disabled={seats[s.key] <= 0 || nSeats <= 1} aria-label="Remove a seat">
                  −
                </button>
                <b>{seats[s.key]}</b>
                <button onClick={() => setSeats({ ...seats, [s.key]: Math.min(9, seats[s.key] + 1) })} aria-label="Add a seat">
                  +
                </button>
              </div>
              {vote && first && (
                <div className="agent-w" title={`First choice: ${title(vote, first)}`}>
                  1st: {short(vote, first)}
                  <div className={gains ? "good" : "bad"}>{gains ? "gains" : "loses"}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <label className="field">
        <span>Study area</span>
        <select value={area} onChange={(e) => setArea(e.target.value)}>
          {Object.entries(meta.levels).map(([cd, name]) => (
            <option key={cd} value={`cd:${cd}`}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Plans may change up to {budget}% of parcels</span>
        <input type="range" min={1} max={15} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
      </label>
      <label className="check">
        <input type="checkbox" checked={residents} onChange={(e) => setResidents(e.target.checked)} /> Residents' referendum (by tax block)
      </label>
      <label className="check">
        <input type="checkbox" checked={ballot} onChange={(e) => setBallot(e.target.checked)} /> Parcel-by-parcel ballot
      </label>
      <button className="primary wide" onClick={run} disabled={busy}>
        {busy ? "Counting the votes…" : "🗳 Hold the vote"}
      </button>
      {Object.keys(useStore.getState().changes()).length > 0 && (
        <div className="muted small mt">Your current plan is on the ballot as “Your plan”.</div>
      )}

      {vote && <Results vote={vote} short={short} title={title} />}

      {vote && (
        <>
          <div className="row gap mt">
            <button
              className="primary"
              onClick={() => {
                applyChanges(vote.plan_changes[vote.decision.plan] ?? {}, true);
                setPreview(undefined);
                notify("Winning plan applied", "good");
              }}
            >
              Apply winning plan
            </button>
            <button onClick={() => setPreview({ label: vote.decision.title, changes: vote.plan_changes[vote.decision.plan] ?? {} })}>
              Preview
            </button>
            {vote.parcel_ballot && (
              <button className={overlay ? "on" : ""} onClick={() => showBallotOnMap(vote)}>
                {overlay ? "Hide parcel ballot" : "Parcel ballot on map"}
              </button>
            )}
          </div>

          <div className="card mt">
            <div className="eyebrow">Compared with bargaining solutions (game theory)</div>
            <table className="solutions">
              <tbody>
                {Object.entries(BARGAIN_LABEL).map(([k, label]) => {
                  const s = vote.bargaining[k] as { plan: string } | null;
                  return (
                    <tr key={k} className={s?.plan === vote.decision.plan ? "match" : ""}>
                      <td>{label}</td>
                      <td>{s ? title(vote, s.plan) : "no plan every agent gains from"}</td>
                      <td>{s?.plan === vote.decision.plan ? "✓" : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <button className="mt" onClick={async () => setPoa(await api.priceOfAnarchy(area))}>
              Cost of fragmented control
            </button>
            {poa && (
              <div className="poa">
                If each stakeholder controlled its own parcels and acted alone, total welfare would be{" "}
                <b>{poa.welfare_fragmented.toFixed(1)}</b>, against <b>{poa.welfare_cooperative.toFixed(1)}</b> when planned
                together. <b>Cost of fragmented control (heuristic): {poa.price_of_anarchy ? poa.price_of_anarchy.toFixed(2) : "n/a"}</b>. Both
                plans come from the same heuristic search; this is not a formal price of anarchy (see Methods).
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Results({ vote, short, title }: { vote: Vote; short: (v: Vote, id: string) => string; title: (v: Vote, id: string) => string }) {
  const meta = useStore((s) => s.meta)!;
  const agents = Object.fromEntries(meta.stakeholders.map((s) => [s.key, s]));
  const c = vote.council;
  const win = vote.decision.plan;
  const ids = vote.candidates.map((x) => x.id);
  const rank = c.rules.schulze.ranking ?? ids;
  const top = rank.slice(0, 6);
  const rob = c.robustness;
  const robTop = rob ? Object.entries(rob.both).sort((a, b) => b[1] - a[1]).filter(([, p]) => p > 0).slice(0, 4) : [];
  const ev = vote.plan_evaluations[win];
  const badges = [
    c.condorcet_winner === win && "Condorcet winner",
    vote.decision.double_majority === true && "Double majority",
    vote.decision.double_majority === false && "Contested",
    `${c.consensus.rules_won[win]}/${c.consensus.n_rules} rules`,
  ].filter(Boolean) as string[];

  return (
    <>
      <div className="card mt agreed">
        <div className="eyebrow">Simulated council decision · Schulze rule</div>
        <div className="agreed-title">{vote.decision.title}</div>
        <div className="badges">
          {badges.map((b) => (
            <span key={b} className={`badge ${b === "Contested" ? "bad" : ""}`}>
              {b}
            </span>
          ))}
        </div>
        {ev && <PillarCards ev={ev} />}
        <ul className="small explain">
          {vote.decision.explanation.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </div>

      <details className="card mt glossary">
        <summary>How to read this</summary>
        <ul className="small">
          <li><b>Ballot</b>: each stakeholder ranks every plan from its own priorities. Nobody types or talks; the ranking follows from the impacts.</li>
          <li><b>Head to head</b>: plan A beats plan B if more seats rank A above B.</li>
          <li><b>Condorcet winner</b>: a plan that beats every other plan head to head. It does not always exist; when preferences go in a circle, there is a <b>cycle</b>.</li>
          <li><b>Smith set</b>: the smallest group of plans that each beat every plan outside the group.</li>
          <li><b>Schulze</b> (the deciding rule): picks the Condorcet winner when there is one, otherwise the plan with the strongest chain of head-to-head wins. Near-identical plans cannot split its vote.</li>
          <li><b>Other rules</b> are shown for comparison: plurality (most first choices), Borda (points by rank), instant runoff, Copeland (count of head-to-head wins), Kemeny–Young (the ranking that agrees with the most pairwise preferences), approval (plans better than no change), score (0–10) and majority judgment (median grade).</li>
          <li><b>Double majority</b>: both council seats and affected residents prefer the plan to no change.</li>
          <li><b>Robustness</b>: how often the winner still wins when coefficients and seat weights are varied.</li>
        </ul>
      </details>

      <div className="card mt">
        <div className="eyebrow">Ballots (top three of {ids.length} plans)</div>
        <table className="ballots">
          <thead>
            <tr>
              <th>Voter</th>
              <th>Seats</th>
              <th>1st</th>
              <th>2nd</th>
              <th>3rd</th>
            </tr>
          </thead>
          <tbody>
            {c.voters.map((v) => (
              <tr key={v.key} className={v.seats ? "" : "muted"}>
                <td title={agents[v.key]?.name}>
                  {agents[v.key]?.icon} {agents[v.key]?.name.split(" ")[0]}
                </td>
                <td>{v.seats}</td>
                {c.ballots[v.key].slice(0, 3).map((id) => (
                  <td key={id} className={id === win ? "good" : ""} title={title(vote, id)}>
                    {short(vote, id)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card mt">
        <div className="eyebrow">Winner under each rule</div>
        <table className="rules">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Council</th>
              {vote.residents && <th>Residents</th>}
            </tr>
          </thead>
          <tbody>
            {RULE_ORDER.filter((r) => c.rules[r]).map((r) => (
              <tr key={r}>
                <td>{c.rules[r].label}</td>
                <td className={c.rules[r].winner === win ? "good" : ""} title={title(vote, c.rules[r].winner)}>
                  {short(vote, c.rules[r].winner)}
                </td>
                {vote.residents && (
                  <td className={vote.residents.rules[r]?.winner === win ? "good" : ""} title={vote.residents.rules[r] ? title(vote, vote.residents.rules[r].winner) : ""}>
                    {vote.residents.rules[r] ? short(vote, vote.residents.rules[r].winner) : "–"}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="muted small">
          {c.condorcet_winner ? `Condorcet winner: ${title(vote, c.condorcet_winner)}.` : "No Condorcet winner: the majority preferences form a cycle."}{" "}
          Smith set: {c.smith_set.length} plan{c.smith_set.length > 1 ? "s" : ""}.
        </div>
      </div>

      <div className="card mt">
        <div className="eyebrow">Head to head (seats preferring row over column)</div>
        <div className="h2h-wrap">
          <table className="h2h">
            <thead>
              <tr>
                <th />
                {top.map((id) => (
                  <th key={id} title={title(vote, id)}>
                    {short(vote, id)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {top.map((a) => (
                <tr key={a}>
                  <th title={title(vote, a)}>{short(vote, a)}</th>
                  {top.map((b) => {
                    if (a === b) return <td key={b} className="self">–</td>;
                    const ia = ids.indexOf(a), ib = ids.indexOf(b);
                    const f = c.pairwise[ia][ib], g = c.pairwise[ib][ia];
                    return (
                      <td key={b} className={f > g ? "win" : f < g ? "lose" : ""}>
                        {+f.toFixed(1)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {rob && (
        <div className="card mt">
          <div className="eyebrow">Robustness ({rob.samples} simulated votes, coefficients and seats varied)</div>
          {robTop.map(([id, p]) => (
            <div key={id} className="robust-row" title={title(vote, id)}>
              <span className={id === win ? "good" : ""}>{short(vote, id)}</span>
              <div className="bar">
                <div style={{ width: `${p * 100}%` }} className={id === win ? "on" : ""} />
              </div>
              <b>{Math.round(p * 100)}%</b>
            </div>
          ))}
          <div className="muted small">
            The winner wins {Math.round(rob.coefficients[win] * 100)}% of votes with coefficients varied only, and{" "}
            {Math.round(rob.seats[win] * 100)}% with seat weights varied only.
          </div>
        </div>
      )}

      {vote.residents && (
        <div className="card mt">
          <div className="eyebrow">Residents' referendum</div>
          <div className="small">
            {vote.residents.precincts} tax blocks · {Math.round(vote.residents.residents).toLocaleString()} residents ·{" "}
            {vote.residents.affected_precincts} blocks see a local change
          </div>
          {(() => {
            const r = vote.residents.council_winner_vs_status_quo;
            const voting = r.for + r.against;
            const pct = voting > 0 ? Math.round((100 * r.for) / voting) : 0;
            return (
              <div className="yesno mt">
                <div className="yes" style={{ width: `${pct}%` }}>
                  {pct}% yes
                </div>
                <div className="no" style={{ width: `${100 - pct}%` }}>
                  {100 - pct}% no
                </div>
              </div>
            );
          })()}
          <div className="muted small">
            Council's plan against no change, among residents with a preference. The residents' own winner:{" "}
            <b>{title(vote, vote.residents.winner)}</b>
            {vote.residents.agrees_with_council ? " (the same plan)." : "."}
          </div>
        </div>
      )}

      {vote.parcel_ballot && (
        <div className="card mt">
          <div className="eyebrow">Parcel-by-parcel ballot</div>
          <div className="small">
            On {vote.parcel_ballot.eligible.toLocaleString()} eligible parcels the council ranked the allowed uses.{" "}
            {vote.parcel_ballot.passed.toLocaleString()} changes won an absolute majority of seats; the strongest{" "}
            {vote.parcel_ballot.changed} (the change budget) form the “Parcel ballot” plan.
          </div>
        </div>
      )}

      <div className="muted small mt">
        {c.manipulation.length
          ? `Strategic-voting check: ${c.manipulation.length} rule/voter cases where one insincere ballot changes a result (${[...new Set(c.manipulation.map((m) => m.rule))].join(", ")}). Agent ballots are sincere by construction.`
          : "Strategic-voting check: no single voter can change any result by misreporting."}{" "}
        Counted in {(vote.ms / 1000).toFixed(1)} s.
      </div>
    </>
  );
}
