"""City adapters and their shared helpers, on synthetic data or small cached inputs (no downloads)."""
import geopandas as gpd
import numpy as np
import pytest

from planarena.cities.common import local_crs, plausible_floor_area, round_by_block


def test_the_ten_cities():
    from planarena.cities.build import CITIES, resolve

    assert len(CITIES) == 10 and resolve("Milwaukee") == "5553000" and resolve("dallas, tx") == "4819000"
    assert "0668000" not in CITIES  # San Jose was replaced by Milwaukee
    with pytest.raises(SystemExit):
        resolve("Wauwatosa")


def test_units_keep_block_totals():
    x = np.array([0.4, 0.4, 0.4, 2.6, 0.2, 0.0])
    blk = np.array([0, 0, 0, 1, 1, 2])
    out = round_by_block(x, blk)
    assert np.allclose(out, np.round(out))
    assert out[:3].sum() == 1 and out[3:5].sum() == 3 and out[5] == 0


def test_local_projection_is_in_us_feet():
    crs = local_crs(43.05, -88.0)
    pts = gpd.GeoSeries.from_xy([-88.0, -88.0], [43.05, 43.05 + 1 / 111.0], crs=4326).to_crs(crs)
    assert 3260 < pts.iloc[0].distance(pts.iloc[1]) < 3310  # 1/111 degree of latitude is about 1.0 km = 3,281 ft


def test_implausible_floor_area_is_dropped():
    fa, n = plausible_floor_area(np.array([268_563_964.0, 50_000.0]), np.array([26_524.0, 10_000.0]))
    assert n == 1 and fa[0] == 0 and fa[1] == 50_000


def test_energy_factors_read_from_the_epa_hub():
    from planarena.national import energy
    from planarena.national.common import NATIONAL

    if not (NATIONAL / "energy" / "ghg-emission-factors-hub-2025.xlsx").exists():
        pytest.skip("EPA hub not downloaded")
    f = energy.fuel_factors()
    assert f["_detail"]["kg_co2_g_ch4_g_n2o_per_mmbtu"]["natural_gas"] == [53.06, 1.0, 0.1]
    assert 5.3e-5 < f["natural_gas"] < 5.33e-5  # t CO2e per kBtu


def test_philadelphia_uses_and_zoning():
    from planarena.cities.adapters.philadelphia import allowed, use_of
    from planarena.config import USE_INDEX as U

    assert use_of("1", "ROW PORCH FRONT") == "res" and use_of("3", "ROW MIXED-COM/RES-BLT AS RES") == "mix"
    assert use_of("4", "SCHOOL") == "pub" and use_of("4", "PARKING GARAGE/DECK") == "prk" and use_of("6", None) == "vac"
    assert use_of(None, float("nan")) == "unknown"
    assert not (allowed("RSA5") >> U["ind"]) & 1 and (allowed("ICMX") >> U["ind"]) & 1
    assert (allowed("SPPOA") >> U["opn"]) & 1 and not (allowed("SPPOA") >> U["res"]) & 1


def test_milwaukee_land_use_groups():
    from planarena.cities.adapters.milwaukee import group_of

    assert group_of(8810) == 1 and group_of(8820) == 2 and group_of(8830) == 3 and group_of(8899) == 4
    assert group_of(5812) == 5 and group_of(4225) == 8 and group_of(6553) == 12 and group_of(8880) == 13
    assert group_of(7523) == 6 and group_of(0) == 0
