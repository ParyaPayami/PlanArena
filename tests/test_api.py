"""API smoke tests using FastAPI's TestClient."""
import io

import pytest
from fastapi.testclient import TestClient

from planarena.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_and_meta(client):
    assert client.get("/api/health").json()["ok"]
    meta = client.get("/api/meta").json()
    assert meta["n_parcels"] > 40000
    assert len(meta["land_uses"]) == 9
    assert len(meta["stakeholders"]) == 5


def test_evaluate_and_bad_input(client):
    r = client.post("/api/evaluate", json={"changes": {"10": "opn"}, "scope": "affected"})
    assert r.status_code == 200 and r.json()["n_changed"] == 1
    assert client.post("/api/evaluate", json={"changes": {"10": "castle"}}).status_code == 400
    assert client.post("/api/evaluate", json={"changes": {"99999999": "res"}}).status_code == 400


def test_parcel_detail(client):
    p = client.get("/api/parcel/0").json()
    assert "allowed_uses" in p and "per_use" in p


def test_suggest(client):
    r = client.post("/api/suggest", json={"scope": "cd:103", "mode": "balanced", "max_change_share": 0.03}).json()
    assert len(r["changes"]) > 0
    assert r["evaluation"]["overall"] > 0


def test_upload_csv_round_trip(client):
    sample = client.get("/api/sample-plan.csv").text
    files = {"file": ("plan.csv", io.BytesIO(sample.encode()), "text/csv")}
    r = client.post("/api/upload", files=files).json()
    assert r["upload"]["matched"] == r["upload"]["rows"] > 0
    assert r["n_changed"] == r["upload"]["matched"]


def test_upload_rejects_unknown_format(client):
    files = {"file": ("plan.xlsx", io.BytesIO(b"x"), "application/octet-stream")}
    assert client.post("/api/upload", files=files).status_code == 400
