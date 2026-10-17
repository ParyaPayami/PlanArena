"""Tier B adapter: any Massachusetts city or town, from the MassGIS Level 3 standardized assessors' parcels.

Each of the 351 towns publishes tax-parcel polygons and an assessing table (MassGIS, L3 standard): use code, floor
area, residential area, units, year built, stories, zoning code, assessed value and lot size. Condominium records are
summed to their parcel (LOC_ID). Owner fields are never read.

Land use: the Massachusetts DOR property-type classification (first three characters of USE_CODE), with overrides
from the town's own code descriptions (vacant, parking, housing authority, conservation, utilities). Zoning codes are
recorded but not interpreted (no FAR or use tables), so capacity uses the context FAR and every use is allowed.

Run:  python -I -m planarena.cities.adapters.massgis "Cambridge"
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

from planarena.cities.common import finish_twin, reconcile_lot_area
from planarena.cities.registry import city_dir, register
from planarena.cities.tier_a import _districts, local_crs
from planarena.config import DATA, USE_INDEX as U, USE_KEYS, WEB_CRS
from planarena.national import census, places
from planarena.national.common import download
from planarena.twin.build import FLOOR_HEIGHT_M, _polygonal

RAW = DATA / "raw" / "massgis_l3"
BUCKET = "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
PREFIX = "shapefiles/l3parcels/"
ALL = (1 << len(USE_KEYS)) - 1
ASSESS_COLS = ["LOC_ID", "BLDG_VAL", "LAND_VAL", "OTHER_VAL", "TOTAL_VAL", "FY", "LOT_SIZE", "USE_CODE", "SITE_ADDR",
               "ZONING", "YEAR_BUILT", "BLD_AREA", "UNITS", "RES_AREA", "STORIES"]


def town_files() -> dict[str, str]:
    """MassGIS town key (letters only, upper case) -> zip file key in the public bucket."""
    out = {}
    r = subprocess.run(["curl", "-sf", "-m", "120", f"{BUCKET}?list-type=2&prefix={PREFIX}&max-keys=1000"],
                       check=True, capture_output=True, text=True)
    for k in re.findall(r"<Key>([^<]+)</Key>", r.stdout):
        m = re.match(rf"{PREFIX}L3_SHP_M(\d{{3}})_([A-Z]+)\.zip$", k)
        if m:
            out[m.group(2)] = k
    return out


def _key(name: str) -> str:
    return re.sub(r"[^A-Z]", "", name.upper())


def use_of(code: str, desc: str) -> str:
    """PlanArena use of a Massachusetts DOR property-type code, with the town's description as a tie-breaker."""
    c = (code or "").strip().upper()
    c3 = (c + "000")[:3] if c else ""
    d = (desc or "").upper()
    if "HOUSING AUTHORITY" in d or c3 == "908":
        return "res"
    if "PARKING" in d or "PKG" in d or c3 in ("336", "337"):
        return "prk"
    if "CONSERVATION" in d or "CEMETER" in d or "STATE PARKS" in d:
        return "opn"
    if "VACANT" in d or "UNDEVELOPABLE" in d or "DEVELOPABLE" in d or re.search(r"\bUNDEV\b", d) or c3 in ("130", "131", "132", "390", "391", "392", "440", "441", "442"):
        return "vac"
    if not c3 or not c3[0].isdigit():
        return "unknown"
    a, b, z = c3[0], c3[1], c3[2]
    if a == "0":  # mixed use: second digit is the primary class
        if b == "1" or (b == "3" and z == "1"):
            return "mix"
        return {"2": "opn", "3": "com", "4": "ind", "6": "opn", "7": "opn", "8": "opn", "9": "pub"}.get(b, "com")
    if a == "1":
        return "res"
    if a in "2678":
        return "opn"
    if a == "3":
        if c3 in ("304", "305") or b == "5":
            return "pub"
        if b == "1":
            return "ind"
        if b == "8":
            return "opn"
        return "com"
    if a == "4":
        return "tra" if b in "23" else "ind"
    if a == "5":
        return "com"
    if a == "9":
        if re.search(r"UTILIT|TRANSPORTATION|RAILROAD|ELECTRIC|TELEPHONE|PIPELINE|WATER SUPPLY", d):
            return "tra"
        if re.search(r"PARK|RECREATION|FOREST|BEACH", d):
            return "opn"
        return "pub"
    return "unknown"


def load(town_key: str, zip_key: str) -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.Series]:
    z = download(BUCKET + zip_key, RAW / zip_key.rsplit("/", 1)[1])
    ext = RAW / z.stem
    if not ext.exists():
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if ".." not in n and not n.startswith("/"):
                    zf.extract(n, ext)
    tp = next(ext.rglob("*TaxPar*.shp"))
    asf = next(ext.rglob("*Assess*.dbf"))
    g = gpd.read_file(tp, columns=["LOC_ID", "POLY_TYPE"], engine="pyogrio")
    a = pyogrio.read_dataframe(asf, read_geometry=False, columns=ASSESS_COLS)
    descs = {}
    for lut in sorted(ext.rglob("*UC_LUT*.dbf")):
        t = pyogrio.read_dataframe(lut, read_geometry=False)
        for r in t.sort_values("TOWN_ID").itertuples():  # town-specific rows (TOWN_ID > 0) override state rows
            descs[str(r.USE_CODE).strip()] = str(r.USE_DESC)
    return g, a, pd.Series(descs)


