"""Core invariants of the PlanArena twin, impact engine, optimizer and agents.

Run with:  .venv/bin/python -m pytest -q
"""
import numpy as np
import pytest

from planarena.agents.gametheory import individually_rational, kalai_smorodinsky, nash_bargaining, pareto_front
from planarena.agents.negotiation import generate_candidates, negotiate
from planarena.agents.stakeholders import DEFAULT_STAKEHOLDERS
from planarena.config import USE_INDEX as U
from planarena.indicators.engine import INDICATORS, load_engine
from planarena.optimize.suggest import SuggestConfig, Suggester


@pytest.fixture(scope="module")
def engine():
    return load_engine()


@pytest.fixture(scope="module")
def suggester(engine):
    return Suggester(engine)


def test_baseline_has_zero_deltas(engine):
    ev = engine.evaluate(engine.base_use, scope="city")
    assert ev["n_changed"] == 0
    assert all(abs(r["delta"]) < 1e-9 for r in ev["indicators"])
    assert abs(ev["overall"]) < 1e-9


def test_undo_returns_exactly_to_baseline(engine):
    use = engine.base_use.copy()
    idx = np.nonzero(engine.base_use == U["prk"])[0][:30]
    use[idx] = U["res"]
    assert engine.evaluate(use, scope="city")["n_changed"] == 30
    use[idx] = engine.base_use[idx]
    assert all(abs(r["delta"]) < 1e-9 for r in engine.evaluate(use, scope="city")["indicators"])


def test_parking_to_housing_adds_homes_and_no_job_gain(engine):
    use = engine.base_use.copy()
    idx = np.nonzero(engine.base_use == U["prk"])[0][:20]
    use[idx] = U["res"]
    rows = {r["key"]: r for r in engine.evaluate(use, scope="city")["indicators"]}
    assert rows["homes"]["delta"] > 0
    # Staffed garages lose their few jobs; housing on a parking lot never creates jobs here.
    assert rows["jobs"]["delta"] <= 1e-6


def test_mixed_to_residential_never_loses_homes(engine):
    use = engine.base_use.copy()
    idx = np.nonzero((engine.base_use == U["mix"]) & (engine.obs_units > 0))[0][:200]
    use[idx] = U["res"]
    rows = {r["key"]: r for r in engine.evaluate(use, scope="city")["indicators"]}
    assert rows["homes"]["delta"] >= 0


def test_vacant_to_park_improves_green_space(engine):
    use = engine.base_use.copy()
    idx = np.nonzero(engine.base_use == U["vac"])[0][:10]
    use[idx] = U["opn"]
    rows = {r["key"]: r for r in engine.evaluate(use, scope="city")["indicators"]}
    assert rows["green_space"]["delta"] > 0
    assert rows["green_space"]["score"] > 0


def test_scores_are_bounded(engine):
    use = engine.base_use.copy()
    idx = np.nonzero(engine.cd == 103)[0]
    use[idx] = U["opn"]
    ev = engine.evaluate(use, scope="cd:103")
    assert all(-100 <= r["score"] <= 100 for r in ev["indicators"])


def test_by_use_parcel_counts_balance(engine):
    use = engine.base_use.copy()
    idx = np.nonzero(engine.base_use == U["prk"])[0][:15]
    use[idx] = U["com"]
    ev = engine.evaluate(use)
    assert sum(r["parcels"] for r in ev["by_use"]) == 0


def test_evaluate_is_fast(engine):
    import time
    use = engine.base_use.copy()
    use[np.nonzero(engine.base_use == U["prk"])[0][:50]] = U["res"]
    t0 = time.time()
    engine.evaluate(use)
    assert time.time() - t0 < 0.5


