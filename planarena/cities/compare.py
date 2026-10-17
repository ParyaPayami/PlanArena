"""How good is Tier A? Run the Tier A pipeline inside a Tier B city and score it against the parcel records.

Tier A pseudo-lots from Census blocks and Overture buildings are scored against the city's parcel records (land use,
floor area, homes) and LODES 2023 (jobs), and in Manhattan against LL84 2023 (building emissions), next to the
Tier B result for the same test. Cities: Manhattan (MapPLUTO 25v3.1), Milwaukee (MPROP) and Massachusetts towns (MassGIS L3).
Writes results/validation/tier_a_vs_b_<city>.json.

Run:  python -I -m planarena.cities.compare [manhattan|milwaukee|cambridge|<Tier B GEOID>]
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from planarena.config import DATA, PROCESSED, PROJECTED_CRS, ROOT, USE_KEYS

RAW = DATA / "raw"
MANHATTAN = {"dir": PROCESSED, "state": "NY", "fips": "36", "label": "Manhattan", "emissions": True}


def config(city: str) -> dict:
    """A Tier B city by short name ("manhattan", "milwaukee", "cambridge") or GEOID."""
    if city == "manhattan":
        return MANHATTAN
    from planarena.cities import registry
    from planarena.national import places

    reg = {k: v for k, v in registry.cities().items() if v["tier"] == "B" and k != registry.DEFAULT}
    gid = city if city in reg else next((k for k, v in reg.items() if v["label"].lower().startswith(city.lower())), None)
    if gid is None:
        raise SystemExit(f"no Tier B city {city!r} is built")
    pl = places.place(gid)
    return {"dir": registry.city_dir(gid), "state": pl["state"], "fips": gid[:2], "label": pl["label"].split(",")[0],
            "emissions": False}


def _r(x, d=3):
    return None if x is None or not np.isfinite(x) else round(float(x), d)


def _agree(pred: np.ndarray, obs: np.ndarray) -> dict:
    ok = np.isfinite(pred) & np.isfinite(obs)
    p, o = pred[ok], obs[ok]
    lp, lo = np.log1p(np.clip(p, 0, None)), np.log1p(np.clip(o, 0, None))
    rel = np.abs(p - o) / np.where(o > 0, o, np.nan)
    return {"n": int(ok.sum()), "total_ratio": _r(p.sum() / o.sum()), "pearson_r": _r(np.corrcoef(p, o)[0, 1]),
            "log_r": _r(np.corrcoef(lp, lo)[0, 1]), "median_abs_pct_error": _r(np.nanmedian(rel))}


def _classes(y: np.ndarray, p: np.ndarray) -> dict:
    labels = sorted(set(y) | set(p))
    f1 = []
    for c in labels:
        tp = np.sum((p == c) & (y == c))
        prec = tp / max(np.sum(p == c), 1)
        rec = tp / max(np.sum(y == c), 1)
        f1.append(0 if prec + rec == 0 else 2 * prec * rec / (prec + rec))
    conf = pd.crosstab(pd.Series([USE_KEYS[i] for i in y], name="mappluto"),
                       pd.Series([USE_KEYS[i] for i in p], name="tier_a"))
    return {"n": int(len(y)), "accuracy": _r(np.mean(y == p)), "macro_f1": _r(np.mean(f1)),
            "majority_class_accuracy": _r(np.bincount(y).max() / len(y)),
            "confusion": {r: {c: int(v) for c, v in row.items()} for r, row in conf.iterrows()}}


def build_tier_a(city: str) -> Path:
    from planarena.cities.tier_a import build_city

    c = config(city)
    work = DATA / "cities" / f"tierA_{city}"
    if not (work / "parcels.parquet").exists():
        g = gpd.read_parquet(c["dir"] / "parcels.geoparquet")
        outline = shapely.union_all(g.geometry.buffer(80).values).buffer(-80)  # close the streets between lots
        bnd = gpd.GeoSeries([outline], crs=g.crs).to_crs(4326).iloc[0]
        build_city("", out_dir=work, area={"id": f"tierA_{city}", "label": f"{c['label']} (Tier A test)",
                                          "state": c["state"], "boundary": bnd}, use_model=False, correct_floor_area=False)
    return work


def compare(city: str = "manhattan") -> dict:
    from planarena.calibrate import LL97
    from planarena.indicators.engine import load_engine
    from planarena.national.census import lodes_jobs

    c = config(city)
    WORK = build_tier_a(city)
    pb = pd.read_parquet(c["dir"] / "parcels.parquet")
    gb = gpd.read_parquet(c["dir"] / "parcels.geoparquet")
    pa = pd.read_parquet(WORK / "parcels.parquet")
    ga = gpd.read_parquet(WORK / "parcels.geoparquet").to_crs(gb.crs)
    meta_a = json.loads((WORK / "twin_meta.json").read_text())

    # MapPLUTO lot under each pseudo-lot (representative point), and census block of each MapPLUTO lot
    a, k = shapely.STRtree(gb.geometry.values).query(ga.geometry.representative_point().values, predicate="within")
    lot = np.full(len(pa), -1)
    lot[a] = k
    # census block of each parcel: the block of the pseudo-lot under its representative point (nearest if none)
    tree = shapely.STRtree(shapely.make_valid(ga.geometry.values))
    rp_b = gb.geometry.representative_point().values
    a2, k2 = tree.query(rp_b, predicate="within")
    under = np.full(len(pb), -1)
    under[a2] = k2
    miss = under < 0
    under[miss] = tree.nearest(rp_b[miss])
    blk_b = pd.Series(pa.census_block.to_numpy()[under], index=pb.index)

    out = {"test": __doc__.strip().split("\n\n")[1], "city": c["label"],
           "tier_a": {k: meta_a[k] for k in ("n_parcels", "data_quality", "source")}, "tier_b_parcels": int(len(pb))}

    # 1. land use of built pseudo-lots
    m = (lot >= 0) & (pa.bldg_area.to_numpy() > 0)
    y = pb.use.to_numpy()[lot[m]]
    keep = y >= 0
    pred = pa.use.to_numpy()[m][keep]
    out["land_use"] = _classes(y[keep], pred)
    conf = pa.use_confidence.to_numpy()[m][keep]
    out["land_use"]["accuracy_by_confidence"] = {str(c): {"n": int((conf == c).sum()), "accuracy": _r(np.mean(y[keep][conf == c] == pred[conf == c]))}
                                                 for c in (0, 1, 2) if (conf == c).any()}

    # 2. floor area and 3. homes, by census block
    fa_b = pb.bldg_area.groupby(blk_b).sum()
    fa_a = pa.bldg_area.groupby(pa.census_block).sum()
    j = fa_b.index.intersection(fa_a.index)
    out["floor_area_by_block"] = _agree(fa_a[j].to_numpy(), fa_b[j].to_numpy())
    u_b = pb.units_res.groupby(blk_b).sum()
    u_a = pa.units_res.groupby(pa.census_block).sum()
    j = u_b.index.intersection(u_a.index)
    out["homes_by_block"] = _agree(u_a[j].to_numpy(), u_b[j].to_numpy()) | {
        "note": "Tier A homes are Census 2020 housing units; Tier B homes are the city's parcel records."}
    out["height_observed_share"] = meta_a["data_quality"]["height_observed_share"]

    ea, eb = load_engine(WORK), load_engine(c["dir"])
    bbl_of = pb.bbl.to_numpy()
    # 4. building emissions vs LL84 2023 (LL97 factors), per MapPLUTO lot with an LL84 record
    if c["emissions"]:
        d = pd.DataFrame(json.loads((RAW / "ll84_2023" / "ll84_manhattan_2023_bbl.json").read_text()))
        for col in LL97:
            d[col] = pd.to_numeric(d.get(col), errors="coerce")
        d["bbl"] = pd.to_numeric(d.nyc_borough_block_and_lot.astype(str).str.split(";").str[0].str.strip(), errors="coerce")
        d["t"] = sum(d[col].clip(lower=0).fillna(0) * v for col, v in LL97.items())
        obs = d[d.t > 0].groupby("bbl").t.sum()
        ghg_a = pd.Series(ea.baseline_state["ghg"]).groupby(lot).sum()
        ghg_a = ghg_a[ghg_a.index >= 0]
        s_a = pd.Series(ghg_a.to_numpy(), index=bbl_of[ghg_a.index.to_numpy()])
        j = obs.index.intersection(s_a.index)
        out["emissions_ll84_2023"] = {"tier_a": _agree(s_a[j].to_numpy(), obs[j].to_numpy())}
        s_b = pd.Series(eb.baseline_state["ghg"], index=bbl_of)
        out["emissions_ll84_2023"]["tier_b"] = _agree(s_b[j].to_numpy(), obs[j].to_numpy())
        out["emissions_ll84_2023"]["note"] = ("Same LL84 buildings for both tiers. Tier A uses national RECS/CBECS energy "
                                              "intensities and the eGRID New York State electricity factor; the observed values use "
                                              "the LL97 factors, so part of the Tier A gap is the grid factor.")

    # 5. jobs by census block vs LODES 2023 (Tier A is fitted to these blocks, Tier B is fitted city-wide)
    w = lodes_jobs(c["fips"], c["state"])
    ja = pd.Series(ea.baseline_state["jobs"]).groupby(pa.census_block.to_numpy()).sum()
    jb = pd.Series(eb.baseline_state["jobs"]).groupby(blk_b.to_numpy()).sum()
    j = ja.index.intersection(jb.index)
    out["jobs_by_block"] = {"tier_a": _agree(ja[j].to_numpy(), w.reindex(j).fillna(0).to_numpy()),
                            "tier_b": _agree(jb[j].to_numpy(), w.reindex(j).fillna(0).to_numpy()),
                            "note": "In-sample for both tiers: each fits its rates to these LODES blocks."}
    (ROOT / "results" / "validation" / f"tier_a_vs_b_{city}.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    import sys

    r = compare(sys.argv[1] if len(sys.argv) > 1 else "manhattan")
    print(json.dumps({k: v for k, v in r.items() if k not in ("land_use",)} | {"land_use": {k: v for k, v in r["land_use"].items() if k != "confusion"}}, indent=1, default=str)[:4000])
