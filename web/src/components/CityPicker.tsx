import { useEffect, useState } from "react";
import { api, cityHref, type CityEntry } from "../api";
import { useStore } from "../store";

/** The PlanArena cities: each built from the land use its own government publishes for every parcel. */
export default function CityPicker() {
  const meta = useStore((s) => s.meta)!;
  const [open, setOpen] = useState(false);
  const [cities, setCities] = useState<CityEntry[]>([]);

  useEffect(() => {
    if (open) api.cities().then(setCities).catch(() => undefined);
  }, [open]);

  return (
    <>
      <button className="link city-button" onClick={() => setOpen(true)} title="Choose a city">
        {meta.city} ▾
      </button>
      {open && (
        <div className="modal-back" onClick={() => setOpen(false)}>
          <div className="modal methods" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Choose a city">
            <h2>Choose a city</h2>
            <p className="muted small">
              Each city's baseline is the land use its government or regional planning agency publishes for every
              parcel. The adopted plan and zoning are separate layers. Nothing is estimated: a city whose official
              data is still being added is listed but cannot be opened yet.
            </p>
            <div className="city-hits">
              {cities.map((c) => (
                <div key={c.id} className="city-hit">
                  <span>
                    <b>{c.label}</b>{" "}
                    <span className="muted small">
                      {c.built ? `${(c.parcels ?? 0).toLocaleString()} parcels` : c.status}
                    </span>
                  </span>
                  {c.built ? (
                    <a className="button chip" href={cityHref(c.id)}>
                      Open
                    </a>
                  ) : (
                    <span className="muted small">soon</span>
                  )}
                </div>
              ))}
            </div>
            <button onClick={() => setOpen(false)}>Close</button>
          </div>
        </div>
      )}
    </>
  );
}
