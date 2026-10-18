"""Tier A twin of any US place from national open data (no parcel file needed).

Lots are pseudo-lots. Within each 2020 census block, every building's Voronoi cell (seeded at the building's
representative point, clipped to the block and capped at 30 m from the building) is one lot; block land outside
every cell becomes lots without buildings. What each column holds, and how good it is, is recorded per column in
twin_meta.json ("columns": observed / estimated / missing).

Sources: Census 2020 blocks (housing units, population), LEHD LODES 2023 (jobs), Overture Maps buildings, places and
land use, EIA RECS/CBECS and EPA eGRID/Emission Factors Hub (energy and emissions). No zoning or assessed value.

Run:  python -I -m planarena.cities.tier_a <GEOID or "City, ST">
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from planarena.cities.common import finish_twin
from planarena.cities.registry import city_dir, register
from planarena.config import FT_PER_M, USE_INDEX as U, USE_KEYS, WEB_CRS
from planarena.national import census, overture, places
from planarena.twin.build import FLOOR_HEIGHT_M, _polygonal

SQFT_PER_M2 = FT_PER_M ** 2
MIN_BLDG_M2 = 20.0        # smaller footprints are sheds and noise
CELL_CAP_M = 30.0         # a building's lot extends at most this far from the building
MIN_OPEN_SQFT = 5000.0    # block land outside building cells smaller than this is dropped
ACCESSORY_M2 = 60.0       # a building this small within ACCESSORY_NEAR_M of a larger one is accessory (garage, shed)
ACCESSORY_NEAR_M = 25.0
MIX_RES_SHARE = 0.7       # assumption: residential share of a mixed-use building's floor area
ALL_USES = (1 << len(USE_KEYS)) - 1

# Overture building subtype -> PlanArena use
BLDG_SUBTYPE = {"residential": "res", "commercial": "com", "entertainment": "com", "service": "com",
                "industrial": "ind", "agricultural": "ind", "education": "pub", "medical": "pub", "civic": "pub",
                "religious": "pub", "military": "pub", "transportation": "tra"}
# Overture place taxonomy (top level) -> PlanArena use; hospitals are public institutions, clinics commercial
PLACE_TOP = {"shopping": "com", "food_and_drink": "com", "services_and_business": "com", "lifestyle_services": "com",
             "lodging": "com", "arts_and_entertainment": "com", "sports_and_recreation": "com", "health_care": "com",
             "education": "pub", "community_and_government": "pub", "cultural_and_historic": "pub",
             "travel_and_transportation": "tra"}
RETAIL_TOP = {"shopping", "food_and_drink", "lifestyle_services"}
OFFICE_TOP = {"services_and_business", "health_care"}
# Overture land-use subtype/class -> use of land without buildings (or evidence for a building's use)
OPEN_LU = {"park", "recreation", "golf", "cemetery", "protected", "managed", "horticulture", "agriculture",
           "landfill"}
LU_EVIDENCE = {"education": "pub", "medical": "pub", "religious": "pub", "military": "pub", "transportation": "tra",
               "residential": "res"}
LU_CLASS = {"retail": "com", "commercial": "com", "industrial": "ind", "parking": "prk", "railway": "tra",
            "school": "pub", "hospital": "pub", "university": "pub", "college": "pub"}


def local_crs(lat: float, lon: float) -> str:
    """Transverse Mercator centred on the place, in US feet (the units the engine uses everywhere)."""
    return f"+proj=tmerc +lat_0={lat:.5f} +lon_0={lon:.5f} +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=us-ft +no_defs"


# ----------------------------------------------------------------------------- lots
def tessellate(blocks: gpd.GeoDataFrame, bldg: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Pseudo-lots: building cells inside blocks, plus remaining block land."""
    cap = CELL_CAP_M * FT_PER_M
    geoms, blk_of, has_bldg = [], [], []
    main = np.nonzero(~bldg.accessory.to_numpy())[0]
    by_block = {k: main[v] for k, v in pd.Series(bldg.block.to_numpy()[main]).groupby(bldg.block.to_numpy()[main]).indices.items()}
    for bi, blk in enumerate(blocks.geometry.values):
        idx = by_block.get(bi)
        if idx is None:
            if blk.area >= MIN_OPEN_SQFT:
                geoms.append(blk); blk_of.append(bi); has_bldg.append(False)
            continue
        pts = bldg.rp.values[idx]
        xy = np.round(shapely.get_coordinates(pts), 1)
        uniq, inv = np.unique(xy, axis=0, return_inverse=True)
        inv = inv.ravel()
        foot = [shapely.union_all(bldg.geometry.values[idx][inv == k]) for k in range(len(uniq))]
        if len(uniq) == 1:
            cells = [blk]
        else:
            vor = shapely.voronoi_polygons(shapely.multipoints(uniq), extend_to=blk, ordered=True)
            cells = list(shapely.get_parts(vor))
        cells = shapely.intersection(shapely.intersection(np.array(cells, dtype=object), blk),
                                     shapely.buffer(np.array(foot, dtype=object), cap))
        cells = shapely.make_valid(cells)
        for c in cells:
            if not c.is_empty and c.area > 0:
                geoms.append(c); blk_of.append(bi); has_bldg.append(True)
        rest = shapely.difference(blk, shapely.union_all(cells))
        for part in shapely.get_parts(rest):
            if part.geom_type == "Polygon" and part.area >= MIN_OPEN_SQFT:
                geoms.append(part); blk_of.append(bi); has_bldg.append(False)
    lots = gpd.GeoDataFrame({"block_i": np.array(blk_of, "int64"), "cell": np.array(has_bldg)},
                            geometry=geoms, crs=blocks.crs)
    lots["geometry"] = lots.geometry.map(_polygonal)
    return lots


