import { useEffect, useMemo, useRef, useState } from "react";
import CityMap from "../components/CityMap";
import { PillarCards } from "../components/Scoreboard";
import Toast from "../components/Toast";
import { api } from "../api";
import { loadCity, startAutoEvaluate, useStore } from "../store";
import { fmtDelta, fmtScore } from "../format";
import type { Evaluation, Meta, Vote } from "../types";
import type { Changes } from "../api";

const STAR_KEY = "planarena-stars";

function loadStars(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(STAR_KEY) || "{}");
  } catch {
    return {};
  }
}
function saveStars(cd: string, n: number) {
  try {
    const s = loadStars();
    s[cd] = Math.max(s[cd] ?? 0, n);
    localStorage.setItem(STAR_KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable: progress is not kept */
  }
}

interface Mission {
  homes: number;
  ghgPct: number;
}

function missionFor(base: Evaluation): Mission {
  const homes = base.indicators.find((r) => r.key === "homes")!.baseline;
  return { homes: Math.max(50, Math.round((homes * 0.01) / 10) * 10), ghgPct: 2 };
}

function goals(ev: Evaluation | undefined, m: Mission) {
  const get = (k: string) => ev?.indicators.find((r) => r.key === k);
  const homes = get("homes")?.delta ?? 0;
  const park = get("park_access")?.delta ?? 0;
  const ghg = get("ghg")?.pct ?? 0;
  return [
    { label: `Add ${m.homes.toLocaleString()} homes`, done: homes >= m.homes, progress: Math.max(0, Math.min(1, homes / m.homes)), value: `${Math.round(homes).toLocaleString()} / ${m.homes.toLocaleString()}` },
    { label: "Keep park access", done: park >= -1e-6, progress: park >= -1e-6 ? 1 : 0, value: fmtDelta({ key: "park_access", kind: "share", unit: "" }, park) },
    { label: `Emissions under +${m.ghgPct}%`, done: ghg <= m.ghgPct, progress: ghg <= m.ghgPct ? 1 : 0, value: `${ghg >= 0 ? "+" : ""}${ghg.toFixed(1)}%` },
  ];
}

export default function Game() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [level, setLevel] = useState<string | null>(null);
  useEffect(() => {
    api.meta().then(setMeta);
  }, []);
  if (!meta) return <div className="boot"><div className="logo big" /><div className="boot-title">PlanArena</div><div className="boot-sub">Loading city…</div></div>;
  if (!level) return <LevelSelect meta={meta} onPick={setLevel} />;
  return <Level key={level} meta={meta} cd={level} onExit={() => setLevel(null)} onNext={(cd) => setLevel(cd)} />;
}

function LevelSelect({ meta, onPick }: { meta: Meta; onPick: (cd: string) => void }) {
  const stars = loadStars();
  const total = Object.values(stars).reduce((a, b) => a + b, 0);
  return (
    <div className="game-home">
      <div className="game-hero">
        <div className="logo big" />
        <h1>PlanArena</h1>
        <p>Re-plan Manhattan one neighbourhood at a time. Add homes, keep parks close and cut emissions. Then put your plan to the stakeholder council against the AI planner's.</p>
        <div className="star-total">⭐ {total} / {Object.keys(meta.levels).length * 3}</div>
      </div>
      <div className="levels">
        {Object.entries(meta.levels).map(([cd, name], k) => (
          <button key={cd} className="level-card" onClick={() => onPick(cd)}>
            <div className="level-num">{k + 1}</div>
            <div className="level-name">{name}</div>
            <div className="level-stars">{"★".repeat(stars[cd] ?? 0)}{"☆".repeat(3 - (stars[cd] ?? 0))}</div>
          </button>
        ))}
      </div>
      <a className="game-desktop-link" href="/">Open the planner Studio (desktop) →</a>
    </div>
  );
}

