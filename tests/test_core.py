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
    """Block 1006 (CD 105), on a 1.4M sq ft lot: first-order gains without the land-use mix term missed the best plan,
    which only exact polishing found. With the mix term, first-order search reaches it, and polishing never lowers
    the score."""
    s = Suggester(engine, None)
    cand = np.nonzero((engine.p.block.to_numpy() == 1006) & (engine.cd == 105))[0]
    base = dict(scope="cd:105", candidate_parcels=cand, w_fit=0.0, max_change_share=0.4, rounds=2,
                require_precedent=False)  # the move that exposed the gap is itself unprecedented (see next test)
    plain = s.suggest(SuggestConfig(**base))["evaluation"]["overall"]
    polished = s.suggest(SuggestConfig(polish=30, **base))["evaluation"]["overall"]
    assert polished >= plain - 1e-9 and plain >= polished - 1e-6 and plain > 0.5


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


def _deltas(engine, use, far, keys=("homes", "jobs", "ghg")):
    ev = engine.evaluate(use, scope="city", far=far)
    return {r["key"]: r["delta"] for r in ev["indicators"] if r["key"] in keys}


def test_difference_form_is_invariant_to_baseline_residuals():
    """R2: under the difference form, a baseline residual (observed vs modelled) does not enter the deltas."""
    e = load_engine()
    e.delta_form = "difference"
    rng = np.random.default_rng(1)
    # Density increases within the same use: no quantity can go negative, so no flooring is needed.
    idx = np.nonzero((e.base_use == U["com"]) & (e.bldg > 0) & (e.lot > 0))[0][:40]
    use = e.base_use.copy()
    far = np.full(e.n, np.nan)
    far[idx] = 1.5 * e.bldg[idx] / e.lot[idx]
    before = _deltas(e, use, far)
    # Inject a residual: inflate observed floor-area components and homes on the changed parcels.
    for k in e.obs:
        e.obs[k] = e.obs[k].copy()
        e.obs[k][idx] = e.obs[k][idx] * 1.3 + 1000.0
    e.obs_units = e.obs_units.copy()
    e.obs_units[idx] = e.obs_units[idx] + rng.integers(1, 20, len(idx))
    e.baseline_state = e.parcel_state(e.base_use)
    e._variant_cache = {}
    e._city_base = e.aggregate(e.baseline_state, e.access(e.baseline_state), np.ones(e.n, bool))
    after = _deltas(e, use, far)
    assert e.clip_events == 0
    for k in before:
        assert abs(after[k] - before[k]) < 1e-6 * max(1.0, abs(before[k])), k


def test_hybrid_density_change_keeps_the_parcels_own_mix(engine):
    """R2: a FAR change without a use change scales the parcel's observed composition, not the city's mix."""
    i = int(np.nonzero((engine.base_use == U["com"]) & (engine.bldg > 50_000))[0][0])
    far = np.full(engine.n, np.nan)
    far[i] = 2 * engine.bldg[i] / engine.lot[i]
    st = engine.parcel_state(engine.base_use, far)
    base = engine.baseline_state
    assert abs(st["jobs"][i] - 2 * base["jobs"][i]) < 1e-6 * max(1.0, base["jobs"][i])
    assert abs(st["fa_total"][i] - 2 * engine.bldg[i]) < 1e-6 * engine.bldg[i]


def test_precedent_table_only_uses_earlier_periods():
    """R5: precedents for a decision year never include later conversions."""
    from planarena.models import history, transition

    if not all((history.snapshot_dir(y) / "parcels.parquet").exists() for y in history.RELEASES):
        pytest.skip("annual snapshots not built (python -I -m planarena.models.history)")
    early = transition.precedent(as_of=2018, write=False)
    late = transition.precedent(as_of=2025, write=False)
    assert all(int(p.split("->")[1]) <= 2018 for p in early["pairs"])
    assert (np.array(early["counts"]) <= np.array(late["counts"])).all()
    assert early["total_changes"] < late["total_changes"]


