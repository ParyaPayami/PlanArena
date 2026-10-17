"""Cities beyond Manhattan: the API serves any built city, and studies stay with their city.

Uses a Tier A city already built locally (python -I -m planarena.cities.tier_a "Wauwatosa, WI"); skipped otherwise.
"""
import pytest
from fastapi.testclient import TestClient

from planarena.api import store
from planarena.api.app import app
from planarena.cities import registry

TIER_A = "5584675"  # Wauwatosa, WI


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    store.DB = tmp_path_factory.mktemp("db") / "cities.sqlite3"
    return TestClient(app)


def test_unknown_city_is_rejected(client):
    assert client.get("/api/meta", headers={"X-PlanArena-City": "9999999"}).status_code == 404


def test_manhattan_is_the_default_city(client):
    m = client.get("/api/meta").json()
    assert m["city_id"] == registry.DEFAULT and m["tier"] == "B"
    assert any(c["id"] == registry.DEFAULT for c in client.get("/api/cities").json())


@pytest.mark.skipif(not registry.exists(TIER_A), reason="Tier A test city not built")
def test_tier_a_city_evaluates_and_flags_missing_data(client):
    h = {"X-PlanArena-City": TIER_A}
    m = client.get("/api/meta", headers=h).json()
    assert m["tier"] == "A" and m["n_parcels"] > 1000
    assert "value" in m["missing_indicators"] and m["columns"]["zoning"].startswith("missing")
    base = m["baseline_city"]
    assert base["homes"] > 0 and base["jobs"] > 0 and base["ghg"] > 0
    ev = client.post("/api/evaluate", json={"changes": {"0": "opn"}}, headers=h).json()
    assert ev["n_changed"] == 1
    assert client.get(f"/city-data/{TIER_A}/parcels.geojson").status_code == 200
    r = client.get(f"/city-data/{TIER_A}/..%2Fcalibrated.yaml")
    assert r.status_code == 404 and "jobs_sqft_per_worker" not in r.text


@pytest.mark.skipif(not registry.exists(TIER_A), reason="Tier A test city not built")
def test_studies_stay_with_their_city(client):
    h = {"X-PlanArena-City": TIER_A}
    s = client.post("/api/scenarios", json={"name": "Wauwatosa study", "changes": {"1": "opn"}}, headers=h).json()
    assert any(x["id"] == s["id"] for x in client.get("/api/scenarios", headers=h).json())
    assert not any(x["id"] == s["id"] for x in client.get("/api/scenarios").json())
    assert client.get(f"/api/scenarios/{s['id']}").status_code == 404


TIER_B_MA = "2501711000"  # Cambridge, MA


@pytest.mark.skipif(not registry.exists(TIER_B_MA), reason="Cambridge not built")
def test_vector_tiles_and_points(client, tmp_path):
    import math

    import mapbox_vector_tile

    from planarena.cities.tiles import TileSource

    h = {"X-PlanArena-City": TIER_B_MA}
    m = client.get("/api/meta", headers=h).json()
    n = m["n_parcels"]
    assert len(client.get("/api/points", headers=h).content) == 16 * n
    src = TileSource(registry.city_dir(TIER_B_MA), tmp_path)
    lon, lat = (m["bbox"][0] + m["bbox"][2]) / 2, (m["bbox"][1] + m["bbox"][3]) / 2
    z = 14
    x = int((lon + 180) / 360 * 2 ** z)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** z)
    t = mapbox_vector_tile.decode(src.tile(z, x, y))
    feats = t["parcels"]["features"]
    assert feats and all(0 <= f["properties"]["i"] < n for f in feats)
    assert (tmp_path / str(z) / str(x) / f"{y}.pbf").exists()  # cached
    assert client.get(f"/city-tiles/{TIER_B_MA}/3/0/0.pbf").status_code == 404  # outside the served zooms