def test_optimizer_respects_protections(engine, suggester):
    r = suggester.suggest(SuggestConfig(scope="cd:103", max_change_share=0.05))
    ch = r["changed"]
    assert len(ch) > 0
    assert not engine.protected[ch].any(), "landmarks and historic districts are protected"
    assert not np.isin(engine.base_use[ch], [U["opn"], U["pub"], U["tra"]]).any()
    homes = engine.obs_units[ch] > 0
    assert np.isin(r["use"][ch][homes], [U["res"], U["mix"]]).all(), "existing homes are never removed"
    bits = (engine.allowed[ch] >> r["use"][ch]) & 1
    assert bits.all(), "zoning respected"
    assert r["evaluation"]["overall"] > 0


def test_consensus_plan_is_individually_rational(suggester):
    cfg = SuggestConfig(scope="cd:103", max_change_share=0.05,
                        unanimity_weights=[s.normalized() for s in DEFAULT_STAKEHOLDERS])
    ev = suggester.suggest(cfg)["evaluation"]
    assert all(s.utility(ev) >= -1e-6 for s in DEFAULT_STAKEHOLDERS)


def test_game_theory_solution_concepts():
    u = np.array([[1.0, 1.0], [3.0, 0.2], [0.2, 3.0], [-1.0, 5.0], [2.0, 1.5]])
    assert individually_rational(u).tolist() == [True, True, True, False, True]
    assert nash_bargaining(u) == 4  # 2.0 * 1.5 = 3.0 is the largest product
    assert kalai_smorodinsky(u) in (0, 4)
    assert pareto_front(u)[4] and not pareto_front(u)[0]


def test_negotiation_reaches_individually_rational_agreement(suggester):
    plans = generate_candidates(suggester, DEFAULT_STAKEHOLDERS, scope="cd:110")
    res = negotiate(plans, DEFAULT_STAKEHOLDERS)
    assert res["agreed_plan"] in res["plan_ids"]
    assert all(v >= -1e-6 for v in res["utilities"].values())
    assert res["transcript"][-1]["kind"] == "agree"


def test_indicator_metadata_complete():
    keys = [i.key for i in INDICATORS]
    assert len(keys) == len(set(keys)) == 11
    assert {i.pillar for i in INDICATORS} == {"social", "economic", "environmental"}


def test_calibrated_coefficients_are_loaded(engine):
    assert engine.coef.get("calibrated_on"), "run python -m planarena.calibrate"
    assert engine.coef["emissions_tco2e_per_kbtu"]["status"] == "derived"
    assert engine.coef["jobs_sqft_per_worker"]["status"] == "calibrated"


def test_baseline_jobs_match_qcew_target(engine):
    target = engine.coef["jobs_sqft_per_worker"]["calibration_target_jobs"]
    assert abs(engine.baseline_state["jobs"].sum() / target - 1) < 0.005


def test_paving_open_space_increases_runoff(engine):
    use = engine.base_use.copy()
    idx = np.nonzero((engine.base_use == U["opn"]) & (engine.bldg == 0))[0][:20]
    use[idx] = U["prk"]
    row = {r["key"]: r for r in engine.evaluate(use, scope="affected")["indicators"]}["runoff"]
    assert row["delta"] > 0


def test_no_indicator_is_provisional_after_calibration(engine):
    assert not any(engine.provisional.values()), engine.provisional


def test_web_layers_are_polygonal():
    """Every display parcel must be a polygon; a collapsed line once pulled a level's camera off the map."""
    import json

    from planarena.config import WEB_DATA

    for f in [WEB_DATA / "parcels.geojson", *sorted((WEB_DATA / "levels").glob("*.geojson"))]:
        types = {ft["geometry"]["type"] for ft in json.loads(f.read_text())["features"]}
        assert types <= {"Polygon", "MultiPolygon"}, (f.name, types)


