"""Build any US place with the best data available for it.

Tier B where an adapter covers the place (New York City: MapPLUTO; Milwaukee: MPROP; every Massachusetts city and town: MassGIS L3; every
Florida place: DOR parcel maps and tax roll), Tier A (national open data) everywhere else.

Run:  python -I -m planarena.cities.build <GEOID or "City, ST">
"""
from __future__ import annotations

import json
import sys

from planarena.national import places

MILWAUKEE = "5553000"
NEW_YORK = "3651000"


def tier_for(geoid: str) -> str:
    pl = places.place(geoid)
    return "B" if geoid in (MILWAUKEE, NEW_YORK) or pl["state"] in ("MA", "FL") else "A"


def build(target: str) -> dict:
    hit = [places.place(target)] if target.isdigit() else places.search(target, 1)
    if not hit:
        raise SystemExit(f"no US place matches {target!r}")
    geoid = hit[0]["geoid"]
    if geoid == NEW_YORK:
        from planarena.cities.adapters import nyc

        return nyc.build()
    if geoid == MILWAUKEE:
        from planarena.cities.adapters import milwaukee

        return milwaukee.build()
    if hit[0]["state"] == "MA":
        from planarena.cities.adapters import massgis

        try:
            return massgis.build(geoid)
        except SystemExit as e:  # no L3 file for this place (e.g. a CDP inside a town): fall back to Tier A
            print(f"MassGIS: {e}; building Tier A instead", flush=True)
    if hit[0]["state"] == "FL":
        from planarena.cities.adapters import florida

        return florida.build(geoid)
    from planarena.cities.tier_a import build_city

    return build_city(geoid)


if __name__ == "__main__":
    m = build(" ".join(sys.argv[1:]))
    print(json.dumps({k: m.get(k) for k in ("city", "tier", "n_parcels", "use_counts", "build_seconds")}, indent=1))
