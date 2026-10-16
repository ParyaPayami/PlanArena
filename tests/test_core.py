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
