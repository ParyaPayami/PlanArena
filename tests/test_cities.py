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
