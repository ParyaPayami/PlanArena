"""Tier B adapter: City of Milwaukee, WI, from the Master Property File (MPROP) and parcel polygons.

Sources (City of Milwaukee Open Data, data.milwaukee.gov): MPROP (assessment, land use, floor area, units, year built,
stories, zoning, historic designation) and ParcelPolygonTax (parcel polygons keyed by tax key). Condominium units are
aggregated to their parcel, as MapPLUTO does. Owner names in MPROP are never read.

Zoning: Milwaukee regulates bulk with height, setback and density rules rather than one FAR, so PlanArena uses a
simplified screen: the district family sets which uses are allowed, and the context FAR (90th percentile of built FAR
in the census block group, or the lot's own built FAR if higher) stands in for capacity. Flagged in the UI.

Run:  python -I -m planarena.cities.adapters.milwaukee
"""
from __future__ import annotations

import json
import time
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from planarena.cities.common import finish_twin
from planarena.cities.registry import city_dir, register
from planarena.cities.tier_a import local_crs
from planarena.config import DATA, USE_INDEX as U, USE_KEYS, WEB_CRS
from planarena.national import census, places
from planarena.national.common import download
from planarena.twin.build import FLOOR_HEIGHT_M, _polygonal

GEOID = "5553000"
RAW = DATA / "raw"
MPROP_URL = ("https://data.milwaukee.gov/dataset/562ab824-48a5-42cd-b714-87e205e489ba/resource/"
             "0a2c7f31-cd15-4151-8222-09dd57d5f16d/download/mprop.csv")
PARCEL_URL = ("https://data.milwaukee.gov/dataset/3e238aee-5a21-4e2f-8ae7-803440c5d88a/resource/"
              "83503103-1049-4bc6-851f-2597d9cf580e/download/parcelpolygontax.zip")
COLS = ["TAXKEY", "HOUSE_NR_LO", "SDIR", "STREET", "STTYPE", "C_A_LAND", "C_A_TOTAL", "C_A_EXM_LAND", "C_A_EXM_TOTAL",
        "BLDG_TYPE", "NR_STORIES", "NR_UNITS", "BLDG_AREA", "YR_BUILT", "LOT_AREA", "ZONING", "LAND_USE", "LAND_USE_GP",
        "GEO_ALDER", "HIST_CODE", "YR_ASSMT"]
# MPROP land-use group (Appendix H) -> PlanArena use
GROUP_USE = {1: "res", 2: "res", 3: "res", 4: "mix", 5: "com", 6: "com", 7: "com", 8: "ind", 9: "tra", 10: "opn",
             11: "pub", 12: "opn", 13: "vac"}
PARKING_CODES = {7521, 7523, 7525}
STORAGE_CODES = set(range(4221, 4227)) | {4231}  # warehousing and storage
HISTORIC_LOCAL = {"1", "3", "5", "7"}  # locally designated (protected); 2 and 4 are National Register only
ALL = (1 << len(USE_KEYS)) - 1
bit = lambda *keys: sum(1 << U[k] for k in keys)
ZONING_FAMILY = {  # district prefix -> allowed PlanArena uses (simplified from the Milwaukee Zoning Code, ch. 295)
    "RS": bit("res", "pub", "opn", "vac"), "RT": bit("res", "pub", "opn", "vac"),
    "RM": bit("res", "mix", "pub", "opn", "prk", "vac"), "RO": bit("res", "mix", "com", "pub", "opn", "prk", "vac"),
    "NS": bit("res", "mix", "com", "pub", "opn", "prk", "vac"), "LB": bit("res", "mix", "com", "pub", "opn", "prk", "vac"),
    "RB": bit("res", "mix", "com", "pub", "opn", "prk", "vac"), "CS": bit("res", "mix", "com", "pub", "opn", "prk", "vac"),
    "C9": bit("res", "mix", "com", "pub", "opn", "prk", "tra", "vac"),
    "IO": bit("com", "ind", "tra", "pub", "opn", "prk", "vac"), "IL": bit("com", "ind", "tra", "pub", "opn", "prk", "vac"),
    "IM": bit("mix", "com", "ind", "tra", "pub", "opn", "prk", "vac"), "IH": bit("ind", "tra", "pub", "opn", "prk", "vac"),
    "PK": bit("opn", "pub", "vac"), "TL": bit("res", "mix", "com", "pub", "opn", "prk", "vac"),
}


def _family(z: str) -> str:
    z = (z or "").upper()
    return z[:2] if z[:2] in ZONING_FAMILY else ("PD" if z.startswith("PD") else "OTHER")


