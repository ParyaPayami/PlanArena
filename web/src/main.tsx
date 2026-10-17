import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Studio from "./studio/Studio";
import Game from "./game/Game";
import { loadCity, startAutoEvaluate, useStore } from "./store";
import "./styles.css";

const isPlay = window.location.pathname.startsWith("/play");

function Boot() {
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const ready = useStore((s) => !!s.data);
  useEffect(() => {
    if (isPlay) return;
    loadCity("/data/parcels.geojson", setProgress)
      .then(({ meta, data }) => {
        useStore.getState().init(meta, data);
        startAutoEvaluate();
      })
      .catch((e) => setError(String(e)));
  }, []);
  if (isPlay) return <Game />;
  if (error) return <div className="boot">Could not load the city: {error}</div>;
  if (!ready)
    return (
      <div className="boot">
        <div className="logo big" />
        <div className="boot-title">PlanArena</div>
        <div className="boot-sub">Building the digital twin…</div>
        <div className="boot-bar">
          <div style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      </div>
    );
  return <Studio />;
}

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  navigator.serviceWorker.register("/sw.js").catch(() => undefined);
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Boot />
  </StrictMode>,
);
