"""ArcGIS Urban export: every reference between the files resolves, as Urban's import requires."""
import json

import geopandas as gpd
import pandas as pd
import pytest

from planarena.cities.registry import city_dir
from planarena.integrations import urban_export


@pytest.mark.skipif(not (city_dir("5553000") / "parcels.parquet").exists(), reason="Milwaukee twin not built")
def test_milwaukee_district_export_is_consistent(tmp_path):
    p = pd.read_parquet(city_dir("5553000") / "parcels.parquet", columns=["bbl", "cd"])
    d = str(p.cd.value_counts().index[-1])  # the smallest district keeps the test quick
    first = p[p.cd.astype(str) == d].bbl.iloc[0]
    plan = tmp_path / "plan.csv"
    plan.write_text(f"i,bbl,address,current_use,land_use,far\n0,{first},,res,mix,2.5\n")
    out = urban_export.export("Milwaukee", tmp_path / "urban", district=d, plan=plan)
    space = pd.read_csv(out / "space_use_types.csv")
    assert list(space.CustomID) == ["res", "mix", "com", "ind", "tra", "pub", "opn", "prk", "vac"]
    zt = pd.read_csv(out / "zoning_types.csv")
    assert zt.CustomID.is_unique
    for allowed in zt.AllowedSpaceUseTypes:
        assert set(json.loads(allowed)) <= set(space.CustomID)  # zoning types refer to space-use Custom IDs
    lots = gpd.read_file(out / "parcels.geojson")
    assert lots.crs.to_epsg() == 4326 and lots.CustomID.is_unique and len(lots) == (p.cd.astype(str) == d).sum()
    zones = gpd.read_file(out / "zoning.geojson")
    assert set(zones.ZoningType) <= set(zt.CustomID) and zones.geometry.is_valid.all()
    assert lots.Changed.sum() == 1 and lots.loc[lots.Changed, "ScenarioUse"].iloc[0] == "mix"
    assert not (out / "land_use.geojson").exists()  # Milwaukee has no plan layer: nothing is invented
