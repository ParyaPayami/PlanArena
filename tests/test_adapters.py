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


def test_philadelphia_zoning_families():
    from planarena.cities.adapters.philadelphia import allowed
    from planarena.config import USE_INDEX as U

    assert not (allowed("RSA5") >> U["ind"]) & 1 and (allowed("ICMX") >> U["ind"]) & 1
    assert (allowed("SPPOA") >> U["opn"]) & 1 and not (allowed("SPPOA") >> U["res"]) & 1


def test_crosswalks():
    from planarena.sources.crosswalk import milwaukee, nyc, philadelphia
    from planarena.taxonomy import KEYS

    # New York: MapPLUTO land use refined by building class and units
    assert nyc("01", "A1", 1) == "sf" and nyc("01", "B2", 2) == "mf_small" and nyc("02", "C1", 12) == "mf"
    assert nyc("05", "O4", 0) == "off" and nyc("05", "H2", 0) == "hot" and nyc("06", "E1", 0) == "whs"
    assert nyc("08", "W1", 0) == "edu" and nyc("08", "I1", 0) == "hlt" and nyc("08", "M1", 0) == "civ"
    assert nyc(None, None, None) == "unknown" and nyc("11", float("nan"), 0) == "vac"
    # Milwaukee: MPROP group refined by the SIC-style code
    assert milwaukee("8810", "1", "1") == "sf" and milwaukee("8830", "3", "12") == "mf" and milwaukee("5812", "5", "0") == "ret"
    assert milwaukee("5093", "5", "0") == "whs" and milwaukee("8062", "6", "0") == "hlt" and milwaukee("7523", "9", "0") == "prk"
    assert milwaukee("8211", "11", "0") == "edu" and milwaukee("6553", "12", "0") == "opn" and milwaukee("0", "0", "0") == "unknown"
    # Philadelphia: three-digit code where present, two-digit otherwise, OPA category splits homes
    assert philadelphia(12, None, 1) == "sf" and philadelphia(12, None, 2) == "mf_small" and philadelphia(12, None, 14) == "mf"
    assert philadelphia(31, 317) == "whs" and philadelphia(41, 413) == "edu" and philadelphia(51, 514) == "prk"
    assert philadelphia(41, None, 4, "SCHOOL") == "edu" and philadelphia(41, None, 4, "HOSPITAL") == "hlt"
    assert philadelphia(41, None, 4, "RELIGIOUS") == "civ" and philadelphia(31, None, 5, "WAREHOUSE") == "whs"
    assert philadelphia(None, None) == "unknown" and philadelphia(92, None) == "unknown" and philadelphia(91, None) == "vac"
    for key in ("sf", "mf", "whs", "edu", "prk", "vac"):
        assert key in KEYS


def test_milwaukee_land_use_groups():
    from planarena.cities.adapters.milwaukee import group_of

    assert group_of(8810) == 1 and group_of(8820) == 2 and group_of(8830) == 3 and group_of(8899) == 4
    assert group_of(5812) == 5 and group_of(4225) == 8 and group_of(6553) == 12 and group_of(8880) == 13
    assert group_of(7523) == 6 and group_of(0) == 0


def test_scag_crosswalk_covers_the_code_list():
    from planarena.sources.crosswalk import SCAG, SCAG_GENERIC_MF, SCAG_UNKNOWN, scag
    from planarena.taxonomy import KEYS

    # every code of the SCAG 2020 Annual Land Use code list (136 codes) is classed, or unknown on purpose
    codes = set(SCAG) | set(SCAG_GENERIC_MF) | set(SCAG_UNKNOWN) | {"1100"}
    assert len(codes) == 136 and all(v in KEYS for v in SCAG.values())
    assert all(scag(c) != "unknown" for c in codes - set(SCAG_UNKNOWN))
    assert scag("1110") == "sf" and scag("1110", 48) == "mf" and scag("1122") == "mf_small"
    assert scag("1120", 3) == "mf_small" and scag("1120", 40) == "mf" and scag("1120") == "mf"
    assert scag("1233") == "hot" and scag("1244") == "hlt" and scag("1247") == "prk" and scag("1340") == "whs"
    assert scag("1700") == "vac" and scag("1820") == "opn" and scag("1620") == "mix" and scag("1413") == "tra"
    assert scag("7777") == "unknown" and scag("7777", specific_plan="1600") == "mix" and scag(None) == "unknown"


def test_los_angeles_zone_families():
    from planarena.cities.adapters.losangeles import ALL, allowed
    from planarena.config import USE_INDEX as U

    on = lambda z, k: bool((allowed(z) >> U[k]) & 1)
    assert on("R1", "res") and not on("R1", "com") and on("C2", "res") and on("C2", "com") and not on("C2", "ind")
    assert on("M2", "ind") and not on("M2", "res") and on("RAS3", "com") and on("P", "prk") and not on("P", "res")
    assert allowed("PVSP") == ALL and allowed("DOWNTOWN") == ALL  # specific plans are not screened


def test_los_angeles_plan_and_zone_classes():
    from planarena.sources.crosswalk import los_angeles_plan, los_angeles_zone

    # residential designations by the city's density category; everything else by SCAG's translation
    assert los_angeles_plan("Low Medium II Residential", "1120") == "mf_small"
    assert los_angeles_plan("Medium Residential", "1120") == "mf" and los_angeles_plan("Low Residential", "1110") == "sf"
    assert los_angeles_plan("Community Commercial", "1220") == "ret" and los_angeles_plan(None, "1240") == "civ"
    assert los_angeles_zone("RD1.5", "1123") == "mf_small" and los_angeles_zone("R3", "1123") == "mf"
    assert los_angeles_zone("RE11", "1111") == "sf" and los_angeles_zone("RAS4", "1600") == "mf"
    assert los_angeles_zone("C2", "1220") == "ret" and los_angeles_zone("PVSP", "7777", "1600") == "mix"
