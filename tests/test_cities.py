"""Cities beyond Manhattan: the API serves the built cities, and studies stay with their city.

Uses Milwaukee if it is built locally (python -I -m planarena.cities.build Milwaukee); skipped otherwise.
"""
import pytest
from fastapi.testclient import TestClient

from planarena.api import store
from planarena.api.app import app
from planarena.cities import registry

CITY = "5553000"  # Milwaukee, WI


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    store.DB = tmp_path_factory.mktemp("db") / "cities.sqlite3"
    return TestClient(app)


def test_unknown_city_is_rejected(client):
    assert client.get("/api/meta", headers={"X-PlanArena-City": "9999999"}).status_code == 404


def test_manhattan_is_the_default_city_and_the_ten_cities_are_listed(client):
    m = client.get("/api/meta").json()
    assert m["city_id"] == registry.DEFAULT
    listed = client.get("/api/cities").json()
    assert listed[0]["id"] == registry.DEFAULT and len(listed) == 11
    assert {c["label"] for c in listed} >= {"Chicago, IL", "Milwaukee, WI", "Dallas, TX"}


@pytest.mark.skipif(not registry.exists(CITY), reason="Milwaukee not built")
def test_a_city_evaluates_and_serves_its_layers(client):
    h = {"X-PlanArena-City": CITY}
    m = client.get("/api/meta", headers=h).json()
    assert m["n_parcels"] > 100_000 and m["map"] == "tiles"
    base = m["baseline_city"]
    assert base["homes"] > 0 and base["jobs"] > 0 and base["ghg"] > 0
    ev = client.post("/api/evaluate", json={"changes": {"0": "opn"}}, headers=h).json()
    assert ev["n_changed"] == 1
    level = next(iter(m["levels"]))
    assert client.get(f"/city-data/{CITY}/levels/{level}.geojson").status_code == 200
    r = client.get(f"/city-data/{CITY}/..%2Fcalibrated.yaml")
    assert r.status_code == 404 and "jobs_sqft_per_worker" not in r.text


@pytest.mark.skipif(not registry.exists(CITY), reason="Milwaukee not built")
def test_studies_stay_with_their_city(client):
    h = {"X-PlanArena-City": CITY}
    s = client.post("/api/scenarios", json={"name": "Milwaukee study", "changes": {"1": "opn"}}, headers=h).json()
    assert any(x["id"] == s["id"] for x in client.get("/api/scenarios", headers=h).json())
    assert not any(x["id"] == s["id"] for x in client.get("/api/scenarios").json())
    assert client.get(f"/api/scenarios/{s['id']}").status_code == 404


@pytest.mark.skipif(not registry.exists(CITY), reason="Milwaukee not built")
def test_vector_tiles_and_points(client, tmp_path):
    import math

    import mapbox_vector_tile

    from planarena.cities.tiles import TileSource

    h = {"X-PlanArena-City": CITY}
    m = client.get("/api/meta", headers=h).json()
    n = m["n_parcels"]
    assert len(client.get("/api/points", headers=h).content) == 16 * n
    src = TileSource(registry.city_dir(CITY), tmp_path)
    lon, lat = (m["bbox"][0] + m["bbox"][2]) / 2, (m["bbox"][1] + m["bbox"][3]) / 2
    z = 14
    x = int((lon + 180) / 360 * 2 ** z)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** z)
    t = mapbox_vector_tile.decode(src.tile(z, x, y))
    feats = t["parcels"]["features"]
    assert feats and all(0 <= f["properties"]["i"] < n for f in feats)
    assert (tmp_path / str(z) / str(x) / f"{y}.pbf").exists()  # cached
    assert client.get(f"/city-tiles/{CITY}/3/0/0.pbf").status_code == 404  # outside the served zooms
