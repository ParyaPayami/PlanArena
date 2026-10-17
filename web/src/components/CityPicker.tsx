import { useEffect, useRef, useState } from "react";
import { api, cityHref, type BuildJob, type CityEntry, type PlaceHit } from "../api";
import { useStore } from "../store";

/** Switch to any built city, or build a Tier A twin of any US place from national open data. */
export default function CityPicker() {
  const meta = useStore((s) => s.meta)!;
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PlaceHit[]>([]);
  const [built, setBuilt] = useState<CityEntry[]>([]);
  const [job, setJob] = useState<BuildJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number>();

  useEffect(() => {
    if (open) api.cities().then(setBuilt).catch(() => undefined);
  }, [open]);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    timer.current = window.setTimeout(() => api.places(q).then(setHits).catch((e) => setError(String(e))), 250);
  }, [q]);

  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = window.setInterval(() => {
      api.buildStatus(job.geoid).then((j) => {
        setJob(j);
        if (j.status === "done") window.location.href = cityHref(j.geoid);
      });
    }, 2000);
    return () => window.clearInterval(t);
  }, [job]);

  const build = (h: PlaceHit) => {
    setError(null);
    api.buildCity(h.geoid).then(setJob).catch((e) => setError(String(e)));
  };

  return (
    <>
      <button className="link city-button" onClick={() => setOpen(true)} title="Choose or build a city">
        {meta.city} <span className={`badge ${meta.tier === "A" ? "bad" : ""}`}>Tier {meta.tier}</span> ▾
      </button>
      {open && (
        <div className="modal-back" onClick={() => setOpen(false)}>
          <div className="modal methods" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Choose a city">
            <h2>Choose a city</h2>
            <p className="muted small">
              <b>Tier B</b> cities use official parcel records (Manhattan, Milwaukee and every Massachusetts city and
              town). <b>Tier A</b> works for any US city or town: lots are
              estimated from Overture buildings within 2020 census blocks; homes come from the Census and jobs from
              LEHD LODES by block; land use and floor area are estimated; there is no zoning or assessed value.
            </p>
            {built.length > 0 && (
              <>
                <h4>Built</h4>
                <div className="badges">
                  {built.map((c) => (
                    <a key={c.id} className="button chip" href={cityHref(c.id)}>
                      {c.label} · Tier {c.tier}
                    </a>
                  ))}
                </div>
              </>
            )}
            <h4>Any US place</h4>
            <div className="search" style={{ width: "100%" }}>
              <span className="muted">⌕</span>
              <input autoFocus value={q} placeholder="City or town, e.g. Milwaukee or Austin, TX" onChange={(e) => setQ(e.target.value)} />
            </div>
            {job && (
              <p className={job.status === "failed" ? "bad" : "muted"}>
                {job.status === "running" && <>Building {job.label}… {job.step} ({job.elapsed ?? 0} s)</>}
                {job.status === "failed" && <>Build failed. {job.log?.split("\n").slice(-3).join(" ")}</>}
                {job.status === "done" && <>Built. Opening…</>}
              </p>
            )}
            {error && <p className="bad small">{error}</p>}
            <div className="city-hits">
              {hits.map((h) => (
                <div key={h.geoid} className="city-hit">
                  <span>
                    <b>{h.label}</b> <span className="muted small">{h.land_km2.toLocaleString()} km² · {h.kind === "cousub" ? "town" : "place"} · Tier {h.tier}</span>
                  </span>
                  {h.built ? (
                    <a className="button chip" href={cityHref(h.geoid)}>Open</a>
                  ) : (
                    <button className="chip" disabled={job?.status === "running"} onClick={() => build(h)}>
                      Build twin
                    </button>
                  )}
                </div>
              ))}
            </div>
            <p className="muted small">
              Building downloads only this place's data (Census, LODES, Overture) and takes about one to ten minutes,
              depending on its size.
            </p>
            <button onClick={() => setOpen(false)}>Close</button>
          </div>
        </div>
      )}
    </>
  );
}
