import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";

export default function SearchBox() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ i: number; bbl: number; address: string; lon: number; lat: number }[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number>();
  const select = useStore((s) => s.select);
  const flyTo = useStore((s) => s.flyTo);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    timer.current = window.setTimeout(() => api.search(q).then((h) => { setHits(h); setOpen(true); }), 200);
  }, [q]);

  const go = (h: (typeof hits)[number]) => {
    select(h.i, false);
    flyTo(h.lon, h.lat, 17.2);
    setOpen(false);
    setQ(h.address || String(h.bbl));
  };

  return (
    <div className="search" onBlur={() => setTimeout(() => setOpen(false), 150)}>
      <span className="muted">⌕</span>
      <input
        value={q}
        placeholder="Find an address or BBL…"
        aria-label="Find an address or parcel ID"
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => hits.length && setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && hits[0]) go(hits[0]);
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && hits.length > 0 && (
        <div className="search-results" role="listbox">
          {hits.map((h) => (
            <button key={h.i} role="option" onMouseDown={() => go(h)}>
              <b>{h.address || "No address"}</b> <span className="muted">BBL {h.bbl}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