def _join_points(lots: gpd.GeoDataFrame, pts: gpd.GeoSeries) -> np.ndarray:
    """Index of the lot containing each point (-1 if none)."""
    tree = shapely.STRtree(lots.geometry.values)
    a, b = tree.query(pts.values, predicate="within")
    out = np.full(len(pts), -1)
    out[a] = b
    return out


# ----------------------------------------------------------------------------- land use
def classify(lots, bldg_lot, bldg, poi_lot, pois, lu_at_lot, hu_block) -> tuple[np.ndarray, np.ndarray, dict]:
    """Rule-based land use of each pseudo-lot, its confidence and floor-area shares. See module docs."""
    n = len(lots)
    use = np.full(n, -1)
    conf = np.zeros(n)  # 2: building tag or place evidence; 1: block housing or land-use polygon; 0: default
    # building evidence
    bsub = pd.Series(bldg.subtype.map(BLDG_SUBTYPE).to_numpy(), index=bldg_lot)
    bsub = bsub[(bsub.index >= 0) & bsub.notna()]
    b_use = bsub.groupby(level=0).agg(lambda s: s.value_counts().index[0])
    # place evidence
    top = pois.hierarchy.fillna("").str.split(">").str[0]
    puse = top.map(PLACE_TOP).where(~pois.basic_category.fillna("").str.contains("hospital"), "pub")
    pdf = pd.DataFrame({"lot": poi_lot, "use": puse.to_numpy(), "top": top.to_numpy()})
    pdf = pdf[(pdf.lot >= 0) & pdf.use.notna()]
    p_use = pdf.groupby("lot").use.agg(lambda s: s.value_counts().index[0])
    n_poi = pdf.groupby("lot").size()
    retail = pdf[pdf.top.isin(RETAIL_TOP)].groupby("lot").size().reindex(n_poi.index, fill_value=0) / n_poi
    office = pdf[pdf.top.isin(OFFICE_TOP)].groupby("lot").size().reindex(n_poi.index, fill_value=0) / n_poi
    floors = lots.floors.to_numpy()
    built = lots.bldg_area.to_numpy() > 0
    hu = hu_block[lots.block_i.to_numpy()] > 0
    for i in range(n):
        lu_sub, lu_cls = lu_at_lot[i]
        if not built[i]:
            if lu_cls == "parking":
                use[i], conf[i] = U["prk"], 1
            elif lu_sub in OPEN_LU or lu_cls in ("park", "grass", "pitch", "playground", "garden", "cemetery"):
                use[i], conf[i] = U["opn"], 1
            else:
                use[i] = U["vac"]
            continue
        b, p = b_use.get(i), p_use.get(i)
        if b is not None:
            u, c = b, 2
            if b == "res" and p == "com":
                u = "mix"
        elif p is not None:
            u, c = p, 2
            if p == "com" and hu[i] and floors[i] >= 3:
                u = "mix"
        elif lu_cls in LU_CLASS and LU_CLASS[lu_cls] != "prk":
            u, c = LU_CLASS[lu_cls], 1
        elif lu_sub in LU_EVIDENCE:
            u, c = LU_EVIDENCE[lu_sub], 1
        elif hu[i]:
            u, c = "res", 1
        else:
            u, c = ("ind" if lots.footprint_sqft.iloc[i] > 20000 else "com"), 0
        use[i], conf[i] = U[u], c
    shares = {"retail": retail, "office": office}
    return use, conf, shares


