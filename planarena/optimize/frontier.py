"""Exact trade-offs between the social, economic and environmental pillars, from the exact optimizer.

The NSGA-III explorer (planarena.optimize.pareto) approximates the trade-off front by evolution. Here each point
is an exact optimum of planarena.optimize.exact, with its certificate:

* Supported front: for weights w on a simplex grid, the plan maximising sum_p w_p x pillar_p (each a Pareto-optimal
  plan when certified; the efficiency frontier of Polasky et al. 2008 in planning terms).
* Epsilon-constraint plans: AUGMECON2 (Mavrotas & Florios 2013), an augmented epsilon-constraint method: maximise
  one pillar subject to floors on the other two over a grid of floors. It also finds Pareto plans no weighting
  reaches. Pillar scores are real-valued, so these plans are a representation of the front, not a guaranteed
  complete Pareto set (AUGMECON2 is exact for integer objective values with unit steps).
* Trade-off rates: along the frontier between two pillars (the third weighted zero), the change in one pillar per
  point gained in the other between neighbouring optimal plans (a marginal rate of transformation).
* Balanced plan and efficiency gap: the plan that maximises the weakest pillar. Its weakest-pillar score is how much
  every pillar could improve at once over today's land use, which scores zero on all three by construction: a
  measure of how far today's land use sits inside the frontier.
* Robustness: the share of frontier plans that stay non-dominated when every frontier plan is re-scored under the
  engine's low and high coefficient variants.

Pillar scores are the engine's (mean of the pillar's indicator scores).
"""
from __future__ import annotations

import itertools
import time

import numpy as np

from planarena.config import PILLARS
from planarena.optimize.exact import ExactOptimizer
from planarena.optimize.suggest import SuggestConfig

PART = {p: 1.0 for p in PILLARS}  # objective weights on pillar parts


def _pillar_cfg(cfg: SuggestConfig) -> SuggestConfig:
    """Indicator weights 1 / (indicators in its pillar): a pillar's part of the objective is its pillar score."""
    from planarena.indicators.engine import INDICATORS

    n_in = {p: sum(1 for i in INDICATORS if i.pillar == p) for p in PILLARS}
    c = SuggestConfig(**{**cfg.__dict__})
    c.indicator_weights = {i.key: 1.0 / n_in[i.pillar] for i in INDICATORS}
    c.pillar_weights = {p: 1.0 for p in PILLARS}
    return c


def _pillars(ex: ExactOptimizer, use, mask, variant: str = "mid") -> dict:
    """The engine's pillar scores of a plan, under the central coefficients or a low/high variant."""
    from planarena.indicators.engine import INDICATORS

    e = ex.e
    if variant == "mid":
        return dict(e.evaluate(use, mask=mask)["pillars"])
    e.variant = variant
    try:
        base, st = e.parcel_state(e.base_use), e.parcel_state(use)
        s, b = e.aggregate(st, e.access(st), mask), e.aggregate(base, e.access(base), mask)
    finally:
        e.variant = "mid"
    out = {p: [] for p in PILLARS}
    for ind in INDICATORS:
        d = s[ind.key] - b[ind.key]
        raw = 100 * d if ind.kind == "share" else (100 * d / abs(b[ind.key]) if abs(b[ind.key]) > 1e-9 else 0.0)
        out[ind.pillar].append(float(np.clip(ind.direction * raw, -100, 100)))
    return {p: float(np.mean(v)) for p, v in out.items()}


def _nondominated(points: list[dict]) -> list[int]:
    keep = []
    for i, a in enumerate(points):
        dom = False
        for j, b in enumerate(points):
            if j != i and all(b[p] >= a[p] - 1e-9 for p in PILLARS) and any(b[p] > a[p] + 1e-9 for p in PILLARS):
                dom = True
                break
        if not dom:
            keep.append(i)
    return keep


