"""Tier B adapter: any Florida city or town, from the Florida Department of Revenue parcel maps and tax roll.

Each county's 2026 parcel map (DOR Property Tax Oversight data portal) carries the real-property roll (NAL)
attributes: DOR land-use code, just value, land value, land area, year built, effective floor area of all
improvements (TOT_LVG_AREA), number of buildings and residential units, address and census block group. Multi-part
parcels are joined; condominium units mapped as stacked copies of one footprint are summed to one lot. Owner fields
are never read. There is no zoning in the roll: all uses are allowed and capacity uses the context FAR.

Run:  python -I -m planarena.cities.adapters.florida "Gainesville"
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import time
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from planarena.cities.common import finish_twin, plausible_floor_area, reconcile_lot_area
from planarena.cities.registry import city_dir, register
from planarena.cities.tier_a import _districts, local_crs
from planarena.config import DATA, USE_INDEX as U, USE_KEYS, WEB_CRS
from planarena.national import census, places
from planarena.national.common import download
from planarena.twin.build import FLOOR_HEIGHT_M, _polygonal

RAW = DATA / "raw" / "florida_dor"
SITE = "https://floridarevenue.com"
PAR_DIR = "/property/dataportal/Documents/PTO Data Portal/Map Data/2026F/2026F PAR"
COLS = ["PARCELNO", "DOR_UC", "JV", "LND_VAL", "LND_SQFOOT", "ACT_YR_BLT", "TOT_LVG_AR", "NO_BULDNG", "NO_RES_UNT",
        "PHY_ADDR1", "JV_HIST_CO", "JV_HIST_SI", "ASMNT_YR"]
ALL = (1 << len(USE_KEYS)) - 1

# DOR land-use codes (2026 NAL/SDF/NAP User's Guide, field 8) -> PlanArena use
_U = {}
for c in (1, 2, 3, 4, 5, 6, 7, 8):
    _U[c] = "res"
_U.update({0: "vac", 9: "opn", 10: "vac", 12: "mix", 20: "tra", 28: "prk", 36: "opn", 38: "opn", 40: "vac", 70: "vac",
           76: "pub", 80: "vac", 82: "opn", 90: "com", 91: "tra", 92: "ind", 93: "vac", 94: "tra", 95: "opn", 96: "opn",
           97: "opn", 98: "tra", 99: "vac"})
for c in list(range(11, 40)):
    _U.setdefault(c, "com")
for c in range(41, 50):
    _U.setdefault(c, "ind")
for c in range(50, 70):
    _U.setdefault(c, "opn")  # agricultural
for c in range(71, 90):
    _U.setdefault(c, "pub")
RETAIL = {11, 13, 14, 15, 16, 21, 22, 26, 27, 29, 30, 33}
OFFICE = {17, 18, 19, 23, 24}
STORAGE = {48, 49}


def use_of(code) -> str:
    try:
        return _U.get(int(code), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def _list(folder: str) -> list[str]:
    url = f"{SITE}/property/dataportal/_api/web/GetFolderByServerRelativeUrl('{folder.replace(' ', '%20')}')/Files"
    r = subprocess.run(["curl", "-sf", "-m", "120", "-A", "Mozilla/5.0", "-H", "Accept: application/json;odata=nometadata", url],
                       check=True, capture_output=True, text=True)
    return [f["Name"] for f in json.loads(r.stdout).get("value", [])]


def _norm(name: str) -> str:
    n = name.lower().replace(" county", "").replace("saint ", "st").replace("st. ", "st")
    return re.sub(r"[^a-z]", "", n)


def parcel_file(county_name: str) -> str:
    files = _list(PAR_DIR)
    keys = {_norm(f.split("_")[0]): f for f in files if f.endswith(".zip")}
    k = _norm(county_name)
    hit = keys.get(k) or keys.get(difflib.get_close_matches(k, list(keys), n=1, cutoff=0.75)[0] if difflib.get_close_matches(k, list(keys), n=1, cutoff=0.75) else "")
    if not hit:
        raise SystemExit(f"no DOR parcel map for {county_name}")
    return hit


def load_county(county_name: str) -> gpd.GeoDataFrame:
    f = parcel_file(county_name)
    z = download(f"{SITE}{PAR_DIR.replace(' ', '%20')}/{f}", RAW / f)
    ext = RAW / z.stem
    if not ext.exists():
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if ".." not in n and not n.startswith("/"):
                    zf.extract(n, ext)
    shp = next(ext.rglob("*.shp"))
    head = set(gpd.read_file(shp, rows=1, engine="pyogrio").columns)
    return gpd.read_file(shp, columns=[c for c in COLS if c in head], engine="pyogrio")


def build(target: str) -> dict:
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:6.0f}s] {s}", flush=True)
    hit = [places.place(target)] if target.isdigit() else places.search(target + ", FL", 1)
    if not hit or hit[0]["state"] != "FL":
        raise SystemExit(f"no Florida place matches {target!r}")
    pl = places.place(hit[0]["geoid"])
    geoid = pl["geoid"]
    out = city_dir(geoid)
    out.mkdir(parents=True, exist_ok=True)
    crs = local_crs(pl["lat"], pl["lon"])
    bnd = places.boundary(geoid)
    blocks = census.blocks(geoid, bnd.bounds)
    inside = blocks.representative_point().within(bnd).to_numpy()
    blocks = blocks[(blocks.AREALAND > 0).to_numpy() & inside].reset_index(drop=True)
    cty = places.counties()
    fips = sorted(set(blocks.GEOID.str[:5]))
    parts = []
    for f in fips:
        name = cty[cty.geoid == f].name.iloc[0]
        log(f"downloading the DOR parcel map for {name}")
        g = load_county(name)
        g = g[g.geometry.notna()].to_crs(4326)
        g = g[g.geometry.representative_point().within(bnd).to_numpy()]
        parts.append(g)
    g = pd.concat(parts, ignore_index=True).to_crs(crs)
    g["geometry"] = g.geometry.make_valid()
    g = g.dissolve("PARCELNO", as_index=False, aggfunc="first")  # multi-part parcels
    num = lambda c: pd.to_numeric(g[c], errors="coerce").fillna(0).astype(float) if c in g else pd.Series(0.0, index=g.index)
    for c in ("JV", "LND_VAL", "LND_SQFOOT", "ACT_YR_BLT", "TOT_LVG_AR", "NO_BULDNG", "NO_RES_UNT", "JV_HIST_CO", "JV_HIST_SI"):
        g[c] = num(c)
    g["use"] = g.DOR_UC.map(use_of)
    g["code"] = pd.to_numeric(g.DOR_UC, errors="coerce").fillna(-1).astype(int)
    g["NO_RES_UNT"] = g.NO_RES_UNT.where(g.use.isin(["res", "mix"]), 0.0)
    # condominium units drawn as stacked copies of one footprint -> one lot
    g["gkey"] = shapely.to_wkb(shapely.normalize(g.geometry.values), hex=True)
    agg = g.groupby("gkey").agg(
        geometry=("geometry", "first"), parcel=("PARCELNO", "first"), address=("PHY_ADDR1", "first"),
        use=("use", lambda s: s[s != "unknown"].value_counts().index[0] if (s != "unknown").any() else "unknown"),
        code=("code", lambda s: s.value_counts().index[0]), land_sqft=("LND_SQFOOT", "max"),
        bldg_area=("TOT_LVG_AR", "sum"), units=("NO_RES_UNT", "sum"), year=("ACT_YR_BLT", "max"),
        n_bldgs=("NO_BULDNG", "sum"), land=("LND_VAL", "sum"), tot=("JV", "sum"),
        hist_co=("JV_HIST_CO", "sum"), hist_si=("JV_HIST_SI", "sum"), n_records=("PARCELNO", "size"))
    p = gpd.GeoDataFrame(agg.reset_index(drop=True), geometry="geometry", crs=crs)
    p["geometry"] = p.geometry.map(_polygonal)
    log(f"{len(g):,} parcels -> {len(p):,} lots ({int((p.n_records > 1).sum()):,} with stacked units)")

    blocks = blocks.to_crs(crs)
    rp = p.geometry.representative_point()
    tree = shapely.STRtree(blocks.geometry.values)
    i, k = tree.query(rp.values, predicate="within")
    blk = np.full(len(p), -1)
    blk[i] = k
    miss = blk < 0
    if miss.any():
        blk[miss] = tree.nearest(rp.values[miss])
    jobs_block = census.lodes_jobs("12", "FL").reindex(blocks.GEOID).fillna(0).to_numpy()

    use_a = p.use.map(U).fillna(-1).astype(int).to_numpy()
    lot, n_lot_fixed = reconcile_lot_area(p.land_sqft.to_numpy(), p.geometry.area.to_numpy())
    fa, n_fa_dropped = plausible_floor_area(p.bldg_area.fillna(0).to_numpy().astype(float), lot)
    res_area = np.where(use_a == U["res"], fa, np.where(use_a == U["mix"], 0.7 * fa, 0.0))  # mixed: assumption
    nonres = fa - res_area
    code = p.code.to_numpy()
    com_like = np.isin(use_a, [U["com"], U["mix"]])
    retail = com_like & np.isin(code, list(RETAIL))
    office = com_like & np.isin(code, list(OFFICE))
    ind = use_a == U["ind"]
    storage = ind & np.isin(code, list(STORAGE))
    ll = gpd.GeoSeries(rp, crs=crs).to_crs(WEB_CRS)
    df = pd.DataFrame({
        "bbl": np.arange(len(p), dtype="int64"), "address": p.address.fillna("").astype(str).to_numpy(), "cd": 0,
        "block": blk.astype("int32"), "zone": "NA", "overlay": "", "special": "",
        "bldg_class": p.code.astype(str).str.zfill(3).to_numpy(), "use": use_a.astype("int16"),
        "lot_area": lot, "bldg_area": fa, "res_area": res_area, "com_area": np.where(com_like, nonres, 0.0),
        "office_area": np.where(office, nonres, 0.0), "retail_area": np.where(retail, nonres, 0.0),
        "factory_area": np.where(ind & ~storage, nonres, 0.0), "storage_area": np.where(storage, nonres, 0.0),
        "garage_area": 0.0, "other_area": np.where(com_like & ~retail & ~office, nonres, 0.0),
        "num_bldgs": p.n_bldgs.to_numpy(), "floors": 0.0, "units_res": p.units.to_numpy(), "units_total": p.units.to_numpy(),
        "assess_land": p.land.to_numpy(), "assess_tot": p.tot.to_numpy(), "year_built": p.year.to_numpy(),
        "built_far": np.divide(fa, lot, out=np.zeros(len(p)), where=lot > 0),
        "historic": ((p["hist_co"] + p["hist_si"]) > 0).to_numpy(), "landmark": False,
        "x": rp.x.to_numpy(), "y": rp.y.to_numpy(), "lon": ll.x.to_numpy(), "lat": ll.y.to_numpy(),
        "height_m": 0.0, "census_block": blocks.GEOID.to_numpy()[blk], "parcel_id": p.parcel.astype(str).to_numpy(),
    })
    # The roll has no stories: floors from building area over an assumed 40% footprint coverage, at least one
    built = df.bldg_area > 0
    df.loc[built, "floors"] = np.clip(np.round(df.bldg_area[built] / np.maximum(0.4 * df.lot_area[built], 1)), 1, 80)
    df["height_m"] = df.floors * FLOOR_HEIGHT_M
    bg = df.census_block.str[:12]
    ctx = df[built].groupby(bg[built]).built_far.quantile(0.9)
    df["max_far"] = np.maximum(bg.map(ctx).fillna(df.built_far[built].quantile(0.9)).to_numpy(), df.built_far.to_numpy())
    df["resid_far"] = df["comm_far"] = df["facil_far"] = df["max_far"]
    df["allowed"] = ALL
    df["cd"] = _districts(df, blocks, blk)
    meta = finish_twin(df, p.geometry.values, crs, out, "FL", float(blocks.POP100.sum() / max(blocks.HU100.sum(), 1)),
                       jobs_block, blk, log, {
        "city": pl["label"], "geoid": geoid, "tier": "B",
        "source": "Florida Department of Revenue 2026 parcel map with preliminary real-property roll (NAL) attributes",
        "source_url": "https://floridarevenue.com/property/Pages/DataPortal_RequestAssessmentRollGISData.aspx",
        "data_quality": {"missing_land_use": int((df.use < 0).sum()), "parcels": int(len(g)),
                         "lots_with_stacked_units": int((p.n_records > 1).sum()),
                         "zero_building_area": int((df.bldg_area <= 0).sum()), "lot_area_from_polygon": n_lot_fixed, "floor_area_implausible_dropped": n_fa_dropped,
                         "counties": fips, "jobs_lodes": int(round(jobs_block[np.unique(blk)].sum()))},
        "columns": {"lot boundaries": "observed (DOR parcel map)", "floor area": "observed (TOT_LVG_AREA, effective area)",
                    "land use": "observed (DOR use code)", "homes": "observed (NO_RES_UNTS)",
                    "jobs": "observed by block (LODES), modelled by floor area", "assessed value": "observed (just value)",
                    "zoning": "missing (context FAR, all uses allowed)", "year built": "observed",
                    "floors": "estimated (floor area / 40% lot coverage)",
                    "landmarks and historic districts": "observed where historic property values are recorded"},
        "missing_indicators": [], "zoning_rules": "none (not in the tax roll)",
        "levels": {str(d): f"Area {d}" for d in sorted(df.cd.unique())},
    }, t0=t0)
    register(geoid, pl["label"], "B", meta)
    log(f"done: {len(df):,} lots")
    return meta


if __name__ == "__main__":
    m = build(" ".join(sys.argv[1:]) or "Gainesville")
    print(json.dumps({k: m[k] for k in ("city", "n_parcels", "use_counts", "data_quality", "build_seconds")}, indent=1))
