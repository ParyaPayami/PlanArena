"""Tier A builder pieces on synthetic data (no downloads): pseudo-lots, unit allocation, projection units."""
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import Polygon, box

from planarena.cities.tier_a import _round_by_block, local_crs, tessellate


def _blocks_and_buildings():
    blocks = gpd.GeoDataFrame({"GEOID": ["a", "b", "c"]},
                              geometry=[box(0, 0, 400, 300), box(500, 0, 900, 300), box(0, 400, 400, 700)])
    fp = [box(20, 20, 80, 80), box(150, 20, 220, 90), box(300, 200, 380, 280),  # block a: three buildings
          box(520, 20, 600, 100), box(603, 20, 610, 27),                          # block b: house + shed
          ]
    b = gpd.GeoDataFrame({"block": [0, 0, 0, 1, 1], "accessory": [False, False, False, False, True]}, geometry=fp)
    b["rp"] = b.geometry.representative_point()
    return blocks, b


def test_pseudo_lots_partition_blocks_and_hold_their_buildings():
    blocks, b = _blocks_and_buildings()
    lots = tessellate(blocks, b)
    for bi, blk in enumerate(blocks.geometry):
        mine = lots[lots.block_i == bi]
        assert mine.geometry.area.sum() <= blk.area + 1e-6
        assert shapely.union_all(mine.geometry.values).difference(blk).area < 1e-6
        for a in range(len(mine)):  # no two lots overlap
            for c in range(a + 1, len(mine)):
                assert mine.geometry.iloc[a].intersection(mine.geometry.iloc[c]).area < 1e-6
    main = b[~b.accessory]
    tree = shapely.STRtree(lots[lots.cell].geometry.values)
    assert all(len(tree.query(p, predicate="within")) == 1 for p in main.rp)  # each building in exactly one lot
    assert int((lots.block_i == 2).sum()) == 1 and not lots[lots.block_i == 2].cell.any()  # empty block = one open lot
    assert int(lots[lots.block_i == 1].cell.sum()) == 1  # the shed does not get a lot of its own


def test_units_keep_block_totals():
    x = np.array([0.4, 0.4, 0.4, 2.6, 0.2, 0.0])
    blk = np.array([0, 0, 0, 1, 1, 2])
    out = _round_by_block(x, blk)
    assert np.allclose(out, np.round(out))
    assert out[:3].sum() == 1 and out[3:5].sum() == 3 and out[5] == 0


def test_local_projection_is_in_us_feet():
    crs = local_crs(43.05, -88.0)
    pts = gpd.GeoSeries.from_xy([-88.0, -88.0], [43.05, 43.05 + 1 / 111.0], crs=4326).to_crs(crs)
    d = pts.iloc[0].distance(pts.iloc[1])
    assert 3260 < d < 3310  # 1/111 degree of latitude is about 1.0 km = 3,281 ft


def test_energy_factors_read_from_the_epa_hub():
    from planarena.national.common import NATIONAL
    from planarena.national import energy

    if not (NATIONAL / "energy" / "ghg-emission-factors-hub-2025.xlsx").exists():
        pytest.skip("EPA hub not downloaded")
    f = energy.fuel_factors()
    assert f["_detail"]["kg_co2_g_ch4_g_n2o_per_mmbtu"]["natural_gas"] == [53.06, 1.0, 0.1]
    assert 5.3e-5 < f["natural_gas"] < 5.33e-5  # t CO2e per kBtu


def test_massachusetts_use_codes():
    from planarena.cities.adapters.massgis import use_of

    cases = {("101", "Single Family Residential"): "res", ("102", "Residential Condominium"): "res",
             ("013", "Mixed Use (Primarily Residential, some Commercial)"): "mix",
             ("031", "Mixed Use (Primarily Commercial, some Residential)"): "mix",
             ("340", "General Office Buildings"): "com", ("337", "Parking Lots"): "prk",
             ("316", "Other Storage, Warehouse, and Distribution facilities"): "ind",
             ("130", "Developable Residential Land"): "vac", ("942", "College or University"): "pub",
             ("9705", "Housing Authority"): "res", ("960", "Church, Mosque, Synagogue, Temple, etc..."): "pub",
             ("9100", "Dept. of Conservation and Recreation (DCR), Division of State Parks and Recreation"): "opn",
             ("930", "Vacant, Selectmen or City Council (Municipal)"): "vac", ("423", "Electric utility"): "tra",
             ("", ""): "unknown"}
    for (code, desc), want in cases.items():
        assert use_of(code, desc) == want, (code, desc)


def test_florida_use_codes():
    from planarena.cities.adapters.florida import use_of

    cases = {"001": "res", "004": "res", "003": "res", "000": "vac", "012": "mix", "017": "com", "039": "com",
             "028": "prk", "048": "ind", "041": "ind", "071": "pub", "083": "pub", "082": "opn", "060": "opn",
             "091": "tra", "094": "tra", "099": "vac", "": "unknown", None: "unknown"}
    for code, want in cases.items():
        assert use_of(code) == want, code


def test_implausible_floor_area_is_dropped():
    import numpy as np

    from planarena.cities.common import plausible_floor_area

    fa, n = plausible_floor_area(np.array([268_563_964.0, 50_000.0]), np.array([26_524.0, 10_000.0]))
    assert n == 1 and fa[0] == 0 and fa[1] == 50_000
