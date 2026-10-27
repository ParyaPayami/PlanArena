"""The exact optimizer: its model equals the engine's score at every plan, its bound is valid, it finds the optimum
that exhaustive search finds, and its trade-off plans are Pareto-optimal and optimal for their weights."""
import itertools

import numpy as np
import pytest

from planarena.config import PILLARS
from planarena.indicators.engine import load_engine
from planarena.optimize.exact import ExactOptimizer
from planarena.optimize.frontier import _pillar_cfg, _pillars, augmecon, frontier
from planarena.optimize.suggest import SuggestConfig, Suggester


@pytest.fixture(scope="module")
def ex():
    e = load_engine()
    sug = Suggester(e, None)
    sug.per_use_values()
    return ExactOptimizer(sug)


def _area(ex, max_moves=14, seed=0):
    """A random tax block with a handful of options, as in planarena.validate.optimizer."""
    e = ex.e
    rng = np.random.default_rng(seed)
    blocks = e.p.groupby(["cd", "block"]).size()
    for cd, blk in rng.permutation(blocks.index.to_numpy()):
        cand = np.nonzero((e.p.block.to_numpy() == blk) & (e.cd == cd))[0]
        cfg = SuggestConfig(scope=f"cd:{int(cd)}", candidate_parcels=cand, w_fit=0.0, max_change_share=1.0)
        _, eligible, allowed = ex.sug.feasible(cfg, e.base_use)
        el = np.nonzero(eligible)[0]
        moves = [(p, u) for p in el for u in np.nonzero(allowed[p])[0] if u != e.base_use[p]]
        if 3 <= len(el) <= 8 and 4 <= len(moves) <= max_moves:
            return cfg, moves
    raise RuntimeError("no small block")


def _plans(e, moves, budget):
    for k in range(budget + 1):
        for combo in itertools.combinations(moves, k):
            if len({p for p, _ in combo}) == k:
                use = e.base_use.copy()
                for p, u in combo:
                    use[p] = u
                yield use


def test_model_equals_engine_score_on_fixed_plans(ex):
    """With a plan fixed and its products exact, the MILP's value is the engine's J (no relaxation gap)."""
    e = ex.e
    cfg = SuggestConfig(scope="cd:105", w_fit=0.0)
    start = e.base_use.copy()
    mask, elig, allowed = ex.sug.feasible(cfg, start)
    prep = ex._prepare(cfg, start, mask, elig, allowed, 6)
    P = prep["pairs"]
    rng = np.random.default_rng(0)
    for trial in range(3):
        chosen, seen = [], set()
        for q in rng.permutation(len(P.parcel)):
            if int(P.parcel[q]) not in seen:
                chosen.append(int(q))
                seen.add(int(P.parcel[q]))
            if len(chosen) >= 2 + 2 * trial:
                break
        plan = start.copy()
        plan[P.parcel[chosen]] = P.use[chosen]
        D = prep["D0"] + P.d["res"][chosen].sum()
        sets, tg = {"serv": {}, "fac": {}, "land": {}}, {}
        ex._refine(prep, plan, np.array(chosen), sets, tg)
        m, ix = ex._build(prep, 6, (D * 0.999, D * 1.001), 10 ** 6, sets, tg)
        on = set(chosen)
        for q, col in enumerate(ix["x"]):
            m.lb[col] = m.ub[col] = 1.0 if q in on else 0.0
        res = m.solve(120, 1e-8)
        assert res["x"] is not None
        assert abs(res["value"] + ix["const"] - ex.objective(plan, start, cfg, mask)) < 1e-3


def test_exact_optimum_and_bound_match_exhaustive_search(ex):
    e = ex.e
    for seed in (0, 1):
        cfg, moves = _area(ex, seed=seed)
        mask = e.scope_mask(e.base_use, cfg.scope)
        best = max(ex.objective(u, e.base_use, cfg, mask) for u in _plans(e, moves, 2))
        r = ex.solve(cfg, budget=2, time_limit=60, incumbent=e.base_use.copy())
        assert r["status"] == "optimal"
        assert abs(r["objective"] - best) < 1e-6
        assert r["bound"] >= best - 1e-9
        changed = r["changed"]
        assert len(changed) <= 2
        _, eligible, allowed = ex.sug.feasible(cfg, e.base_use)
        assert eligible[changed].all() and allowed[changed, r["use"][changed]].all()


def test_exact_front_is_pareto_and_matches_exhaustive_weighted_optima(ex):
    """Every plan the exact front reports is Pareto-optimal among all plans of a small area, every weighting's plan
    is that weighting's exhaustive optimum, and the epsilon-constraint plans are Pareto-optimal too."""
    e = ex.e
    cfg, moves = _area(ex, max_moves=10, seed=3)
    mask = e.scope_mask(e.base_use, cfg.scope)
    budget = 3
    plans = list(_plans(e, moves, budget))
    pts = [_pillars(ex, u, mask) for u in plans]
    dominated = lambda a: any(all(b[p] >= a[p] - 1e-9 for p in PILLARS) and any(b[p] > a[p] + 1e-9 for p in PILLARS)
                              for b in pts)
    pc = SuggestConfig(**{**cfg.__dict__, "conversion_penalty": 0.0})
    res = frontier(ex, pc, mask=mask, budget=budget, step=0.5, time_per_point=30, robustness=False)
    for f in res["front"]:
        assert not dominated(f["pillars"]), f["pillars"]
    for row in res["solves"]:
        lam = row["weights"]
        best = max(sum(lam[p] * q[p] for p in PILLARS) for q in pts)
        u = next(f["use"] for f in res["front"] if lam in f["weights"]) if any(lam in f["weights"] for f in res["front"]) else None
        if u is not None:
            got = _pillars(ex, u, mask)
            assert sum(lam[p] * got[p] for p in PILLARS) >= best - 1e-6
    eps = augmecon(ex, pc, mask=mask, budget=budget, grid=3, time_per_point=30)
    for f in eps["front"]:
        assert not dominated(f["pillars"]), f["pillars"]
    assert _pillar_cfg(cfg).indicator_weights


def test_plausibility_floor_is_respected_and_costs_nothing_when_slack(ex):
    """With a floor on the changed parcels' mean redevelopment probability the plan meets it, and a floor of zero
    leaves the optimum unchanged."""
    from planarena.config import PROCESSED

    e = ex.e
    lik = np.load(PROCESSED / "redevelopment.npz")["p"]
    cfg, moves = _area(ex, seed=0)
    free = ex.solve(cfg, budget=2, time_limit=60, incumbent=e.base_use.copy())
    zero = ex.solve(cfg, budget=2, time_limit=60, incumbent=e.base_use.copy(), likelihood=lik, min_mean_likelihood=0.0)
    assert abs(free["objective"] - zero["objective"]) < 1e-9
    floor = float(np.quantile(lik[[p for p, _ in moves]], 0.8))
    r = ex.solve(cfg, budget=2, time_limit=60, incumbent=e.base_use.copy(), likelihood=lik, min_mean_likelihood=floor)
    assert r["status"] == "optimal" and r["objective"] <= free["objective"] + 1e-9
    if len(r["changed"]):
        assert lik[r["changed"]].mean() >= floor - 1e-12