# ----------------------------------------------------------------------------- features for the land-use model
POI_TOPS = sorted(set(PLACE_TOP) | {"geographic_entities"})
LU_SUBTYPES = sorted(OPEN_LU | set(LU_EVIDENCE) | {"developed", "pedestrian", "construction", "entertainment"})
LU_CLASSES = sorted(set(LU_CLASS) | {"grass", "pitch", "playground", "park", "garden", "cemetery"})


def lot_features(lots, bldg_lot, bldg, poi_lot, pois, lu_at_lot, blocks, rule_use, conf) -> pd.DataFrame:
    """What the national sources say about each pseudo-lot; the land-use model's inputs (no city-specific data)."""
    n = len(lots)
    f = pd.DataFrame(index=lots.index)
    f["foot"] = np.log1p(lots.footprint_sqft)
    f["fa"] = np.log1p(lots.bldg_area)
    f["floors"] = lots.floors
    f["height"] = lots.height_m
    f["height_observed"] = lots.height_observed.astype(float)
    f["lot"] = np.log1p(lots.geometry.area)
    f["coverage"] = np.divide(lots.footprint_sqft, lots.geometry.area, out=np.zeros(n), where=lots.geometry.area > 0)
    f["accessory"] = np.log1p(lots.accessory_sqft)
    f["n_bldgs"] = lots.num_bldgs
    sub = pd.Series(bldg.subtype.fillna("none").to_numpy(), index=bldg_lot)
    sub = sub[sub.index >= 0]
    for k in sorted(BLDG_SUBTYPE) + ["none"]:
        f[f"bsub_{k}"] = (sub == k).groupby(level=0).sum().reindex(f.index, fill_value=0).astype(float)
    top = pois.hierarchy.fillna("").str.split(">").str[0].to_numpy()
    pdf = pd.DataFrame({"lot": poi_lot, "top": top, "hosp": pois.basic_category.fillna("").str.contains("hospital").to_numpy()})
    pdf = pdf[pdf.lot >= 0]
    cnt = pd.crosstab(pdf.lot, pdf.top).reindex(index=f.index, columns=POI_TOPS, fill_value=0)
    for k in POI_TOPS:
        f[f"poi_{k}"] = np.log1p(cnt[k].to_numpy())
    f["poi_hospital"] = pdf.groupby("lot").hosp.any().reindex(f.index, fill_value=False).astype(float)
    lu_s = np.array([x[0] or "" for x in lu_at_lot], dtype=object)
    lu_c = np.array([x[1] or "" for x in lu_at_lot], dtype=object)
    for k in LU_SUBTYPES:
        f[f"lus_{k}"] = (lu_s == k).astype(float)
    for k in LU_CLASSES:
        f[f"luc_{k}"] = (lu_c == k).astype(float)
    blk = lots.block_i.to_numpy()
    hu = blocks.HU100.to_numpy()[blk]
    pop = blocks.POP100.to_numpy()[blk]
    bfa = lots.bldg_area.groupby(blk).sum().reindex(blk).to_numpy()
    f["block_hu"] = np.log1p(hu)
    f["block_pop"] = np.log1p(pop)
    f["block_fa"] = np.log1p(bfa)
    f["block_hu_per_kft2"] = np.divide(hu, bfa / 1000, out=np.zeros(n), where=bfa > 0)
    f["share_of_block_fa"] = np.divide(lots.bldg_area.to_numpy(), bfa, out=np.zeros(n), where=bfa > 0)
    f["block_lots"] = np.log1p(pd.Series(blk).map(pd.Series(blk).value_counts()).to_numpy())
    for u, k in enumerate(USE_KEYS):
        f[f"rule_{k}"] = (rule_use == u).astype(float)
    f["rule_confidence"] = conf
    return f


