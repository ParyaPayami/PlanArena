import { useState } from "react";
import { useStore } from "../store";

const KEY = "planarena.firstPlanDone";

function stored(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

/** A guided first task for new users (usability finding F14); ticks itself off and can be dismissed. */
export default function FirstPlan() {
  const [hidden, setHidden] = useState(stored);
  const selected = useStore((s) => s.selected.size);
  const changed = useStore((s) => s.evaluation?.n_changed ?? 0);
  if (hidden) return null;
  const dismiss = () => {
    try {
      window.localStorage.setItem(KEY, "1");
    } catch {
      /* private window: the card just comes back next time */
    }
    setHidden(true);
  };
  const steps = [
    { done: selected > 0 || changed > 0, text: "Select a parcel: click one on the map, or find an address above." },
    { done: changed > 0, text: "Pick a new use from the list below (or press 1–9)." },
    { done: changed > 0, text: "Read the effect on the right: each score is the change in the area around your edit." },
  ];
  const all = steps.every((s) => s.done);
  return (
    <div className="card first-plan">
      <div className="palette-head">
        <div className="eyebrow">{all ? "First plan done" : "Your first plan"}</div>
        <button className="link" onClick={dismiss}>
          {all ? "close" : "skip"}
        </button>
      </div>
      <ol>
        {steps.map((s, k) => (
          <li key={k} className={s.done ? "done" : ""}>
            {s.done ? "✓ " : ""}
            {s.text}
          </li>
        ))}
      </ol>
      {all && <div className="muted small">Next: the Optimize tab suggests a plan; the Vote tab puts plans to a simulated vote.</div>}
    </div>
  );
}
