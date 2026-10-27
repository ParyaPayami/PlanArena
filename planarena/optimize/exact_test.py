"""Tests of the exact optimizer (planarena.optimize.exact) and the exact trade-off front (planarena.optimize.frontier).

* Blocks: the 20 tax blocks of planarena.validate.optimizer (same seed and filters), every plan with up to two
  changes enumerated; the exact optimizer must return the exhaustive optimum and a bound at least as high.
* Areas: random areas like a lasso selection in the Studio (150-300 m around a random parcel, a budget of 5% of
  eligible parcels): how often the optimum is certified, how long it takes, and how the first-order search with
  and without exact polishing compares with the optimum.
* Districts: every Manhattan district with a budget of ten changes, as in planarena.validate.optimizer_benchmark,
  started from the best plan any heuristic there found, with a time limit: the certified bound and gap.
* Fronts: exact fronts (a 0.25 weight grid and the balanced plan) of random areas: their size, the share of
  certified points, the efficiency gap of today's land use, trade-off rates and robustness to the coefficients;
  on small blocks, every front plan is checked against exhaustive enumeration (Pareto-optimal, optimal for its
  weights).

* Plausibility: the optimum when the changed parcels' mean redevelopment probability must reach a percentile of
  the area's eligible parcels: the cost of plausibility, exactly.

Run:  python -I -m planarena.optimize.exact_test [blocks|areas|fronts|plausibility|districts SECONDS [CDS]|summarize]
      -> results/validation/optimizer_exact.json, frontier_exact.json
"""
from __future__ import annotations

import itertools
import json
import sys
import time

import numpy as np

from planarena.config import PILLARS, ROOT

OUT = ROOT / "results" / "validation" / "optimizer_exact.json"
OUT_FRONT = ROOT / "results" / "validation" / "frontier_exact.json"


def _runtime():
    from planarena.indicators.engine import load_engine
    from planarena.optimize.exact import ExactOptimizer
    from planarena.optimize.suggest import Suggester

    e = load_engine()
    sug = Suggester(e, None)
    sug.per_use_values()
    return e, sug, ExactOptimizer(sug)


def _update(path, key, value) -> dict:
    res = json.loads(path.read_text()) if path.exists() else {"test": __doc__.strip().split("\n\n")[1].replace("\n", " ")}
    res[key] = value
    path.write_text(json.dumps(res, indent=1))
    return res


def blocks(n_areas: int = 20, budget: int = 2, seed: int = 0) -> dict:
    """The blocks of planarena.validate.optimizer: exact optimizer against exhaustive search."""
    from planarena.optimize.suggest import SuggestConfig

    e, sug, ex = _runtime()
    rng = np.random.default_rng(seed)
    blocks_ = e.p.groupby(["cd", "block"]).size()
    rows = []
    for (cd, blk) in rng.permutation(blocks_.index.to_numpy()):
        if len(rows) >= n_areas:
            break
        cand = np.nonzero((e.p.block.to_numpy() == blk) & (e.cd == cd))[0]
        cfg = SuggestConfig(scope=f"cd:{int(cd)}", candidate_parcels=cand, w_fit=0.0, max_change_share=1.0,
                            rounds=budget)
        _, eligible, allowed = sug.feasible(cfg, e.base_use)
        el = np.nonzero(eligible)[0]
        moves = [(p, u) for p in el for u in np.nonzero(allowed[p])[0] if u != e.base_use[p]]
        if not 4 <= len(el) <= 12 or not 4 <= len(moves) <= 40:
            continue
        mask = e.scope_mask(e.base_use, cfg.scope)
        best = 0.0
        for k in range(1, budget + 1):
            for combo in itertools.combinations(moves, k):
                if len({p for p, _ in combo}) < k:
                    continue
                use = e.base_use.copy()
                for p, u in combo:
                    use[p] = u
                best = max(best, ex.objective(use, e.base_use, cfg, mask))
        r = ex.solve(cfg, budget=budget, time_limit=120, incumbent=e.base_use.copy())
        rows.append({"cd": int(cd), "block": int(blk), "moves": len(moves), "exhaustive": best,
                     "exact": r["objective"], "bound": r["bound"], "status": r["status"], "seconds": r["seconds"]})
        print(rows[-1], flush=True)
    t = rows
    out = {"areas": len(t), "exact_equals_exhaustive": int(sum(abs(r["exact"] - r["exhaustive"]) <= 1e-9 for r in t)),
           "bound_at_least_exhaustive": int(sum(r["bound"] >= r["exhaustive"] - 1e-9 for r in t)),
           "certified": int(sum(r["status"] == "optimal" for r in t)),
           "median_seconds": float(np.median([r["seconds"] for r in t])), "rows": t}
    _update(OUT, "blocks", out)
    return out