# ----------------------------------------------------------------------------- build
def floor_area_correction() -> tuple[float, list[str]]:
    """Median Tier A / Tier B floor-area ratio over the comparison cities (planarena.cities.compare), or 1."""
    from planarena.config import ROOT

    files = {f.stem[len("tier_a_vs_b_"):]: f for f in (ROOT / "results" / "validation").glob("tier_a_vs_b_*.json")}
    if "newyork" in files:  # Manhattan is part of New York City: count the city once
        files.pop("manhattan", None)
    rs, names = [], []
    for name, f in sorted(files.items()):
        r = json.loads(f.read_text())["floor_area_by_block"].get("total_ratio")
        if r:
            rs.append(r)
            names.append(name)
    return (float(np.median(rs)), names) if rs else (1.0, [])


def build_city(target: str, out_dir: Path | None = None, area: dict | None = None, use_model: bool = True,
               correct_floor_area: bool = True) -> dict:
    """Build a place by GEOID or name, or any area given as {"id", "label", "state", "boundary" (EPSG:4326)}
    (used to run Tier A inside a Tier B city for the accuracy comparison)."""
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.0f}s] {m}", flush=True)
    if area:
        bnd = area["boundary"]
        c = bnd.representative_point()
        pl = {"geoid": area["id"], "label": area["label"], "state": area["state"], "lat": c.y, "lon": c.x}
    else:
        hit = places.search(target, 1) if not target.isdigit() else [places.place(target)]
        if not hit:
            raise SystemExit(f"no US place matches {target!r}")
        pl = places.place(hit[0]["geoid"])
        bnd = places.boundary(pl["geoid"])
    geoid = pl["geoid"]
    out = out_dir or city_dir(geoid)
    out.mkdir(parents=True, exist_ok=True)
    crs = local_crs(pl["lat"], pl["lon"])
    bbox = bnd.bounds

    log("downloading Census 2020 blocks")
    blocks = census.blocks(geoid, bbox)
    blocks = blocks[(blocks.AREALAND > 0) & blocks.representative_point().within(bnd)].to_crs(crs).reset_index(drop=True)
    blocks["geometry"] = blocks.geometry.make_valid()
    log(f"{len(blocks):,} census blocks, {int(blocks.HU100.sum()):,} housing units, {int(blocks.POP100.sum()):,} people")

    log("downloading Overture buildings (a few minutes)")
    b = overture.fetch(geoid, bbox, "buildings")
    b = b[~b.is_underground.fillna(False).astype(bool)].to_crs(crs)
    b["geometry"] = b.geometry.make_valid()
    b = b[b.geometry.area >= MIN_BLDG_M2 * SQFT_PER_M2].reset_index(drop=True)
    b["rp"] = b.geometry.representative_point()
    tree = shapely.STRtree(blocks.geometry.values)
    a, k = tree.query(b.rp.values, predicate="within")
    b["block"] = -1
    b.loc[a, "block"] = k
    b = b[b.block >= 0].reset_index(drop=True)
    h = pd.to_numeric(b.height, errors="coerce")
    nf = pd.to_numeric(b.num_floors, errors="coerce")
    h = h.where(h > 0, nf * FLOOR_HEIGHT_M)
    b["height_obs"] = h.notna()
    med_block = h.groupby(b.block).median()
    city_med = float(h.median()) if h.notna().any() else 2 * FLOOR_HEIGHT_M
    b["height_m"] = h.fillna(b.block.map(med_block)).fillna(city_med).clip(lower=FLOOR_HEIGHT_M * 0.8)
    b["floors"] = np.maximum(1, np.round(b.height_m / FLOOR_HEIGHT_M))
    b["foot_sqft"] = b.geometry.area
    small = b.foot_sqft < ACCESSORY_M2 * SQFT_PER_M2
    big = ~small
    near = np.zeros(len(b), bool)
    if small.any() and big.any():
        a, k = shapely.STRtree(b.geometry.values[big.to_numpy()]).query(
            b.geometry.values[small.to_numpy()], predicate="dwithin", distance=ACCESSORY_NEAR_M * FT_PER_M)
        hit = np.zeros(int(small.sum()), bool)
        hit[np.unique(a)] = True
        near[np.nonzero(small.to_numpy())[0]] = hit
    b["accessory"] = near
    log(f"{len(b):,} buildings ({int(near.sum()):,} accessory); height observed for {b.height_obs.mean():.0%}")

    lots = tessellate(blocks, b)
    lot_of_b = _join_points(lots, b.rp)
    miss = lot_of_b < 0
    if miss.any():  # representative point fell outside its own (capped) cell: nearest lot in the same block
        near = shapely.STRtree(lots.geometry.values).nearest(b.rp.values[miss])
        lot_of_b[miss] = near
    acc = b.accessory.to_numpy()
    agg = pd.DataFrame({"lot": lot_of_b, "foot": b.foot_sqft, "fa": np.where(acc, 0.0, b.foot_sqft * b.floors),
                        "acc": np.where(acc, b.foot_sqft, 0.0), "floors": np.where(acc, 0, b.floors),
                        "h": np.where(acc, 0, b.height_m), "obs": b.height_obs & ~acc}).groupby("lot")
    lots["accessory_sqft"] = agg.acc.sum().reindex(lots.index, fill_value=0.0)
    lots["footprint_sqft"] = agg.foot.sum().reindex(lots.index, fill_value=0.0)
    lots["bldg_area"] = agg.fa.sum().reindex(lots.index, fill_value=0.0)
    fa_corr, fa_cities = floor_area_correction() if correct_floor_area else (1.0, [])
    lots["bldg_area"] = lots.bldg_area / fa_corr  # footprint x floors overstates floor area (measured in Tier B cities)
    lots["floors"] = agg.floors.max().reindex(lots.index, fill_value=0.0)
    lots["height_m"] = agg.h.max().reindex(lots.index, fill_value=0.0)
    lots["num_bldgs"] = agg.size().reindex(lots.index, fill_value=0).astype(float)
    lots["height_observed"] = agg.obs.any().reindex(lots.index, fill_value=False)
    lots.loc[lots.bldg_area <= 0, "cell"] = False  # a cell left holding only accessory buildings
    log(f"{len(lots):,} pseudo-lots ({int(lots.cell.sum()):,} with buildings)")

    log("downloading Overture places and land use")
    pois = overture.fetch(geoid, bbox, "places")
    pois = pois[(pois.confidence.fillna(0) >= 0.5) & (pois.operating_status.fillna("open") == "open")].to_crs(crs)
    poi_lot = _join_points(lots, pois.geometry)
    lu = overture.fetch(geoid, bbox, "land_use").to_crs(crs)
    lu = lu[lu.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
    lu_at = [(None, None)] * len(lots)
    if len(lu):
        rp = lots.geometry.representative_point()
        a, k = shapely.STRtree(lu.geometry.values).query(rp.values, predicate="within")
        lu_area = lu.geometry.area.to_numpy()
        best = pd.DataFrame({"lot": a, "lu": k, "area": lu_area[k]}).sort_values("area").drop_duplicates("lot")
        for i, j in zip(best.lot, best.lu):
            lu_at[i] = (lu.subtype.iloc[j], lu["class"].iloc[j])
    use, conf, shares = classify(lots, lot_of_b, b, poi_lot, pois, lu_at, blocks.HU100.to_numpy())
    feats = lot_features(lots, lot_of_b, b, poi_lot, pois, lu_at, blocks, use, conf)
    feats.to_parquet(out / "lot_features.parquet")
    land_use_method = "rules"
    if use_model:
        from planarena.cities import landuse_model

        pred = landuse_model.predict(feats)
        if pred is not None:
            built = lots.bldg_area.to_numpy() > 0
            use = np.where(built, pred, use)  # lots without buildings keep the open/parking/vacant rules
            conf = np.where(built, 3, conf)
            land_use_method = "model"
    log(f"land use ({land_use_method}): " + ", ".join(f"{USE_KEYS[u]} {int((use == u).sum()):,}" for u in range(len(USE_KEYS))))

    # homes: each block's 2020 housing units, allocated to its residential and mixed lots by residential floor area
    res_area = np.where(use == U["res"], lots.bldg_area, np.where(use == U["mix"], MIX_RES_SHARE * lots.bldg_area, 0.0))
    hu_block = blocks.HU100.to_numpy()
    blk = lots.block_i.to_numpy()
    tot_res = pd.Series(res_area).groupby(blk).sum()
    orphan = [bi for bi in np.nonzero(hu_block > 0)[0] if tot_res.get(bi, 0) <= 0]
    for bi in orphan:  # housing counted but no residential lot recognised: largest unlabelled buildings become homes
        cand = np.nonzero((blk == bi) & (lots.bldg_area.to_numpy() > 0) & (conf < 2))[0]
        if not len(cand):
            cand = np.nonzero((blk == bi) & (lots.bldg_area.to_numpy() > 0) & ~np.isin(use, [U["pub"], U["tra"]]))[0]
        if len(cand):
            use[cand] = np.where(use[cand] == U["com"], U["mix"], U["res"])
            res_area[cand] = np.where(use[cand] == U["mix"], MIX_RES_SHARE, 1.0) * lots.bldg_area.to_numpy()[cand]
    tot_res = pd.Series(res_area).groupby(blk).sum()
    units = hu_block[blk] * np.divide(res_area, tot_res.reindex(blk).to_numpy(), out=np.zeros(len(lots)),
                                      where=tot_res.reindex(blk).to_numpy() > 0)
    unalloc = float(hu_block.sum() - units.sum())
    units = _round_by_block(units, blk)

    # floor-area components (engine schema)
    fa = lots.bldg_area.to_numpy()
    nonres = fa - res_area
    com_like = np.isin(use, [U["com"], U["mix"]])
    r_sh = shares["retail"].reindex(lots.index).to_numpy()
    o_sh = shares["office"].reindex(lots.index).to_numpy()
    no_poi = np.isnan(r_sh)
    r_sh = np.where(no_poi, 0.3, r_sh)  # assumption without places: 30% retail, 50% office, 20% other
    o_sh = np.where(no_poi, 0.5, o_sh)
    oth = np.clip(1 - r_sh - o_sh, 0, 1)
    ind = use == U["ind"]

    log("downloading LODES jobs")
    jobs = census.lodes_jobs(blocks.GEOID.iloc[0][:2], pl["state"])
    jobs_block = jobs.reindex(blocks.GEOID).fillna(0).to_numpy()

    pt = lots.geometry.representative_point()
    ll = gpd.GeoSeries(pt, crs=crs).to_crs(WEB_CRS)
    df = pd.DataFrame({
        "bbl": np.arange(len(lots), dtype="int64"), "address": "",
        "cd": 0, "block": blk.astype("int32"), "zone": "NA", "overlay": "", "special": "", "bldg_class": "",
        "use": use.astype("int16"), "lot_area": lots.geometry.area.to_numpy(), "bldg_area": fa,
        "res_area": res_area, "com_area": np.where(com_like, nonres, 0.0),
        "office_area": np.where(com_like, nonres * o_sh, 0.0), "retail_area": np.where(com_like, nonres * r_sh, 0.0),
        "factory_area": np.where(ind, nonres, 0.0), "storage_area": 0.0, "garage_area": lots.accessory_sqft.to_numpy(),
        "other_area": np.where(com_like, nonres * oth, 0.0),
        "num_bldgs": lots.num_bldgs.to_numpy(), "floors": lots.floors.to_numpy(),
        "units_res": units, "units_total": units, "assess_land": 0.0, "assess_tot": 0.0, "year_built": 0.0,
        "built_far": np.divide(fa, lots.geometry.area.to_numpy(), out=np.zeros(len(lots)), where=lots.geometry.area.to_numpy() > 0),
        "historic": False, "landmark": False,
        "x": pt.x.to_numpy(), "y": pt.y.to_numpy(), "lon": ll.x.to_numpy(), "lat": ll.y.to_numpy(),
        "height_m": lots.height_m.to_numpy(), "use_confidence": conf.astype("int8"),
        "census_block": blocks.GEOID.to_numpy()[blk],
    })
    # No zoning: context FAR (90th percentile of built FAR among built lots in the census block group) stands in
    # for permitted FAR, and every use is allowed. Flagged as missing zoning in the UI.
    bg = df.census_block.str[:12]
    ctx = df[df.bldg_area > 0].groupby(bg[df.bldg_area > 0]).built_far.quantile(0.9)
    df["max_far"] = np.maximum(bg.map(ctx).fillna(df.built_far.quantile(0.9)).to_numpy(), df.built_far.to_numpy())
    df["resid_far"] = df["comm_far"] = df["facil_far"] = df["max_far"]
    df["allowed"] = ALL_USES
    df["cd"] = _districts(df, blocks, blk)

    pph = float(blocks.POP100.sum() / max(blocks.HU100.sum(), 1))
    meta = finish_twin(df, lots.geometry.values, crs, out, pl["state"], pph, jobs_block, blk, log, {
        "city": pl["label"], "geoid": geoid, "tier": "A",
        "source": f"Tier A: Census 2020 blocks, LODES {census.LODES_YEAR}, Overture Maps {overture.RELEASE}",
        "data_quality": {"missing_land_use": int((df.use < 0).sum()), "pseudo_lots": True,
                         "height_observed_share": round(float(b.height_obs.mean()), 3),
                         "land_use_method": land_use_method,
                         "use_confidence": {str(c): int((conf == c).sum()) for c in (0, 1, 2, 3)},
                         "housing_units_unallocated": round(unalloc, 1), "jobs_lodes": int(round(jobs_block.sum()))},
        "columns": {"lot boundaries": "estimated (building cells within census blocks)",
                    "floor area": (f"estimated (footprint x floors from height, divided by {fa_corr:.2f}, the median "
                                   f"Tier A/Tier B ratio in {', '.join(fa_cities)})" if fa_cities else
                                   "estimated (footprint x floors from height)"),
                    "land use": ("estimated (model trained on Tier B cities; rules for lots without buildings)"
                                 if land_use_method == "model" else "estimated (rules)"),
                    "homes": "observed by block (Census 2020), allocated to lots", "jobs": "observed by block (LODES), modelled by floor area",
                    "assessed value": "missing", "zoning": "missing (context FAR, all uses allowed)",
                    "year built": "missing", "landmarks and historic districts": "missing"},
        "missing_indicators": ["value"], "zoning_rules": "none (Tier A)",
        "levels": {str(d): f"Area {d}" for d in sorted(df.cd.unique())},
    }, t0=t0)
    if not area:
        register(geoid, pl["label"], "A", meta)
    log(f"done: {len(df):,} lots")
    return meta


def _round_by_block(x: np.ndarray, blk: np.ndarray) -> np.ndarray:
    """Integer units whose block sums equal the rounded block totals (largest remainder)."""
    out = np.floor(x)
    rem = x - out
    target = pd.Series(x).groupby(blk).sum().round()
    short = (target - pd.Series(out).groupby(blk).sum()).astype(int)
    order = pd.DataFrame({"b": blk, "r": rem}).sort_values("r", ascending=False)
    order["rank"] = order.groupby("b").cumcount()
    add = order[order["rank"] < order.b.map(short)].index
    out[add] += 1
    return out


def _districts(df: pd.DataFrame, blocks: gpd.GeoDataFrame, blk: np.ndarray) -> np.ndarray:
    """Planning areas: census tracts grouped by k-means on their centroids, about 75,000 residents each (1-15)."""
    from scipy.cluster.vq import kmeans2

    tract = blocks.GEOID.str[:11]
    t = pd.DataFrame({"tract": tract, "x": blocks.geometry.centroid.x, "y": blocks.geometry.centroid.y,
                      "pop": blocks.POP100}).groupby("tract").agg(x=("x", "mean"), y=("y", "mean"), pop=("pop", "sum"))
    k = int(np.clip(round(t["pop"].sum() / 75000), 1, 15))
    k = min(k, len(t))
    if k == 1:
        lab = np.zeros(len(t), int)
    else:
        _, lab = kmeans2(t[["x", "y"]].to_numpy(), k, seed=7, minit="++")
    code = dict(zip(t.index, lab + 1))
    return tract.map(code).to_numpy()[blk].astype("int32")


if __name__ == "__main__":
    m = build_city(" ".join(sys.argv[1:]) or "Wauwatosa, WI")
    print(json.dumps({k: m[k] for k in ("city", "geoid", "n_parcels", "use_counts", "data_quality", "build_seconds")}, indent=1))
