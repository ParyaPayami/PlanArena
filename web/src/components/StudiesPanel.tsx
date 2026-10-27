import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { fmtScore, PILLAR_COLOR } from "../format";
import type { Evaluation, Study } from "../types";

export default function StudiesPanel() {
  const meta = useStore((s) => s.meta)!;
  const applyChanges = useStore((s) => s.applyChanges);
  const notify = useStore((s) => s.notify);
  const [studies, setStudies] = useState<Study[]>([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [compare, setCompare] = useState<string[]>([]);
  const [compared, setCompared] = useState<{ study: Study; ev: Evaluation }[] | null>(null);
  const [history, setHistory] = useState<{ timestamp: string; action: string }[]>([]);

  const refresh = () => api.studies().then(setStudies).catch((e) => notify(String(e), "bad"));
  useEffect(() => {
    refresh();
  }, []);
  useEffect(() => {
    if (open) api.studyHistory(open).then(setHistory);
  }, [open, studies]);

  const save = async () => {
    const changes = useStore.getState().changes();
    if (!Object.keys(changes).length) return notify("Change at least one parcel before saving a study", "bad");
    const s = await api.createStudy({ name: name || `Study ${studies.length + 1}`, description: desc, study_area: "", changes });
    setName("");
    setDesc("");
    await refresh();
    setOpen(s.id);
    notify(`Saved “${s.name}”`, "good");
  };

  const patch = async (s: Study, body: Partial<Study>) => {
    await api.patchStudy(s.id, body);
    refresh();
  };

  const runCompare = async () => {
    const chosen = studies.filter((s) => compare.includes(s.id));
    const evs = await Promise.all(chosen.map((s) => api.evaluate(s.changes, "city")));
    setCompared(chosen.map((study, k) => ({ study, ev: evs[k] })));
  };

  return (
    <div className="panel-pad">
      <h3>Planning studies</h3>
      <p className="muted small">
        Save a plan as a study record with a status workflow, hearing date and checklist, then compare alternatives side
        by side. Every action goes into a tamper-evident audit log.
      </p>
      <div className="card">
        <input className="text" placeholder="Study name (e.g. Canal Street rezoning, alt. A)" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
        <textarea className="text" placeholder="Purpose and description" value={desc} onChange={(e) => setDesc(e.target.value)} rows={2} maxLength={4000} />
        <button className="primary wide" onClick={save}>
          ＋ Save current plan as a study
        </button>
      </div>

      {studies.length > 1 && (
        <div className="row gap">
          <button disabled={compare.length < 2} onClick={runCompare}>
            Compare {compare.length || ""} selected
          </button>
          {compared && <button onClick={() => setCompared(null)}>Close comparison</button>}
        </div>
      )}
      {compared && (
        <div className="card mt compare">
          <div className="eyebrow">Side-by-side (whole-city scores)</div>
          <table>
            <thead>
              <tr>
                <th />
                {compared.map((c) => (
                  <th key={c.study.id}>{c.study.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Parcels changed</td>
                {compared.map((c) => (
                  <td key={c.study.id}>{c.ev.n_changed}</td>
                ))}
              </tr>
              {(["social", "economic", "environmental"] as const).map((p) => (
                <tr key={p}>
                  <td style={{ color: PILLAR_COLOR[p] }}>{p}</td>
                  {compared.map((c) => (
                    <td key={c.study.id}>{fmtScore(c.ev.pillars[p])}</td>
                  ))}
                </tr>
              ))}
              {meta.indicators.map((ind) => (
                <tr key={ind.key}>
                  <td className="muted">{ind.label}</td>
                  {compared.map((c) => {
                    const r = c.ev.indicators.find((x) => x.key === ind.key)!;
                    return (
                      <td key={c.study.id} className={r.score > 0.005 ? "good" : r.score < -0.005 ? "bad" : ""}>
                        {fmtScore(r.score)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="studies">
        {studies.map((s) => (
          <div key={s.id} className={`study ${open === s.id ? "open" : ""}`}>
            <div className="study-head">
              <input
                type="checkbox"
                checked={compare.includes(s.id)}
                onChange={(e) => setCompare((c) => (e.target.checked ? [...c, s.id] : c.filter((x) => x !== s.id)))}
                title="Select for comparison"
              />
              <div className="study-title" onClick={() => setOpen(open === s.id ? null : s.id)}>
                <b>{s.name}</b>
                <div className="muted small">
                  {s.summary?.n_changed ?? Object.keys(s.changes).length} parcels · {s.status} · score{" "}
                  {s.summary ? fmtScore(s.summary.overall) : "–"}
                </div>
              </div>
              <button
                onClick={() => {
                  applyChanges(s.changes, true);
                  notify(`Loaded “${s.name}”`, "good");
                }}
              >
                Load
              </button>
            </div>
            {open === s.id && (
              <div className="study-body">
                {s.description && <p className="small">{s.description}</p>}
                <div className="row gap">
                  <label className="field inline">
                    <span>Status</span>
                    <select value={s.status} onChange={(e) => patch(s, { status: e.target.value })}>
                      {meta.statuses.map((st) => (
                        <option key={st}>{st}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field inline">
                    <span>Hearing</span>
                    <input type="date" value={s.hearing_date ?? ""} onChange={(e) => patch(s, { hearing_date: e.target.value })} />
                  </label>
                </div>
                <div className="eyebrow mt">Checklist</div>
                {s.checklist.map((c, k) => (
                  <label key={k} className="check">
                    <input
                      type="checkbox"
                      checked={c.done}
                      onChange={(e) =>
                        patch(s, { checklist: s.checklist.map((x, j) => (j === k ? { ...x, done: e.target.checked } : x)) })
                      }
                    />
                    {c.label}
                  </label>
                ))}
                <form
                  className="row gap add-item"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const inp = (e.currentTarget.elements.namedItem("item") as HTMLInputElement);
                    const label = inp.value.trim();
                    if (!label) return;
                    await patch(s, { checklist: [...s.checklist, { label, done: false }] });
                    inp.value = "";
                  }}
                >
                  <input name="item" className="text" placeholder="Add a checklist step (e.g. Community board review)" maxLength={200} />
                  <button type="submit">Add</button>
                </form>
                <div className="row gap">
                  <button
                    onClick={async () => {
                      await patch(s, { changes: useStore.getState().changes() });
                      notify("Study updated with the current plan", "good");
                    }}
                  >
                    Update with current plan
                  </button>
                  <button onClick={() => api.openReport(s.changes, s.name, s.description)}>Staff report</button>
                  <button
                    className="danger"
                    onClick={async () => {
                      if (!window.confirm(`Delete “${s.name}”? The audit log keeps a record.`)) return;
                      await api.deleteStudy(s.id);
                      setOpen(null);
                      refresh();
                    }}
                  >
                    Delete
                  </button>
                </div>
                <div className="eyebrow mt">History</div>
                <ul className="history">
                  {history.map((h, k) => (
                    <li key={k}>
                      <span className="muted">{h.timestamp.replace("T", " ").slice(0, 16)}</span> {h.action.replace("scenario_", "")}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        {!studies.length && <div className="muted small mt">No studies saved yet.</div>}
      </div>
    </div>
  );
}
