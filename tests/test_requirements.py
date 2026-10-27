"""Acceptance tests for the requirements coded "met" in planarena/requirements_coding.yaml.

Each test names the requirement it demonstrates. tests/test_requirements.py::test_every_met_item_has_a_test
keeps the coding and the tests in step.
"""
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from planarena.api import store
from planarena.api.app import app

CODING = yaml.safe_load((Path(__file__).parents[1] / "planarena" / "requirements_coding.yaml").read_text())


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    store.DB = tmp_path_factory.mktemp("db") / "req.sqlite3"
    return TestClient(app)


@pytest.fixture(scope="module")
def study(client):
    soft = client.get("/api/soft-sites").json()["parcels"][:3]
    changes = {str(i): {"use": "res", "far": 6} for i in soft}
    s = client.post("/api/scenarios", json={"name": "Upzoning study", "description": "Purpose: housing on soft sites",
                                            "study_area": "cd:103", "changes": changes}).json()
    return s, soft


def test_G1_study_is_tied_to_parcels(client, study):
    s, soft = study
    got = client.get(f"/api/scenarios/{s['id']}").json()
    for i in soft:
        assert str(i) in got["changes"]
        assert client.get(f"/api/parcel/{i}").json()["bbl"] > 0


def test_G6_past_studies_can_be_found_and_opened(client, study):
    s, _ = study
    assert s["id"] in [x["id"] for x in client.get("/api/scenarios").json()]
    assert client.get(f"/api/scenarios/{s['id']}").json()["name"] == "Upzoning study"


def test_G7_study_information_is_recorded(client, study):
    got = client.get(f"/api/scenarios/{study[0]['id']}").json()
    assert got["description"].startswith("Purpose") and got["study_area"] == "cd:103" and got["checklist"]


def test_G8_existing_development_current_plan_and_proposed_change(client, study):
    s, soft = study
    p = client.get(f"/api/parcel/{soft[0]}").json()
    for k in ("bldg_area_sqft", "built_far", "zone", "max_far", "use"):  # existing development and current plan
        assert k in p
    assert s["changes"][str(soft[0])] == {"use": "res", "far": 6.0}  # proposed change


def test_G12_and_G13_history_and_status_tracking(client, study):
    s, _ = study
    client.patch(f"/api/scenarios/{s['id']}", json={"status": "under review"})
    client.patch(f"/api/scenarios/{s['id']}", json={"status": "hearing scheduled", "hearing_date": "2027-03-01"})
    hist = client.get(f"/api/scenarios/{s['id']}/history").json()
    assert len(hist) >= 3
    assert client.get("/api/health").json()["audit"]["valid"]


def test_G14_change_in_development_potential_is_quantified(client, study):
    s, _ = study
    ev = client.post("/api/evaluate", json={"changes": s["changes"], "scope": "affected", "ranges": True}).json()
    cap = ev["capacity"]
    assert cap["scenario"]["built_sqft"] > cap["baseline"]["built_sqft"]
    homes = next(r for r in ev["indicators"] if r["key"] == "homes")
    assert homes["delta"] > 0 and homes["range"][0] <= homes["delta"] <= homes["range"][1]


def test_G23_decision_is_recorded(client, study):
    s, _ = study
    assert client.patch(f"/api/scenarios/{s['id']}", json={"status": "adopted"}).json()["status"] == "adopted"


def test_every_met_item_has_a_test():
    names = " ".join(n for n in globals() if n.startswith("test_G"))
    for item in CODING["items"]:
        if item["status"] == "met":
            assert f"_{item['id']}_" in names, item["id"]


def test_G11_staff_can_customise_the_checklist(client, study):
    s, _ = study
    got = client.get(f"/api/scenarios/{s['id']}").json()
    items = got["checklist"] + [{"label": "Community board review", "done": False}]
    upd = client.patch(f"/api/scenarios/{s['id']}", json={"checklist": items}).json()
    assert upd["checklist"][-1]["label"] == "Community board review"
    bad = client.patch(f"/api/scenarios/{s['id']}", json={"checklist": [{"label": "x", "done": False, "owner": "me"}]})
    assert bad.status_code == 422