def build(target: str) -> dict:
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:6.0f}s] {s}", flush=True)
    hit = [places.place(target)] if target.isdigit() else places.search(target + ", MA", 1)
    if not hit or hit[0]["state"] != "MA":
        raise SystemExit(f"no Massachusetts town matches {target!r}")
    pl = places.place(hit[0]["geoid"])
    files = town_files()
    key = _key(pl["name"].replace(" city", "").replace(" town", "").replace(" Town", ""))
    zk = files.get(key) or next((v for k, v in files.items() if k.startswith(key) or key.startswith(k)), None)
    if zk is None:
        raise SystemExit(f"no MassGIS L3 file for {pl['label']}")
    geoid = pl["geoid"]
    out = city_dir(geoid)
    out.mkdir(parents=True, exist_ok=True)
    crs = local_crs(pl["lat"], pl["lon"])
    log(f"downloading MassGIS parcels ({zk.rsplit('/', 1)[1]})")
    g, a, descs = load(key, zk)
    g = g[g.geometry.notna() & (g.POLY_TYPE.fillna("FEE") != "ROW")].to_crs(crs)
    g["geometry"] = g.geometry.make_valid()
    g = g.dissolve("LOC_ID", as_index=False)  # multi-part parcels
    for c in ("BLDG_VAL", "LAND_VAL", "OTHER_VAL", "TOTAL_VAL", "LOT_SIZE", "YEAR_BUILT", "BLD_AREA", "UNITS",
              "RES_AREA", "STORIES", "FY"):
        a[c] = pd.to_numeric(a[c], errors="coerce").fillna(0)
    a["USE_CODE"] = a.USE_CODE.fillna("").astype(str).str.strip()
    a["use"] = [use_of(c, descs.get(c, descs.get(c[:3], ""))) for c in a.USE_CODE]
    # dwellings only on residential and mixed records (UNITS can count hotel rooms or beds elsewhere)
    a["UNITS"] = a.UNITS.where(a.use.isin(["res", "mix"]), 0.0)
    agg = a.groupby("LOC_ID").agg(
        use=("use", lambda s: s[s != "unknown"].value_counts().index[0] if (s != "unknown").any() else "unknown"),
        code=("USE_CODE", "first"), address=("SITE_ADDR", "first"), zone=("ZONING", "first"),
        lot_acres=("LOT_SIZE", "max"), bldg_area=("BLD_AREA", "sum"), res_area=("RES_AREA", "sum"),
        units=("UNITS", "sum"), floors=("STORIES", "max"), year=("YEAR_BUILT", "max"), land=("LAND_VAL", "sum"),
        tot=("TOTAL_VAL", "sum"), fy=("FY", "max"), n_records=("USE_CODE", "size"))
    p = g[["LOC_ID", "geometry"]].merge(agg, left_on="LOC_ID", right_index=True, how="left")
    p["use"] = p.use.fillna("unknown")
    p = p.reset_index(drop=True)
    p["geometry"] = p.geometry.map(_polygonal)
    log(f"{len(a):,} assessment records -> {len(p):,} parcels")

    bnd = places.boundary(geoid)
    blocks = census.blocks(geoid, bnd.bounds).to_crs(crs).reset_index(drop=True)
    inside = blocks.to_crs(4326).representative_point().within(bnd).to_numpy()
    blocks = blocks[(blocks.AREALAND > 0).to_numpy() & inside].reset_index(drop=True)
    rp = p.geometry.representative_point()
    tree = shapely.STRtree(blocks.geometry.values)
    i, k = tree.query(rp.values, predicate="within")
    blk = np.full(len(p), -1)
    blk[i] = k
    miss = blk < 0
    if miss.any():
        blk[miss] = tree.nearest(rp.values[miss])
    jobs_block = census.lodes_jobs("25", "MA").reindex(blocks.GEOID).fillna(0).to_numpy()

    use_a = p.use.map(U).fillna(-1).astype(int).to_numpy()
    fa = p.bldg_area.fillna(0).to_numpy()
    lot, n_lot_fixed = reconcile_lot_area(p.lot_acres.fillna(0).to_numpy() * 43560.0, p.geometry.area.to_numpy())
    res_area = np.where(use_a == U["res"], fa, np.where(use_a == U["mix"], np.clip(p.res_area.fillna(0), 0, fa), 0.0))
    res_area = np.where((use_a == U["mix"]) & (res_area <= 0), 0.7 * fa, res_area)  # mixed without RES_AREA: assumption
    nonres = fa - res_area
    c3 = p.code.fillna("").str[:3]
    com_like = np.isin(use_a, [U["com"], U["mix"]])
    retail = com_like & c3.str.match(r"^3[23]").to_numpy()
    office = com_like & ~retail & c3.str.match(r"^34").to_numpy()
    ind = use_a == U["ind"]
    storage = ind & c3.str.match(r"^31|^401").to_numpy()
    ll = gpd.GeoSeries(rp, crs=crs).to_crs(WEB_CRS)
    df = pd.DataFrame({
        "bbl": np.arange(len(p), dtype="int64"), "address": p.address.fillna("").astype(str).to_numpy(),
        "cd": 0, "block": blk.astype("int32"), "zone": p.zone.fillna("NA").astype(str).to_numpy(), "overlay": "",
        "special": "", "bldg_class": p.code.fillna("").astype(str).to_numpy(), "use": use_a.astype("int16"),
        "lot_area": lot, "bldg_area": fa, "res_area": res_area, "com_area": np.where(com_like, nonres, 0.0),
        "office_area": np.where(office, nonres, 0.0), "retail_area": np.where(retail, nonres, 0.0),
        "factory_area": np.where(ind & ~storage, nonres, 0.0), "storage_area": np.where(storage, nonres, 0.0),
        "garage_area": 0.0, "other_area": np.where(com_like & ~retail & ~office, nonres, 0.0),
        "num_bldgs": (fa > 0).astype(float), "floors": p.floors.fillna(0).to_numpy(),
        "units_res": p.units.fillna(0).to_numpy(), "units_total": p.units.fillna(0).to_numpy(),
        "assess_land": p.land.fillna(0).to_numpy(), "assess_tot": p.tot.fillna(0).to_numpy(),
        "year_built": p.year.fillna(0).to_numpy(),
        "built_far": np.divide(fa, lot, out=np.zeros(len(p)), where=lot > 0), "historic": False, "landmark": False,
        "x": rp.x.to_numpy(), "y": rp.y.to_numpy(), "lon": ll.x.to_numpy(), "lat": ll.y.to_numpy(),
        "height_m": p.floors.fillna(0).to_numpy() * FLOOR_HEIGHT_M, "census_block": blocks.GEOID.to_numpy()[blk],
        "loc_id": p.LOC_ID.astype(str).to_numpy(),
    })
    bg = df.census_block.str[:12]
    built = df.bldg_area > 0
    ctx = df[built].groupby(bg[built]).built_far.quantile(0.9)
    df["max_far"] = np.maximum(bg.map(ctx).fillna(df.built_far[built].quantile(0.9)).to_numpy(), df.built_far.to_numpy())
    df["resid_far"] = df["comm_far"] = df["facil_far"] = df["max_far"]
    df["allowed"] = ALL
    df["cd"] = _districts(df, blocks, blk)
    fy = int(p.fy.max()) if p.fy.notna().any() else None
    meta = finish_twin(df, p.geometry.values, crs, out, "MA", float(blocks.POP100.sum() / max(blocks.HU100.sum(), 1)),
                       jobs_block, blk, log, {
        "city": pl["label"], "geoid": geoid, "tier": "B",
        "source": f"MassGIS Level 3 assessors' parcels ({zk.rsplit('/', 1)[1]}, fiscal year {fy})",
        "source_url": "https://www.mass.gov/info-details/massgis-data-property-tax-parcels",
        "data_quality": {"missing_land_use": int((df.use < 0).sum()), "assessment_records": int(len(a)),
                         "condo_parcels": int((p.n_records.fillna(0) > 1).sum()),
                         "parcels_without_assessment": int(p.code.isna().sum()),
                         "zero_building_area": int((df.bldg_area <= 0).sum()), "lot_area_from_polygon": n_lot_fixed,
                         "jobs_lodes": int(round(jobs_block[np.unique(blk)].sum()))},
        "columns": {"lot boundaries": "observed (assessors' parcels)", "floor area": "observed (BLD_AREA)",
                    "land use": "observed (DOR use code)", "homes": "observed (UNITS on residential and mixed records)",
                    "jobs": "observed by block (LODES), modelled by floor area", "assessed value": "observed (TOTAL_VAL)",
                    "zoning": "codes recorded, not interpreted (context FAR, all uses allowed)",
                    "year built": "observed", "landmarks and historic districts": "missing"},
        "missing_indicators": [], "zoning_rules": "none (codes recorded only)",
        "levels": {str(d): f"Area {d}" for d in sorted(df.cd.unique())},
    }, t0=t0)
    register(geoid, pl["label"], "B", meta)
    log(f"done: {len(df):,} parcels")
    return meta


if __name__ == "__main__":
    m = build(" ".join(sys.argv[1:]) or "Cambridge")
    print(json.dumps({k: m[k] for k in ("city", "n_parcels", "use_counts", "data_quality", "build_seconds")}, indent=1))