function Level({ meta, cd, onExit, onNext }: { meta: Meta; cd: string; onExit: () => void; onNext: (cd: string) => void }) {
  const s = useStore();
  const [loaded, setLoaded] = useState(false);
  const [brush, setBrush] = useState("res");
  const [base, setBase] = useState<Evaluation | null>(null);
  const [rival, setRival] = useState<Evaluation | null>(null);
  const [rivalChanges, setRivalChanges] = useState<Changes | null>(null);
  const [finished, setFinished] = useState(false);
  const [council, setCouncil] = useState<Vote | null>(null);
  const [voting, setVoting] = useState(false);
  const [floats, setFloats] = useState<{ id: number; text: string; good: boolean }[]>([]);
  const prevEv = useRef<Evaluation | undefined>(undefined);

  useEffect(() => {
    let live = true;
    loadCity(`/data/levels/${cd}.geojson`).then(({ meta: m, data }) => {
      if (!live) return;
      useStore.getState().init(m, data);
      useStore.setState({ scope: `cd:${cd}`, selected: new Set(), past: [], future: [], preview: undefined, evaluation: undefined });
      startAutoEvaluate();
      setLoaded(true);
    });
    api.evaluate({}, `cd:${cd}`).then((e) => live && setBase(e));
    api.suggest({ scope: `cd:${cd}`, mode: "balanced", max_change_share: 0.05 }).then((r) => {
      if (!live) return;
      setRival(r.evaluation);
      setRivalChanges(r.changes);
    });
    return () => {
      live = false;
    };
  }, [cd]);

  // Floating "+120 homes" feedback after each evaluation.
  useEffect(() => {
    const ev = s.evaluation;
    if (!ev || !prevEv.current) {
      prevEv.current = ev;
      return;
    }
    const before = Object.fromEntries(prevEv.current.indicators.map((r) => [r.key, r.delta]));
    const items = ev.indicators
      .map((r) => ({ r, d: r.delta - (before[r.key] ?? 0) }))
      .filter(({ r, d }) => Math.abs(d) > (r.kind === "share" ? 0.0005 : r.key === "value" ? 5e5 : 0.5))
      .sort((a, b) => Math.abs(b.r.score) - Math.abs(a.r.score))
      .slice(0, 2)
      .map(({ r, d }) => ({ id: Math.random(), text: `${fmtDelta(r, d)} ${r.label.split(" ")[0].toLowerCase()}`, good: d * r.direction > 0 }));
    if (items.length) {
      setFloats((f) => [...f, ...items]);
      window.setTimeout(() => setFloats((f) => f.filter((x) => !items.includes(x))), 1600);
    }
    prevEv.current = ev;
  }, [s.evaluation]);

  const mission = useMemo(() => (base ? missionFor(base) : null), [base]);
  const g = mission ? goals(s.evaluation, mission) : [];
  const done = g.filter((x) => x.done).length;
  const overall = s.evaluation && s.evaluation.n_changed ? s.evaluation.overall : 0;
  // The council elects a plan by the Schulze rule; identical plans are merged, so resolve aliases.
  const elected = council ? council.decision.plan : null;
  const youId = council ? (council.aliases.you ?? "you") : "you";
  const councilElectsYou = !!council && elected === youId && youId !== "status-quo";
  const stars = g.length ? (g[0].done ? 1 : 0) + (done === 3 ? 1 : 0) + (done === 3 && councilElectsYou ? 1 : 0) : 0;
  const finish = async () => {
    setFinished(true);
    setCouncil(null);
    setVoting(true);
    try {
      const v = await api.vote({
        scope: `cd:${cd}`, residents: false, parcel_ballot: false, samples: 0,
        plans: { ai: { title: "Recommended plan", changes: rivalChanges ?? {} }, you: { title: "Your plan", changes: s.changes() } },
      });
      setCouncil(v);
    } catch (e) {
      s.notify(String(e), "bad");
    } finally {
      setVoting(false);
    }
  };
  useEffect(() => {
    if (council) saveStars(cd, stars);
  }, [council]);
  const levelKeys = Object.keys(meta.levels);
  const nextCd = levelKeys[(levelKeys.indexOf(cd) + 1) % levelKeys.length];

  const view = useMemo(() => {
    if (!s.data) return null;
    let x = 0, y = 0, n = 0;
    for (const f of s.data.features) {
      const i = (f.properties as { i: number }).i;
      if (!Number.isFinite(s.data.lon[i]) || !Number.isFinite(s.data.lat[i])) continue;
      x += s.data.lon[i];
      y += s.data.lat[i];
      n++;
    }
    return { longitude: x / n, latitude: y / n, zoom: 14.2, pitch: 0, bearing: -29 };
  }, [loaded]);

  if (!loaded || !s.data || !view || !s.meta)
    return <div className="boot"><div className="logo big" /><div className="boot-sub">Loading {meta.levels[cd]}…</div></div>;

  return (
    <div className="game">
      <CityMap
        data={s.data}
        landUses={meta.land_uses}
        use={s.use}
        version={s.version}
        selected={s.selected}
        selVersion={s.selVersion}
        view3d={s.view3d}
        mode="paint"
        initialViewState={view}
        onPaint={(i) => s.paint(brush, [i])}
      />
      <div className="hud">
        <div className="hud-top">
          <button className="round" onClick={onExit} aria-label="Back to levels">‹</button>
          <div className="hud-title">
            <div className="eyebrow">Level {levelKeys.indexOf(cd) + 1}</div>
            <div>{meta.levels[cd]}</div>
          </div>
          <div className="hud-score">
            <div className={`big-score ${overall > 0.05 ? "good" : overall < -0.05 ? "bad" : ""}`}>{fmtScore(overall)}</div>
            <div className="eyebrow">AI {rival ? fmtScore(rival.overall) : "…"}</div>
          </div>
        </div>
        <div className="goals">
          {g.map((x) => (
            <div key={x.label} className={`goal ${x.done ? "done" : ""}`}>
              <span className="goal-check">{x.done ? "✓" : "○"}</span>
              <span className="goal-label">{x.label}</span>
              <span className="goal-val">{x.value}</span>
              <div className="goal-bar"><div style={{ width: `${x.progress * 100}%` }} /></div>
            </div>
          ))}
        </div>
      </div>
      <div className="floats">
        {floats.map((f) => (
          <div key={f.id} className={`float ${f.good ? "good" : "bad"}`}>{f.text}</div>
        ))}
      </div>
      <div className="sheet">
        {!s.past.length && <div className="tip">Tap or drag across parcels to paint them with the selected land use</div>}
        <div className="brushes">
          {meta.land_uses.map((u) => (
            <button key={u.key} className={`brush ${brush === u.key ? "on" : ""}`} onClick={() => setBrush(u.key)}>
              <span className="brush-dot" style={{ background: u.color }} />
              <span>{u.label.split(" ")[0].replace(",", "")}</span>
            </button>
          ))}
        </div>
        <div className="sheet-actions">
          <button className="round" onClick={s.undo} disabled={!s.past.length} aria-label="Undo">↶</button>
          <button className="round" onClick={s.toggle3d} aria-label="3D">{s.view3d ? "3D" : "2D"}</button>
          <button className="primary finish" onClick={finish}>
            Finish & vote 🗳
          </button>
        </div>
      </div>
      {finished && s.evaluation && (
        <div className="modal-back">
          <div className="modal">
            <div className="result-stars">{[0, 1, 2].map((k) => <span key={k} className={k < stars ? "on" : ""}>★</span>)}</div>
            <h2>
              {voting ? "The council is voting…" : councilElectsYou && stars === 3 ? "The council elected your plan!"
                : councilElectsYou ? "Elected! Now meet every goal" : stars >= 2 ? "Great plan, but the council chose another"
                : stars === 1 ? "Homes delivered!" : "Keep trying"}
            </h2>
            <div className="vs">
              <div><div className="eyebrow">You</div><div className="big-score">{fmtScore(overall)}</div></div>
              <div className="muted">vs</div>
              <div><div className="eyebrow">AI planner</div><div className="big-score">{rival ? fmtScore(rival.overall) : "…"}</div></div>
            </div>
            {council && (
              <>
                <div className="council-vote">
                  {council.council.voters.map((v) => {
                    const a = meta.stakeholders.find((x) => x.key === v.key);
                    const first = council.council.ballots[v.key][0];
                    const label = council.candidates.find((c) => c.id === first)?.title ?? first;
                    return (
                      <div key={v.key} className="ballot" title={a?.name}>
                        <span className="agent-icon">{a?.icon}</span>
                        <span className={first === youId ? "good" : first === "status-quo" ? "muted" : "bad"}>{label}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="muted small center-row">
                  Elected by the Schulze rule: <b>{council.decision.title}</b>
                  {council.council.condorcet_winner === council.decision.plan ? " (beats each rival head to head)" : ""}
                </div>
              </>
            )}
            <PillarCards ev={s.evaluation} />
            <div className="row gap center-row">
              <button onClick={() => setFinished(false)}>Keep editing</button>
              <button className="primary" onClick={() => onNext(nextCd)}>Next level ›</button>
            </div>
          </div>
        </div>
      )}
      <Toast />
    </div>
  );
}