def frontier(ex: ExactOptimizer, cfg: SuggestConfig, mask: np.ndarray | None = None, budget: int | None = None,
             use: np.ndarray | None = None, step: float = 0.25, time_per_point: float = 30.0,
             robustness: bool = True) -> dict:
    """Supported front on a weight grid, the balanced plan, trade-off rates and robustness, all exact."""
    t0 = time.time()
    e = ex.e
    start = (e.base_use if use is None else np.asarray(use)).astype("int16")
    pc = _pillar_cfg(cfg)
    k = int(round(1 / step))
    grid = [(a / k, b / k, (k - a - b) / k) for a in range(k + 1) for b in range(k + 1 - a)]
    plans, rows = {}, []
    for w in grid:
        lam = dict(zip(PILLARS, w))
        r = ex.solve(pc, use=start, mask=mask, budget=budget, time_limit=time_per_point,
                     objective={"weights": lam}, by_pillar=True)
        key = tuple(np.nonzero(r["use"] != start)[0].tolist()) + tuple(r["use"][r["use"] != start].tolist())
        plans.setdefault(key, r["use"])
        rows.append({"weights": lam, "plan": key, "status": r["status"], "rel_gap": r["rel_gap"],
                     "seconds": r["seconds"]})
    # the balanced plan: the weakest pillar as high as possible
    bal = ex.solve(pc, use=start, mask=mask, budget=budget, time_limit=time_per_point,
                   objective={"maxmin": list(PILLARS)}, by_pillar=True)
    bkey = tuple(np.nonzero(bal["use"] != start)[0].tolist()) + tuple(bal["use"][bal["use"] != start].tolist())
    plans.setdefault(bkey, bal["use"])
    keys = list(plans)
    pts = [_pillars(ex, plans[k_], mask) for k_ in keys]
    front = _nondominated(pts)
    out_plans = []
    for i in front:
        u = plans[keys[i]]
        ch = np.nonzero(u != start)[0]
        out_plans.append({"pillars": pts[i], "n_changed": int(len(ch)), "use": u,
                          "balanced": keys[i] == bkey,
                          "weights": [r["weights"] for r in rows if r["plan"] == keys[i]]})
    # trade-off rates along each edge of the weight simplex (two pillars, the third at zero weight)
    rates = {}
    for a, b in itertools.combinations(PILLARS, 2):
        seq = [r for r in rows if r["weights"][[p for p in PILLARS if p not in (a, b)][0]] == 0.0]
        seq.sort(key=lambda r: -r["weights"][a])
        pv = []
        for r in seq:
            p_ = pts[keys.index(r["plan"])]
            if not pv or (abs(p_[a] - pv[-1][a]) > 1e-9 or abs(p_[b] - pv[-1][b]) > 1e-9):
                pv.append(p_)
        steps = []
        for u_, v_ in zip(pv[:-1], pv[1:]):
            da, db = v_[a] - u_[a], v_[b] - u_[b]
            if abs(da) > 1e-9:
                steps.append({"from": {a: u_[a], b: u_[b]}, "to": {a: v_[a], b: v_[b]},
                              f"{b}_per_{a}_point": db / da})
        rates[f"{a}-{b}"] = steps
    res = {"front": out_plans, "grid_points": len(grid), "solves": rows,
           "balanced": {"pillars": _pillars(ex, bal["use"], mask), "status": bal["status"], "rel_gap": bal["rel_gap"],
                        "efficiency_gap": float(min(_pillars(ex, bal["use"], mask).values()))},
           "rates": rates, "certified_share": float(np.mean([r["status"] == "optimal" for r in rows] +
                                                            [bal["status"] == "optimal"])),
           "seconds": round(time.time() - t0, 1)}
    if robustness and len(out_plans) > 1:
        stay = []
        for v in ("a", "b"):
            pv = [_pillars(ex, p["use"], mask, v) for p in out_plans]
            stay.append(len(_nondominated(pv)) / len(pv))
        res["robust_share"] = float(min(stay))
    return res


def augmecon(ex: ExactOptimizer, cfg: SuggestConfig, mask: np.ndarray | None = None, budget: int | None = None,
             use: np.ndarray | None = None, grid: int = 6, time_per_point: float = 30.0,
             maximize: str = "economic") -> dict:
    """AUGMECON2: maximise one pillar with floors on the other two over a grid between their payoff-table extremes;
    returns the non-dominated plans found (the exact Pareto set when the grid is fine enough)."""
    e = ex.e
    start = (e.base_use if use is None else np.asarray(use)).astype("int16")
    pc = _pillar_cfg(cfg)
    others = [p for p in PILLARS if p != maximize]
    # payoff table: each pillar's best value (the ranges for the floors)
    best = {}
    for p in PILLARS:
        r = ex.solve(pc, use=start, mask=mask, budget=budget, time_limit=time_per_point,
                     objective={"weights": {q: (1.0 if q == p else 1e-3) for q in PILLARS}}, by_pillar=True)
        best[p] = r
    ranges = {}
    for q in others:
        vals = [_pillars(ex, best[p]["use"], mask)[q] for p in PILLARS]
        ranges[q] = (min(vals), max(vals))
    plans = {}
    for i, j in itertools.product(range(grid + 1), repeat=2):
        floors = {others[0]: ranges[others[0]][0] + i / grid * (ranges[others[0]][1] - ranges[others[0]][0]),
                  others[1]: ranges[others[1]][0] + j / grid * (ranges[others[1]][1] - ranges[others[1]][0])}
        # floors on pillar parts: a pillar part is its pillar score
        r = ex.solve(pc, use=start, mask=mask, budget=budget, time_limit=time_per_point,
                     objective={"epsilon": {"maximize": maximize, "floors": floors}}, by_pillar=True)
        if np.isfinite(r["objective"]):
            key = tuple(np.nonzero(r["use"] != start)[0].tolist()) + tuple(r["use"][r["use"] != start].tolist())
            plans.setdefault(key, r["use"])
    for p in PILLARS:
        u = best[p]["use"]
        plans.setdefault(tuple(np.nonzero(u != start)[0].tolist()) + tuple(u[u != start].tolist()), u)
    keys = list(plans)
    pts = [_pillars(ex, plans[k_], mask) for k_ in keys]
    front = _nondominated(pts)
    return {"front": [{"pillars": pts[i], "use": plans[keys[i]]} for i in front], "grid": grid, "ranges": ranges}