def load() -> gpd.GeoDataFrame:
    mf = download(MPROP_URL, RAW / "milwaukee_mprop" / "mprop.csv")
    zf = download(PARCEL_URL, RAW / "milwaukee_parcels" / "parcelpolygontax.zip")
    ext = zf.parent / "extracted"
    if not ext.exists():
        with zipfile.ZipFile(zf) as z:
            for n in z.namelist():
                if ".." not in n and not n.startswith("/"):
                    z.extract(n, ext)
    shp = next(ext.rglob("ParcelPolygonTax.shp"))
    g = gpd.read_file(shp, columns=["FK_Tax", "FK_Parcel", "InactiveFl"], engine="pyogrio")
    g = g[(g.InactiveFl == 0) & g.geometry.notna()]
    m = pd.read_csv(mf, dtype=str, usecols=COLS)
    m["key"] = pd.to_numeric(m.TAXKEY, errors="coerce")
    g["key"] = pd.to_numeric(g.FK_Tax, errors="coerce")
    return g.merge(m, on="key", how="left")


def build() -> dict:
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:6.0f}s] {s}", flush=True)
    pl = places.place(GEOID)
    out = city_dir(GEOID)
    out.mkdir(parents=True, exist_ok=True)
    crs = local_crs(pl["lat"], pl["lon"])
    g = load().to_crs(crs)
    g["geometry"] = g.geometry.make_valid()
    num = lambda c: pd.to_numeric(g[c], errors="coerce").fillna(0).astype(float)
    for c in ("C_A_LAND", "C_A_TOTAL", "C_A_EXM_LAND", "C_A_EXM_TOTAL", "NR_STORIES", "NR_UNITS", "BLDG_AREA", "YR_BUILT",
              "LOT_AREA", "LAND_USE", "LAND_USE_GP"):
        g[c] = num(c)
    # NR_UNITS also counts hotel rooms, nursing-home beds and other non-dwelling units (MPROP documentation);
    # dwellings are counted only on residential and mixed land-use groups (1-4).
    g["NR_UNITS"] = g.NR_UNITS.where(g.LAND_USE_GP.astype(int).isin([1, 2, 3, 4]), 0.0)
    code = g.LAND_USE.astype(int)
    use = g.LAND_USE_GP.astype(int).map(GROUP_USE)
    use = use.where(~code.isin(PARKING_CODES), "prk")
    g["use_i"] = use.map(U).fillna(-1).astype(int)
    g["addr"] = (g.HOUSE_NR_LO.fillna("").str.lstrip("0") + " " + g.SDIR.fillna("") + " " + g.STREET.fillna("") + " "
                 + g.STTYPE.fillna("")).str.split().str.join(" ")
    # condominium units -> one parcel (sum quantities, keep the most common use, the first geometry)
    agg = g.groupby("FK_Parcel").agg(
        geometry=("geometry", "first"), taxkey=("key", "min"), address=("addr", "first"), zone=("ZONING", "first"),
        use=("use_i", lambda s: s.value_counts().index[0]), code=("LAND_USE", "first"), bldg_type=("BLDG_TYPE", "first"),
        lot_area=("LOT_AREA", "max"), bldg_area=("BLDG_AREA", "sum"), units=("NR_UNITS", "sum"), floors=("NR_STORIES", "max"),
        year=("YR_BUILT", "max"), land=("C_A_LAND", "sum"), tot=("C_A_TOTAL", "sum"), exl=("C_A_EXM_LAND", "sum"),
        ext=("C_A_EXM_TOTAL", "sum"), alder=("GEO_ALDER", "first"), histcode=("HIST_CODE", "first"), n_keys=("key", "size"))
    p = gpd.GeoDataFrame(agg.reset_index(drop=True), geometry="geometry", crs=crs)
    p["geometry"] = p.geometry.map(_polygonal)
    log(f"{len(g):,} tax keys -> {len(p):,} parcels")

    bnd = places.boundary(GEOID)
    blocks = census.blocks(GEOID, bnd.bounds).to_crs(crs).reset_index(drop=True)
    inside = blocks.to_crs(4326).representative_point().within(bnd).to_numpy()
    blocks = blocks[(blocks.AREALAND > 0).to_numpy() & inside].reset_index(drop=True)
    rp = p.geometry.representative_point()
    a, k = shapely.STRtree(blocks.geometry.values).query(rp.values, predicate="within")
    blk = np.full(len(p), -1)
    blk[a] = k
    miss = blk < 0
    if miss.any():
        blk[miss] = shapely.STRtree(blocks.geometry.values).nearest(rp.values[miss])
    jobs = census.lodes_jobs("55", "WI")
    jobs_block = jobs.reindex(blocks.GEOID).fillna(0).to_numpy()

    use_a = p.use.to_numpy()
    fa = p.bldg_area.to_numpy()
    lot = np.where(p.lot_area > 0, p.lot_area, p.geometry.area).astype(float)
    res = np.isin(use_a, [U["res"]])
    mix = use_a == U["mix"]
    MIX_RES = 0.7  # assumption, as for Tier A: MPROP has no residential/commercial split
    res_area = np.where(res, fa, np.where(mix, MIX_RES * fa, 0.0))
    nonres = fa - res_area
    grp = (p.code // 1000).astype(int).to_numpy()
    com_like = np.isin(use_a, [U["com"], U["mix"]])
    retail = com_like & (grp == 5)
    office = com_like & ~retail & np.isin((p.code // 100).astype(int).to_numpy(), list(range(60, 68)) + list(range(73, 74)) + [80, 81, 87])
    ind = use_a == U["ind"]
    storage = ind & p.code.astype(int).isin(STORAGE_CODES).to_numpy()
    pt = rp
    ll = gpd.GeoSeries(pt, crs=crs).to_crs(WEB_CRS)
    zone = p.zone.fillna("NA").astype(str)
    fam = zone.map(_family)
    df = pd.DataFrame({
        "bbl": p.taxkey.astype("int64").to_numpy(), "address": p.address.fillna("").to_numpy(),
        "cd": pd.to_numeric(p.alder, errors="coerce").fillna(0).astype("int32").to_numpy(),
        "block": blk.astype("int32"), "zone": zone.to_numpy(), "overlay": "", "special": "",
        "bldg_class": p.bldg_type.fillna("").astype(str).to_numpy(), "use": use_a.astype("int16"),
        "lot_area": lot, "bldg_area": fa, "res_area": res_area, "com_area": np.where(com_like, nonres, 0.0),
        "office_area": np.where(office, nonres, 0.0), "retail_area": np.where(retail, nonres, 0.0),
        "factory_area": np.where(ind & ~storage, nonres, 0.0), "storage_area": np.where(storage, nonres, 0.0),
        "garage_area": 0.0, "other_area": np.where(com_like & ~retail & ~office, nonres, 0.0),
        "num_bldgs": (fa > 0).astype(float), "floors": p.floors.to_numpy(), "units_res": p.units.to_numpy(),
        "units_total": p.units.to_numpy(), "assess_land": (p.land + p.exl).to_numpy(),
        "assess_tot": (p.tot + p.ext).to_numpy(), "year_built": p.year.to_numpy(),
        "built_far": np.divide(fa, lot, out=np.zeros(len(p)), where=lot > 0),
        "historic": p["histcode"].fillna("").astype(str).isin(HISTORIC_LOCAL).to_numpy(), "landmark": False,
        "x": pt.x.to_numpy(), "y": pt.y.to_numpy(), "lon": ll.x.to_numpy(), "lat": ll.y.to_numpy(),
        "height_m": p.floors.to_numpy() * FLOOR_HEIGHT_M, "census_block": blocks.GEOID.to_numpy()[blk],
    })
    bg = df.census_block.str[:12]
    built = df.bldg_area > 0
    ctx = df[built].groupby(bg[built]).built_far.quantile(0.9)
    df["max_far"] = np.maximum(bg.map(ctx).fillna(df.built_far[built].quantile(0.9)).to_numpy(), df.built_far.to_numpy())
    df["resid_far"] = df["comm_far"] = df["facil_far"] = df["max_far"]
    df["allowed"] = fam.map(lambda f: ZONING_FAMILY.get(f, ALL)).to_numpy().astype("int64")
    alders = sorted(d for d in df.cd.unique() if d > 0)
    meta = finish_twin(df, p.geometry.values, crs, out, "WI", float(blocks.POP100.sum() / max(blocks.HU100.sum(), 1)),
                       jobs_block, blk, log, {
        "city": pl["label"], "geoid": GEOID, "tier": "B",
        "source": f"City of Milwaukee MPROP (assessment year {int(pd.to_numeric(g.YR_ASSMT, errors='coerce').max())}) and parcel polygons",
        "source_url": "https://data.milwaukee.gov/dataset/mprop",
        "data_quality": {"missing_land_use": int((df.use < 0).sum()), "tax_keys": int(len(g)),
                         "condo_parcels": int((p.n_keys > 1).sum()), "zero_building_area": int((df.bldg_area <= 0).sum()),
                         "lots_outside_census_blocks": int(miss.sum()), "jobs_lodes": int(round(jobs_block[np.unique(blk)].sum()))},
        "columns": {"lot boundaries": "observed (city parcels)", "floor area": "observed (MPROP BLDG_AREA)",
                    "land use": "observed (MPROP land-use group)",
                    "homes": "observed (MPROP NR_UNITS on residential and mixed parcels only)",
                    "jobs": "observed by block (LODES), modelled by floor area", "assessed value": "observed (MPROP, incl. exempt)",
                    "zoning": "simplified (district family sets allowed uses; context FAR for capacity)",
                    "year built": "observed", "landmarks and historic districts": "observed (locally designated)",
                    "mixed-use split": "assumed 70% residential"},
        "missing_indicators": [], "zoning_rules": "Milwaukee Zoning Code district families (simplified)",
        "levels": {str(d): f"Aldermanic district {d}" for d in alders},
    }, t0=t0)
    register(GEOID, pl["label"], "B", meta)
    log(f"done: {len(df):,} parcels")
    return meta


if __name__ == "__main__":
    m = build()
    print(json.dumps({k: m[k] for k in ("city", "n_parcels", "use_counts", "data_quality", "build_seconds")}, indent=1))