def test_transition_features_read_only_the_decision_year_snapshot(tmp_path, monkeypatch):
    """R5: the features of a lot at decision year t come from the t snapshot alone, never from a later one."""
    from pathlib import Path

    from planarena.models import history, rolling

    t = 2020
    if not (history.snapshot_dir(t) / "parcels.parquet").exists():
        pytest.skip("annual snapshots not built (python -I -m planarena.models.history)")
    monkeypatch.setattr(rolling, "CACHE", tmp_path)
    opened = []
    real_pq, real_load = rolling.pd.read_parquet, rolling.np.load
    monkeypatch.setattr(rolling.pd, "read_parquet", lambda p, *a, **k: (opened.append(Path(p)), real_pq(p, *a, **k))[1])
    monkeypatch.setattr(rolling.np, "load", lambda p, *a, **k: (opened.append(Path(p)), real_load(p, *a, **k))[1])
    x = rolling._x(t)
    data = [p for p in opened if tmp_path not in p.parents]
    assert data and all(p.parent == history.snapshot_dir(t) for p in data), data
    assert x.shape[0] == len(real_pq(history.snapshot_dir(t) / "parcels.parquet"))


def test_deployed_precedent_table_is_current():
    """The table the optimizer uses must be the date-aware one built from every annual pair (a stale table from an
    earlier version was caught by a clean-clone reproduction)."""
    import json

    from planarena.config import PROCESSED
    from planarena.models.history import RELEASES

    f = PROCESSED / "conversion_precedent.json"
    if not f.exists():
        pytest.skip("precedent table not built (python -I -m planarena.models.transition precedent)")
    t = json.loads(f.read_text())
    years = sorted(RELEASES)
    assert t.get("as_of") == years[-1]
    assert set(t.get("pairs", [])) == {f"{a}->{b}" for a, b in zip(years, years[1:])}


def test_first_order_gains_track_exact_changes_in_shares(engine, suggester):
    """The optimizer's first-order gains for the resident-weighted shares (access, mix, green cover) rank single
    moves as the full engine does."""
    from scipy.stats import spearmanr

    rng = np.random.default_rng(1)
    cfg = SuggestConfig(scope="cd:111")
    use = engine.base_use.astype("int16").copy()
    mask, eligible, allowed = suggester.feasible(cfg, use)
    ctx = suggester._state(mask, use)
    ag = suggester._access_gain(use, ctx["state"], ctx["acc"], mask, suggester.per_use_values())
    el = np.nonzero(eligible)[0]
    moves = [(p, u) for p in rng.choice(el, 80, replace=False) for u in np.nonzero(allowed[p])[0] if u != use[p]]
    moves = [moves[i] for i in rng.choice(len(moves), min(40, len(moves)), replace=False)]
    keys = ("mix", "green_cover", "facility_access")
    pred, obs = {k: [] for k in keys}, {k: [] for k in keys}
    for p, u in moves:
        t = use.copy()
        t[p] = u
        st = engine.parcel_state(t)
        a = engine.aggregate(st, engine.access(st), mask)
        for k in keys:
            pred[k].append(ag[k][p, u])
            obs[k].append(a[k] - ctx["base"][k])
    for k in keys:
        assert spearmanr(pred[k], obs[k])[0] > 0.9, k


def test_building_already_on_the_start_record_is_not_new(tmp_path):
    """A building with a year built of t0 that is already on the t0 record is not development in (t0, t1]."""
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import box

    from planarena.models.transition import labels

    geom = [box(0, 0, 10, 10), box(20, 0, 30, 10)]
    for name, fa, yb in (("t0", [5000.0, 0.0], [2020, 0]), ("t1", [5000.0, 8000.0], [2020, 2022])):
        d = tmp_path / name
        d.mkdir()
        pd.DataFrame({"bldg_area": fa, "year_built": yb, "use": [U["res"], U["vac"]]}).to_parquet(d / "parcels.parquet")
        gpd.GeoDataFrame(geometry=geom).to_parquet(d / "parcels.geoparquet")
    lab = labels(tmp_path / "t0", tmp_path / "t1", 2020)
    assert lab.developed.tolist() == [False, True]


def test_pareto_front_has_no_plan_beaten_on_every_pillar(engine, suggester):
    from planarena.optimize.pareto import pareto

    idx = np.nonzero((engine.p.block.to_numpy() == 1599) & (engine.cd == 110))[0]
    r = pareto(suggester, idx.tolist(), generations=30)
    v = np.array([[f["pillars"][p] for p in r["objectives"]] for f in r["front"]])
    beaten = ((v[None] >= v[:, None]).all(-1) & (v[None] > v[:, None]).any(-1)).any(1)
    assert len(v) and not beaten.any()
