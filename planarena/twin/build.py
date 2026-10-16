"""Build the PlanArena digital twin of a city from MapPLUTO.

Outputs (data/processed):
  parcels.parquet      one row per tax lot: attributes, land-use class, zoning mask, grid cell
  parcels.geoparquet   projected geometry, for analysis
  graph.npz            parcel graph: adjacency, k-nearest-neighbour and same-zoning relations
  twin_meta.json       grid, extent, provenance
Outputs (web/public/data):
  parcels.geojson      simplified WGS84 polygons for the map (i, u, h, cd)
  levels/<cd>.geojson  one file per community district, for the mobile game

Run with:  python -m planarena.twin.build
"""
from __future__ import annotations

import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely import STRtree

from planarena.config import (
    CITY_NAME, FT_PER_M, PLUTO_PATH, PLUTO_TO_USE, PROCESSED, PROJECTED_CRS,
    UNKNOWN_USE, USE_KEYS, WEB_CRS, WEB_DATA,
)
from planarena.twin.zoning import RULE_SOURCE, allowed_mask

PLUTO_COLS = [
    "BBL", "Address", "CD", "Block", "ZoneDist1", "Overlay1", "SPDist1", "LandUse",
    "BldgClass", "LotArea", "BldgArea", "ResArea", "ComArea", "OfficeArea",
    "RetailArea", "FactryArea", "StrgeArea", "GarageArea", "OtherArea", "NumBldgs",
    "NumFloors", "UnitsRes", "UnitsTotal", "AssessLand", "AssessTot", "YearBuilt",
    "HistDist", "Landmark", "BuiltFAR", "ResidFAR", "CommFAR", "FacilFAR", "Version",
]
FLOOR_HEIGHT_M = 3.5  # assumption: average floor-to-floor height for 3D massing
CELL_M = 50.0  # accessibility raster resolution

CD_NAMES = {
    101: "Financial District & Tribeca", 102: "Greenwich Village & SoHo",
    103: "Lower East Side & Chinatown", 104: "Chelsea & Hell's Kitchen",
    105: "Midtown", 106: "Murray Hill, Gramercy & Stuy Town",
    107: "Upper West Side", 108: "Upper East Side",
    109: "Morningside & Hamilton Heights", 110: "Central Harlem",
    111: "East Harlem", 112: "Washington Heights & Inwood",
}


def load_pluto(path=PLUTO_PATH) -> gpd.GeoDataFrame:
    g = gpd.read_file(path, columns=PLUTO_COLS, engine="pyogrio")
    if g.crs is None or g.crs.to_string() != PROJECTED_CRS:
        g = g.to_crs(PROJECTED_CRS)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)
    g["geometry"] = g.geometry.make_valid()
    return g


def tabulate(g: gpd.GeoDataFrame) -> pd.DataFrame:
    num = lambda c: pd.to_numeric(g[c], errors="coerce").fillna(0).astype("float64")
    pt = g.geometry.representative_point()
    df = pd.DataFrame({
        "bbl": pd.to_numeric(g["BBL"], errors="coerce").astype("int64"),
        "address": g["Address"].fillna(""),
        "cd": pd.to_numeric(g["CD"], errors="coerce").fillna(0).astype("int32"),
        "block": pd.to_numeric(g["Block"], errors="coerce").fillna(0).astype("int32"),
        "zone": g["ZoneDist1"].fillna("NA"),
        "overlay": g["Overlay1"].fillna(""),
        "special": g["SPDist1"].fillna(""),
        "bldg_class": g["BldgClass"].fillna(""),
        "use": g["LandUse"].map(PLUTO_TO_USE).fillna(UNKNOWN_USE).astype("int16"),
        "lot_area": num("LotArea"), "bldg_area": num("BldgArea"),
        "res_area": num("ResArea"), "com_area": num("ComArea"),
        "office_area": num("OfficeArea"), "retail_area": num("RetailArea"),
        "factory_area": num("FactryArea"), "storage_area": num("StrgeArea"),
        "garage_area": num("GarageArea"), "other_area": num("OtherArea"),
        "num_bldgs": num("NumBldgs"), "floors": num("NumFloors"),
        "units_res": num("UnitsRes"), "units_total": num("UnitsTotal"),
        "assess_land": num("AssessLand"), "assess_tot": num("AssessTot"),
        "year_built": num("YearBuilt"),
        "built_far": num("BuiltFAR"), "resid_far": num("ResidFAR"),
        "comm_far": num("CommFAR"), "facil_far": num("FacilFAR"),
        "historic": g["HistDist"].notna().to_numpy(),
        "landmark": g["Landmark"].notna().to_numpy(),
        "x": pt.x.to_numpy(), "y": pt.y.to_numpy(),
    })
    # Lots with no recorded area still need a footprint for indicators.
    poly_area = g.geometry.area.to_numpy()
    df.loc[df.lot_area <= 0, "lot_area"] = poly_area[df.lot_area <= 0]
    df["max_far"] = df[["resid_far", "comm_far", "facil_far"]].max(axis=1)
    df["allowed"] = [allowed_mask(z, o) for z, o in zip(df.zone, df.overlay)]
    df["height_m"] = (df.floors * FLOOR_HEIGHT_M).clip(lower=0)
    ll = gpd.GeoSeries(pt, crs=PROJECTED_CRS).to_crs(WEB_CRS)
    df["lon"], df["lat"] = ll.x.to_numpy(), ll.y.to_numpy()
    return df