def _random_area(e, rng, districts=None, lo_m=150.0, hi_m=300.0):
    xy = np.c_[e.p.cx.to_numpy(), e.p.cy.to_numpy()].astype(float)
    pool = np.nonzero((e.base_use >= 0) & (np.isin(e.cd, districts) if districts else True))[0]
    c = int(rng.choice(pool))
    rad = rng.uniform(lo_m, hi_m) / 50.0
    return np.nonzero(((xy - xy[c]) ** 2).sum(1) <= rad ** 2)[0]


def areas(n: int = 30, seed: int = 11, time_limit: float = 120.0, budget_share: float = 0.05) -> dict:
    from planarena.optimize.suggest import SuggestConfig

    e, sug, ex = _runtime()
    rng = np.random.default_rng(seed)
    rows = []
    while len(rows) < n:
        sel = _random_area(e, rng)
        mask = e.study_area(sel)
        cfg = SuggestConfig(scope="affected", candidate_parcels=sel, w_fit=0.0, mask=mask)
        _, elig, _ = sug.feasible(cfg, e.base_use)
        nel = int(elig.sum())
        if nel < 10:
            continue
        budget = max(2, int(budget_share * nel))
        cfg.max_change_share = budget / nel + 1e-9
        t0 = time.time()
        fast = sug.suggest(SuggestConfig(**{**cfg.__dict__, "polish": 0}))["use"]
        t_fast = time.time() - t0
        t0 = time.time()
        pol = sug.suggest(SuggestConfig(**{**cfg.__dict__, "polish": 30}))["use"]
        t_pol = time.time() - t0
        r = ex.solve(cfg, mask=mask, budget=budget, time_limit=time_limit, incumbent=fast)
        J = lambda u: ex.objective(u, e.base_use, cfg, mask)
        rows.append({"parcels": int(len(sel)), "eligible": nel, "budget": budget, "status": r["status"],
                     "rel_gap": r["rel_gap"], "seconds": r["seconds"], "J_exact": r["objective"],
                     "J_first_order": J(fast), "J_polished": J(pol), "s_first_order": t_fast, "s_polished": t_pol})
        print(len(rows), {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
    cert = [r for r in rows if r["status"] == "optimal"]
    pos = [r for r in cert if r["J_exact"] > 1e-9]
    out = {"areas": len(rows), "certified": len(cert), "time_limit_seconds": time_limit,
           "parcels_range": [min(r["parcels"] for r in rows), max(r["parcels"] for r in rows)],
           "eligible_range": [min(r["eligible"] for r in rows), max(r["eligible"] for r in rows)],
           "median_seconds_certified": float(np.median([r["seconds"] for r in cert])) if cert else None,
           "max_seconds_certified": float(max(r["seconds"] for r in cert)) if cert else None,
           "first_order_share_of_optimum_median": float(np.median([max(r["J_first_order"], 0) / r["J_exact"] for r in pos])),
           "polished_share_of_optimum_median": float(np.median([max(r["J_polished"], 0) / r["J_exact"] for r in pos])),
           "first_order_optimal": int(sum(r["J_first_order"] >= r["J_exact"] - 1e-6 for r in pos)),
           "polished_optimal": int(sum(r["J_polished"] >= r["J_exact"] - 1e-6 for r in pos)),
           "positive_optimum": len(pos), "rows": rows}
    _update(OUT, "areas", out)
    return out


DISTRICTS = ROOT / "results" / "validation" / "optimizer_exact_districts"


def districts(seconds: float = 10800.0, budget: int = 10, which=tuple(range(101, 113))) -> dict:
    """Every district, started from the best plan of planarena.validate.optimizer_benchmark's heuristics. Each
    district writes its own file (so districts can run in parallel processes); the summary is rebuilt from all."""
    from planarena.optimize.suggest import SuggestConfig

    e, sug, ex = _runtime()
    bench = {r["district"]: r for r in json.loads((ROOT / "results" / "validation" / "optimizer_benchmark.json").read_text())["districts"]}
    DISTRICTS.mkdir(parents=True, exist_ok=True)
    for cd in which:
        cfg = SuggestConfig(scope=f"cd:{cd}", w_fit=0.0, rounds=3)
        inc = _greedy(e, sug, cfg, budget)
        r = ex.solve(cfg, budget=budget, time_limit=seconds, incumbent=inc)
        b = bench.get(cd, {})
        best_h = max([b[m].get("J", b[m].get("J_mean", -np.inf)) for m in b if isinstance(b.get(m), dict)] or [-np.inf])
        row = {"district": cd, "eligible": r["eligible"], "budget": budget, "status": r["status"],
               "objective": r["objective"], "bound": r["bound"], "rel_gap": r["rel_gap"], "seconds": r["seconds"],
               "time_limit_seconds": seconds, "best_heuristic_benchmark": best_h, "intervals": r["intervals"]}
        (DISTRICTS / f"{cd}.json").write_text(json.dumps(row, indent=1))
        print(row, flush=True)
    return summarize_districts()


def summarize_districts() -> dict:
    rows = sorted((json.loads(f.read_text()) for f in DISTRICTS.glob("*.json")), key=lambda r: r["district"])
    out = {"time_limit_seconds": max(r["time_limit_seconds"] for r in rows), "budget": rows[0]["budget"], "rows": rows}
    _update(OUT, "districts", out)
    return out


def _greedy(e, sug, cfg, budget: int, n_cand: int = 150) -> np.ndarray:
    """Greedy search with exact evaluation over the best first-order moves (as in optimizer_benchmark)."""
    mask, eligible, allowed = sug.feasible(cfg, e.base_use)
    pen = cfg.conversion_penalty
    J = lambda u: e.evaluate(u, scope=cfg.scope)["overall"] - pen * int((u != e.base_use).sum())
    ctx = sug._state(mask, e.base_use)
    pu = sug.per_use_values()
    ag = sug._access_gain(e.base_use, ctx["state"], ctx["acc"], mask, pu)
    g = sug._gain(sug._coefficients(ctx["base"], cfg.pillar_weights, None), pu, e.base_use, ag)
    g[~allowed] = -np.inf
    g[~eligible] = -np.inf
    g[np.arange(e.n), e.base_use] = -np.inf
    flat = np.argsort(-g, axis=None)[:n_cand]
    moves = [(int(i // g.shape[1]), int(i % g.shape[1])) for i in flat if np.isfinite(g.flat[i])]
    cur, curJ, used = e.base_use.copy(), J(e.base_use), set()
    for _ in range(budget):
        best = None
        for p_, u_ in moves:
            if p_ in used:
                continue
            t = cur.copy()
            t[p_] = u_
            v = J(t)
            if best is None or v > best[0]:
                best = (v, p_, u_)
        if best is None or best[0] <= curJ:
            break
        curJ, cur[best[1]] = best[0], best[2]
        used.add(best[1])
    return cur


def fronts(n: int = 10, seed: int = 21, step: float = 0.25, n_blocks: int = 5) -> dict:
    from planarena.optimize.frontier import _pillars, frontier
    from planarena.optimize.suggest import SuggestConfig

    e, sug, ex = _runtime()
    rng = np.random.default_rng(seed)
    rows = []
    while len(rows) < n:
        sel = _random_area(e, rng)
        mask = e.study_area(sel)
        cfg = SuggestConfig(scope="affected", candidate_parcels=sel, w_fit=0.0, conversion_penalty=0.0)
        _, elig, _ = sug.feasible(cfg, e.base_use)
        nel = int((elig & mask).sum())
        if nel < 10:
            continue
        budget = max(2, int(0.05 * nel))
        f = frontier(ex, cfg, mask=mask, budget=budget, step=step, time_per_point=60)
        first_rates = {k: (abs(list(v[0].values())[-1]) if v else None) for k, v in f["rates"].items()}
        rows.append({"parcels": int(len(sel)), "eligible": nel, "budget": budget, "front_size": len(f["front"]),
                     "certified_share": f["certified_share"], "efficiency_gap": f["balanced"]["efficiency_gap"],
                     "balanced": f["balanced"]["pillars"], "balanced_status": f["balanced"]["status"],
                     "first_rates": first_rates, "robust_share": f.get("robust_share"), "seconds": f["seconds"]})
        print(len(rows), rows[-1], flush=True)
    # small blocks: front plans against exhaustive enumeration
    checks = []
    blk = e.p.block.to_numpy()
    for (cd, b) in rng.permutation(e.p.groupby(["cd", "block"]).size().index.to_numpy()):
        if len(checks) >= n_blocks:
            break
        cand = np.nonzero((blk == b) & (e.cd == cd))[0]
        cfg = SuggestConfig(scope=f"cd:{int(cd)}", candidate_parcels=cand, w_fit=0.0, max_change_share=1.0,
                            conversion_penalty=0.0)
        _, eligible, allowed = sug.feasible(cfg, e.base_use)
        el = np.nonzero(eligible)[0]
        moves = [(p, u) for p in el for u in np.nonzero(allowed[p])[0] if u != e.base_use[p]]
        if not 3 <= len(el) <= 8 or not 4 <= len(moves) <= 12:
            continue
        mask = e.scope_mask(e.base_use, cfg.scope)
        pts = []
        for k in range(0, 4):
            for combo in itertools.combinations(moves, k):
                if len({p for p, _ in combo}) == k:
                    u = e.base_use.copy()
                    for p, v in combo:
                        u[p] = v
                    pts.append(_pillars(ex, u, mask))
        dominated = lambda a: any(all(q[p] >= a[p] - 1e-9 for p in PILLARS) and any(q[p] > a[p] + 1e-9 for p in PILLARS)
                                  for q in pts)
        exact_front = [a for a in pts if not dominated(a)]
        f = frontier(ex, cfg, mask=mask, budget=3, step=step, time_per_point=60, robustness=False)
        checks.append({"cd": int(cd), "block": int(b), "plans": len(pts), "pareto_plans": len(exact_front),
                       "front_plans": len(f["front"]),
                       "front_plans_dominated": int(sum(dominated(x["pillars"]) for x in f["front"])),
                       "pareto_plans_found": int(sum(any(all(abs(a[p] - x["pillars"][p]) < 1e-6 for p in PILLARS)
                                                         for x in f["front"]) for a in exact_front))})
        print(checks[-1], flush=True)
    out = {"step": step, "areas": rows, "blocks": checks,
           "median_front_size": float(np.median([r["front_size"] for r in rows])),
           "median_certified_share": float(np.median([r["certified_share"] for r in rows])),
           "median_efficiency_gap": float(np.median([r["efficiency_gap"] for r in rows])),
           "median_seconds": float(np.median([r["seconds"] for r in rows])),
           "median_robust_share": float(np.median([r["robust_share"] for r in rows if r["robust_share"] is not None]))}
    OUT_FRONT.write_text(json.dumps({"test": __doc__.strip().split("\n\n")[1].replace("\n", " "), **out}, indent=1))
    return out


def plausibility(n: int = 12, seed: int = 31, levels=(None, 0.5, 0.8, 0.95), time_limit: float = 120.0) -> dict:
    """The cost of plausibility, exactly: in random areas, the optimum when the changed parcels' mean five-year
    redevelopment probability must reach a percentile of the area's eligible parcels."""
    from planarena.config import PROCESSED
    from planarena.optimize.suggest import SuggestConfig

    e, sug, ex = _runtime()
    lik = np.load(PROCESSED / "redevelopment.npz")["p"]
    rng = np.random.default_rng(seed)
    rows = []
    while len(rows) < n:
        sel = _random_area(e, rng)
        mask = e.study_area(sel)
        cfg = SuggestConfig(scope="affected", candidate_parcels=sel, w_fit=0.0, mask=mask)
        _, elig, _ = sug.feasible(cfg, e.base_use)
        nel = int(elig.sum())
        if nel < 10:
            continue
        budget = max(2, int(0.05 * nel))
        el = np.nonzero(elig)[0]
        row = {"parcels": int(len(sel)), "eligible": nel, "budget": budget, "levels": []}
        for q in levels:
            pmin = None if q is None else float(np.quantile(lik[el], q))
            r = ex.solve(cfg, mask=mask, budget=budget, time_limit=time_limit, likelihood=lik, min_mean_likelihood=pmin,
                         incumbent=e.base_use.copy())
            ch = r["changed"]
            row["levels"].append({"percentile": q, "p_min": pmin, "objective": r["objective"], "status": r["status"],
                                  "changes": int(len(ch)), "mean_p_changed": float(lik[ch].mean()) if len(ch) else None})
        rows.append(row)
        print(len(rows), [(l["percentile"], round(l["objective"], 4), l["status"]) for l in row["levels"]], flush=True)
    cost = {}
    for k, q in enumerate(levels[1:], 1):
        rel = [1 - r["levels"][k]["objective"] / r["levels"][0]["objective"] for r in rows
               if r["levels"][0]["objective"] > 1e-9 and r["levels"][k]["status"] == "optimal"]
        cost[str(q)] = float(np.median(rel)) if rel else None
    out = {"areas": rows, "median_cost_of_floor": cost,
           "certified_share": float(np.mean([l["status"] == "optimal" for r in rows for l in r["levels"]]))}
    _update(OUT, "plausibility", out)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "blocks"
    if cmd == "blocks":
        print({k: v for k, v in blocks().items() if k != "rows"})
    elif cmd == "areas":
        print({k: v for k, v in areas().items() if k != "rows"})
    elif cmd == "fronts":
        print({k: v for k, v in fronts().items() if k not in ("areas", "blocks")})
    elif cmd == "plausibility":
        print({k: v for k, v in plausibility().items() if k != "areas"})
    elif cmd == "summarize":
        print(summarize_districts())
    elif cmd == "districts":
        sec = float(sys.argv[2]) if len(sys.argv) > 2 else 10800.0
        which = tuple(int(x) for x in sys.argv[3].split(",")) if len(sys.argv) > 3 else tuple(range(101, 113))
        print(districts(sec, which=which))