def _tennessee():
    # Candidates 0 Memphis, 1 Nashville, 2 Chattanooga, 3 Knoxville (a standard social-choice example).
    orders = {0: [0, 1, 2, 3], 1: [1, 2, 3, 0], 2: [2, 3, 1, 0], 3: [3, 2, 1, 0]}
    U = np.zeros((4, 4))
    for v, o in orders.items():
        for pos, c in enumerate(o):
            U[c, v] = 3 - pos
    return U, np.array([42.0, 26.0, 15.0, 17.0])


def test_voting_rules_match_textbook_results():
    from planarena.agents import voting as V

    U, w = _tennessee()
    r = V.run_rules(U, w)
    assert r["plurality"]["winner"] == 0  # Memphis
    assert r["irv"]["winner"] == 3  # Knoxville
    for rule in ("borda", "copeland", "schulze", "kemeny"):
        assert r[rule]["winner"] == 1, rule  # Nashville
    assert r["condorcet_winner"] == 1 and r["condorcet_loser"] == 0
    assert r["kemeny"]["ranking"] == [1, 2, 3, 0]


def test_condorcet_paradox_has_no_winner():
    from planarena.agents import voting as V

    U = np.array([[2, 0, 1], [1, 2, 0], [0, 1, 2]], float)
    r = V.run_rules(U, np.ones(3))
    assert r["condorcet_winner"] is None and r["smith_set"] == [0, 1, 2]


def test_full_vote_is_consistent(suggester):
    from planarena.agents.voting import hold_vote

    r = hold_vote(suggester, DEFAULT_STAKEHOLDERS, scope="cd:110", samples=20)
    c = r["council"]
    ids = [x["id"] for x in r["candidates"]]
    assert ids[0] == "status-quo" and r["decision"]["plan"] == c["rules"]["schulze"]["winner"]
    if c["condorcet_winner"]:
        assert c["rules"]["schulze"]["winner"] == c["condorcet_winner"]
        assert c["rules"]["kemeny"]["winner"] == c["condorcet_winner"]
    assert c["smith_set"] and c["rules"]["schulze"]["winner"] in c["smith_set"]
    for k in ("coefficients", "seats", "both"):
        assert abs(sum(c["robustness"][k].values()) - 1) < 1e-9
    pb = r["parcel_ballot"]
    assert pb["changed"] <= pb["budget"] and pb["changed"] <= pb["passed"]
    assert all(pb["support"][pb["parcels"].index(i)] > 0.5 for i in pb["chosen"])
    assert r["residents"]["precincts"] > 0


def test_exact_polish_never_worse_and_fixes_large_parcel_case(engine):
    """Block 1006 (CD 105): first-order gains underrate a saturating access effect on a 1.4M sq ft lot."""
    s = Suggester(engine, None)
    cand = np.nonzero((engine.p.block.to_numpy() == 1006) & (engine.cd == 105))[0]
    base = dict(scope="cd:105", candidate_parcels=cand, w_fit=0.0, max_change_share=0.4, rounds=2,
                require_precedent=False)  # the move that exposed the gap is itself unprecedented (see next test)
    plain = s.suggest(SuggestConfig(**base))["evaluation"]["overall"]
    polished = s.suggest(SuggestConfig(polish=30, **base))["evaluation"]["overall"]
    assert polished >= plain - 1e-9 and polished > plain + 0.1


def test_conversions_without_precedent_are_flagged_and_skipped(engine, suggester):
    if engine.precedent is None:
        pytest.skip("run python -I -m planarena.models.transition precedent")
    tower = 10506  # 1.44M sq ft office building, CD 105
    assert not engine.has_precedent(np.array([tower]), np.array([U["pub"]]))[0]
    assert engine.has_precedent(np.array([tower]), np.array([U["res"]]))[0]  # office-to-residential has precedent
    use = engine.base_use.copy()
    use[tower] = U["pub"]
    assert any(w["type"] == "precedent" for w in engine.evaluate(use, scope="cd:105")["warnings"])
    _, _, allowed = suggester.feasible(SuggestConfig(scope="cd:105"), engine.base_use)
    assert not allowed[tower, U["pub"]]