def add_grid(df: pd.DataFrame, cell_m: float = CELL_M) -> dict:
    cell_ft = cell_m * FT_PER_M
    x0, y0 = df.x.min() - cell_ft, df.y.min() - cell_ft
    df["cx"] = ((df.x - x0) // cell_ft).astype("int32")
    df["cy"] = ((df.y - y0) // cell_ft).astype("int32")
    return {"cell_m": cell_m, "cell_ft": cell_ft, "x0": x0, "y0": y0,
            "nx": int(df.cx.max()) + 2, "ny": int(df.cy.max()) + 2}


def build_graph(g: gpd.GeoDataFrame, df: pd.DataFrame, k: int = 8) -> dict[str, np.ndarray]:
    """Three relations: physical adjacency, spatial kNN, and kNN within the same zoning district."""
    tree = STRtree(g.geometry.values)
    src, dst = tree.query(g.geometry.values, predicate="dwithin", distance=3.0)
    keep = src != dst
    adj = np.vstack([src[keep], dst[keep]]).astype("int64")

    xy = df[["x", "y"]].to_numpy()
    _, nn = cKDTree(xy).query(xy, k=k + 1)
    knn = np.vstack([np.repeat(np.arange(len(df)), k), nn[:, 1:].ravel()]).astype("int64")

    zs, zd = [], []
    for _, idx in df.groupby("zone").indices.items():
        if len(idx) < 2:
            continue
        kk = min(4, len(idx) - 1)
        _, nz = cKDTree(xy[idx]).query(xy[idx], k=kk + 1)
        nz = np.atleast_2d(nz)
        zs.append(np.repeat(idx, kk))
        zd.append(idx[nz[:, 1:].ravel()])
    zon = np.vstack([np.concatenate(zs), np.concatenate(zd)]).astype("int64")
    return {"adjacent": adj, "near": knn, "same_zoning": zon}


def write_web(g: gpd.GeoDataFrame, df: pd.DataFrame, web_dir=WEB_DATA) -> None:
    web_dir.mkdir(parents=True, exist_ok=True)
    (web_dir / "levels").mkdir(exist_ok=True)
    w = gpd.GeoDataFrame(
        {"i": np.arange(len(df), dtype="int32"), "u": df.use.to_numpy(),
         "h": df.height_m.round(1).to_numpy(), "cd": df.cd.to_numpy()},
        geometry=g.geometry.simplify(1.5, preserve_topology=True).values,
        crs=PROJECTED_CRS,
    ).to_crs(WEB_CRS)
    opts = {"COORDINATE_PRECISION": 6, "RFC7946": "YES"}
    w.to_file(web_dir / "parcels.geojson", driver="GeoJSON", engine="pyogrio", layer_options=opts)
    for cd, part in w.groupby("cd"):
        if cd in CD_NAMES:
            part.to_file(web_dir / "levels" / f"{cd}.geojson", driver="GeoJSON",
                         engine="pyogrio", layer_options=opts)


def build(out_dir=PROCESSED, web_dir=WEB_DATA) -> dict:
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    g = load_pluto()
    df = tabulate(g)
    grid = add_grid(df)
    graph = build_graph(g, df)
    df.to_parquet(out_dir / "parcels.parquet", index=False)
    gpd.GeoDataFrame({"i": np.arange(len(df))}, geometry=g.geometry.values,
                     crs=PROJECTED_CRS).to_parquet(out_dir / "parcels.geoparquet")
    np.savez_compressed(out_dir / "graph.npz", **graph)
    write_web(g, df, web_dir)
    bounds = gpd.GeoSeries(g.geometry, crs=PROJECTED_CRS).to_crs(WEB_CRS).total_bounds
    meta = {
        "city": CITY_NAME,
        "source": f"NYC DCP MapPLUTO {g['Version'].iloc[0]}",
        "source_path": str(PLUTO_PATH),
        "n_parcels": int(len(df)),
        "use_counts": {USE_KEYS[u] if u >= 0 else "unknown": int(n)
                       for u, n in df.use.value_counts().sort_index().items()},
        "bbox_wgs84": [float(b) for b in bounds],
        "grid": grid,
        "graph_edges": {k: int(v.shape[1]) for k, v in graph.items()},
        "zoning_rules": RULE_SOURCE,
        "floor_height_m": FLOOR_HEIGHT_M,
        "levels": {str(k): v for k, v in CD_NAMES.items()},
        "build_seconds": round(time.time() - t0, 1),
    }
    (out_dir / "twin_meta.json").write_text(json.dumps(meta, indent=2))
    (web_dir / "twin_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
