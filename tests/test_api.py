"""API tests using FastAPI's TestClient. A temporary SQLite database is used."""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from planarena.api import store
from planarena.api.app import app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    store.DB = tmp_path_factory.mktemp("db") / "test.sqlite3"
    return TestClient(app)


def test_health_and_meta(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["audit"]["valid"] and len(h["source_sha256"]) == 64
    meta = client.get("/api/meta").json()
    assert meta["n_parcels"] > 40000 and len(meta["land_uses"]) == 9 and len(meta["stakeholders"]) == 5
    assert "coefficients" in meta and meta["capacity_city"]["zoning_capacity_sqft"] > 0


def test_evaluate_with_far_and_ranges(client):
    r = client.post("/api/evaluate", json={"changes": {"10": {"use": "res", "far": 6}}}).json()
    assert r["n_changed"] == 1
    homes = next(x for x in r["indicators"] if x["key"] == "homes")
    assert homes["range"][0] <= homes["delta"] <= homes["range"][1]
    assert "capacity" in r


def test_evaluate_rejects_bad_input(client):
    assert client.post("/api/evaluate", json={"changes": {"10": "castle"}}).status_code == 400
    assert client.post("/api/evaluate", json={"changes": {"99999999": "res"}}).status_code == 400
    assert client.post("/api/evaluate", json={"changes": {"10": {"use": "res", "far": 99}}}).status_code == 400
    assert client.post("/api/evaluate", json={"changes": {}, "unexpected": 1}).status_code == 422


def test_parcel_search_block(client):
    p = client.get("/api/parcel/0").json()
    assert "allowed_uses" in p and "max_far" in p
    hits = client.get("/api/search", params={"q": str(p["bbl"])[:6]}).json()
    assert hits and all(str(h["bbl"]).startswith(str(p["bbl"])[:6]) for h in hits)
    b = client.get("/api/block/0").json()
    assert 0 in b["parcels"]


def test_suggest_and_pareto(client):
    r = client.post("/api/suggest", json={"scope": "cd:103", "mode": "balanced", "max_change_share": 0.03}).json()
    assert len(r["changes"]) > 0 and r["evaluation"]["overall"] > 0
    blk = client.get("/api/block/100").json()["parcels"][:40]
    pr = client.post("/api/pareto", json={"parcels": blk, "generations": 20, "seed": 3}).json()
    assert "front" in pr
    pr2 = client.post("/api/pareto", json={"parcels": blk, "generations": 20, "seed": 3}).json()
    assert [f["changes"] for f in pr["front"]] == [f["changes"] for f in pr2["front"]]


def test_import_review_csv_and_round_trip(client):
    sample = client.get("/api/sample-plan.csv").text
    rev = client.post("/api/import", files={"file": ("plan.csv", io.BytesIO(sample.encode()), "text/csv")}).json()
    assert rev["valid_changes"] == rev["rows"] > 0 and rev["unmatched"] == 0
    bad = "bbl,land_use,far\n1,res,2\n" + sample.splitlines()[1] + "\n" + sample.splitlines()[1] + "\n" \
          + sample.splitlines()[2].replace(",res,", ",castle,") + "\n"
    rev2 = client.post("/api/import", files={"file": ("bad.csv", io.BytesIO(bad.encode()), "text/csv")}).json()
    assert rev2["unmatched"] == 1 and rev2["duplicates"] == 1 and rev2["unknown_uses"] == 1
    csv_text = client.post("/api/export/csv", json={"changes": rev["changes"]}).text
    rev3 = client.post("/api/import", files={"file": ("rt.csv", io.BytesIO(csv_text.encode()), "text/csv")}).json()
    assert rev3["changes"] == rev["changes"]


def test_import_rejects_unsafe_zip(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../evil.shp", b"x")
    r = client.post("/api/import", files={"file": ("plan.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 422
    assert client.post("/api/import", files={"file": ("plan.xlsx", b"x", "application/octet-stream")}).status_code == 422


def test_exports_and_report(client):
    ch = {"10": "opn", "11": {"use": "res", "far": 5}}
    gj = json.loads(client.post("/api/export/geojson", json={"changes": ch}).text)
    assert len(gj["features"]) == 2 and gj["features"][0]["geometry"]
    x, y = gj["features"][0]["geometry"]["coordinates"][0][0][:2] if gj["features"][0]["geometry"]["type"] == "Polygon" \
        else gj["features"][0]["geometry"]["coordinates"][0][0][0][:2]
    assert -74.1 < x < -73.9 and 40.6 < y < 40.9  # RFC 7946: longitude/latitude
    prov = json.loads(client.post("/api/export/provenance", json={"changes": ch}).text)
    assert len(prov["source"]["sha256"]) == 64 and prov["evaluation"]["n_changed"] == 2
    html = client.post("/api/report", json={"changes": ch, "title": "Test study"}).text
    assert "Test study" in html and "Development capacity" in html


def test_radius(client):
    r = client.post("/api/radius", json={"parcels": [100], "feet": 300}).json()
    assert r["count"] > 0 and all(p["i"] != 100 for p in r["parcels"])


def test_scenarios_and_tamper_evident_audit(client):
    s = client.post("/api/scenarios", json={"name": "Study A", "changes": {"10": "opn"}}).json()
    assert s["status"] == "draft" and s["summary"]["n_changed"] == 1
    s2 = client.patch(f"/api/scenarios/{s['id']}", json={"status": "under review"}).json()
    assert s2["status"] == "under review"
    assert client.patch(f"/api/scenarios/{s['id']}", json={"status": "approved-ish"}).status_code == 422
    hist = client.get(f"/api/scenarios/{s['id']}/history").json()
    assert [h["action"] for h in hist] == ["scenario_created", "scenario_updated"]
    a = client.get("/api/audit").json()
    assert a["verify"]["valid"]
    with store.connect() as db:  # tamper with a past row; verification must detect it
        db.execute("UPDATE audit SET body = '{}' WHERE id = (SELECT MIN(id) FROM audit)")
    assert client.get("/api/audit").json()["verify"]["valid"] is False
    assert client.delete(f"/api/scenarios/{s['id']}").status_code == 200


def test_vote_with_explicit_plans(client):
    base = client.post("/api/suggest", json={"scope": "cd:105", "mode": "balanced", "max_change_share": 0.03}).json()
    r = client.post("/api/vote", json={
        "scope": "cd:105", "samples": 10, "residents": False,
        "plans": {"ai": {"title": "AI plan", "changes": base["changes"]}},
        "seats": {"developer": 2, "residents": 1, "environment": 1, "city": 1, "business": 1},
    })
    assert r.status_code == 200, r.text
    v = r.json()
    assert [c["id"] for c in v["candidates"]] == ["status-quo", "ai"]
    assert v["decision"]["plan"] in ("status-quo", "ai")
    assert client.post("/api/vote", json={"seats": {"mayor": 1}}).status_code == 400


def test_report_includes_vote_summary(client):
    vote = {"decision": {"title": "Balanced", "rule": "Schulze", "explanation": ["It wins <b>4</b> of 9 rules."]},
            "n_candidates": 3, "rules": {"Schulze": "Balanced"}}
    html = client.post("/api/report", json={"changes": {"10": "res"}, "title": "T", "vote": vote}).text
    assert "Stakeholder vote" in html and "&lt;b&gt;4&lt;/b&gt;" in html  # escaped, never raw HTML


def test_rezoning_test_screens_sites(client):
    blk = client.get("/api/block/2000").json()["parcels"]
    changes = {str(i): {"use": "mix", "far": 10.0} for i in blk}
    r = client.post("/api/rezoning-test", json={"changes": changes})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["rezoned_parcels"] == len(blk) and v["n_sites"] == len(v["sites"])
    assert set(v["sites"]) <= set(blk) and v["homes_increment_at_utilisation"] <= v["homes_increment"]
    assert client.post("/api/rezoning-test", json={"changes": {"10": "res"}}).status_code == 400


def test_search_understands_common_address_forms(client):
    hits = client.get("/api/search", params={"q": "14 W 4th St"}).json()
    assert hits and hits[0]["address"] == "14 WEST 4 STREET"
    assert client.get("/api/search", params={"q": "350 Fifth Ave"}).json()[0]["address"].endswith("5 AVENUE")


def test_zoning_summary_of_a_selection(client):
    z = client.post("/api/zoning-summary", json={"parcels": [10, 11, 12]}).json()
    assert z["n"] == 3 and z["has_zoning"] and z["max_far"]["min"] <= z["max_far"]["max"]
    assert all(u in [x["key"] for x in client.get("/api/meta").json()["land_uses"]] for u in z["allowed_on_all"])
    assert client.post("/api/zoning-summary", json={"parcels": [-5]}).status_code == 400
