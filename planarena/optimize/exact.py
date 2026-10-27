"""Certified-optimal land-use plans: the impact engine's score as a mixed-integer linear program.

The first-order optimizer (planarena.optimize.suggest) reports the best plan it finds. This module states the same
objective, J = score - conversion penalty x changes (+ the optional GNN fit term), over every feasible plan of a
scope (a district or a study area) and solves it by branch-and-bound (HiGHS). Every
relaxation below over-estimates J, so the solver's bound is an upper bound on J over all feasible plans and each
answer carries a certificate: the plan's exact score, re-scored by the engine, and how far at most it can be from
the optimum.

Formulation, in changes from the start plan (x[q] = 1 when pair q = (parcel, new use) is chosen; at most one per
eligible parcel and at most `budget` in all):
* Totals (homes, jobs, value, green space, runoff, emissions) are linear in x; the +-100 score clip is exact.
* The five resident-weighted shares have one denominator, the scope's residents D, and never reach the clip, so
  they enter as one weighted mean tau = Q / D of the cells' composite access A (the weighted sum of the five access
  values). With tau = tau0 + delta and A = A0 + alpha, delta x D = N' where
      N' = sum_c R0_c alpha_c + sum_q dres_q x_q (A0_cell(q) - tau0) + sum_q dres_q x_q alpha_cell(q),
  linear except for products of a binary and a narrow continuous variable (McCormick envelopes, exact at binary
  points). The residents D are split into intervals; within one, delta <= N' / D_low when N' >= 0 and
  delta <= N' / D_high otherwise (one binary), which is exact as the intervals narrow.
* Each 50 m cell's access values come from linear sums within the radius (row prefix sums make a disk sum about
  2 x (2r + 1) terms), written as changes from the start:
    park: a binary y with open area within the walk >= park minimum x y (exact);
    services, facilities: (a0 + alpha) x target x (R0 + dR) <= F0 + dF, a0 + alpha <= 1;
    green cover: (g0 + gamma) x (T0 + dT) <= L0 + dL (grouped land T, open land L);
    land-use mix: Gibbs' inequality, (H0 + eta) x (T0 + dT) x log 5 <= sum_g L_g (-log s_g) for any shares s
      (a tangent of the entropy, exact at s = the cell's shares).
  The products alpha x dR (and eta x dT, gamma x dT) are exact for the pairs in an exact set and bounded by a
  McCormick envelope for the rest. Ranges of alpha, eta and gamma come from budget-limited extremes, the last
  through the Fannes-Audenaert continuity bound of entropy.
After each solve the plan is re-scored by the engine; exact products and entropy tangents are added for the pairs
the plan uses, and the loop stops when the bound and the best exact score agree (certified optimal) or at the time
limit (certified gap).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.signal import fftconvolve
from scipy.spatial import cKDTree

from planarena.config import PILLARS, USE_INDEX
from planarena.indicators.engine import ADDITIVE, INDICATORS
from planarena.optimize.suggest import N_USES, SuggestConfig, Suggester

U = USE_INDEX
SHARES = ("park_access", "services_access", "facility_access", "mix", "green_cover")
GROUPS = [("res",), ("mix", "com"), ("ind", "tra"), ("pub",), ("opn",)]  # as in ImpactEngine.access
NG = len(GROUPS)
GID = np.full(N_USES, -1)
for _j, _g in enumerate(GROUPS):
    for _k in _g:
        GID[U[_k]] = _j
LOG_G = float(np.log(NG))
INF = np.inf


class _Model:
    """Sparse MILP builder: columns with bounds, integrality and objective; rows lb <= a.x <= ub."""

    def __init__(self):
        self.lb, self.ub, self.c, self.integ = [], [], [], []
        self.r, self.k, self.v, self.rlb, self.rub = [], [], [], [], []

    def var(self, lb=0.0, ub=1.0, c=0.0, integer=False) -> int:
        self.lb.append(lb); self.ub.append(ub); self.c.append(c); self.integ.append(1 if integer else 0)
        return len(self.lb) - 1

    def row(self, terms, lb=-INF, ub=INF) -> None:
        """terms: (column, coefficient) pairs, duplicates summed. Each row is scaled by its largest coefficient,
        which leaves its solutions unchanged and keeps the solver well conditioned."""
        terms = [(j, a) for j, a in terms if a]
        if not terms:
            return
        s = max(abs(a) for _, a in terms)
        i = len(self.rlb)
        for j, a in terms:
            self.r.append(i); self.k.append(j); self.v.append(a / s)
        self.rlb.append(lb / s if np.isfinite(lb) else lb); self.rub.append(ub / s if np.isfinite(ub) else ub)

    @property
    def size(self) -> dict:
        return {"variables": len(self.lb), "integer": int(sum(self.integ)), "constraints": len(self.rlb),
                "nonzeros": len(self.v)}

    def solve(self, time_limit: float, rel_gap: float, cutoff: float | None = None, start: dict | None = None,
              log: bool = False) -> dict:
        """Maximise c.x with HiGHS. cutoff: only plans with c.x above it are searched (the bound stays valid);
        start: {column: value} of a known feasible plan, completed by the solver. Returns x (None if no plan was
        found), the value, the bound (upper bound on the maximum), and the status."""
        import highspy

        n, mrows = len(self.lb), len(self.rlb)
        A = sp.csc_array((self.v, (self.r, self.k)), shape=(mrows, n))
        A.sum_duplicates()
        h = highspy.Highs()
        h.setOptionValue("output_flag", bool(log))
        h.setOptionValue("time_limit", float(max(time_limit, 1.0)))
        h.setOptionValue("mip_rel_gap", float(rel_gap))
        h.setOptionValue("mip_abs_gap", 1e-7)
        lp = highspy.HighsLp()
        lp.num_col_, lp.num_row_ = n, mrows
        lp.col_cost_ = -np.asarray(self.c, float)
        lp.col_lower_ = np.asarray(self.lb, float)
        lp.col_upper_ = np.asarray(self.ub, float)
        lp.row_lower_ = np.asarray(self.rlb, float)
        lp.row_upper_ = np.asarray(self.rub, float)
        lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
        lp.a_matrix_.start_ = A.indptr.astype(np.int32)
        lp.a_matrix_.index_ = A.indices.astype(np.int32)
        lp.a_matrix_.value_ = A.data.astype(float)
        lp.integrality_ = [highspy.HighsVarType.kInteger if i else highspy.HighsVarType.kContinuous
                           for i in self.integ]
        h.passModel(lp)
        if cutoff is not None:  # minimisation of -c.x: nodes whose bound cannot beat -cutoff are pruned
            h.setOptionValue("objective_bound", float(-cutoff))
        if start:
            idx = np.fromiter(start.keys(), dtype=np.int32)
            val = np.fromiter(start.values(), dtype=float)
            h.setSolution(len(idx), idx, val)
        # a hard deadline: HiGHS checks its own time limit only at some points, so a large model can overrun it
        deadline = time.time() + max(time_limit, 1.0) + 5.0

        def stop(ev):
            if time.time() > deadline:
                ev.interrupt()

        for cb in (h.cbSimplexInterrupt, h.cbIpmInterrupt, h.cbMipInterrupt):
            cb.subscribe(stop)
        h.run()
        st = h.getModelStatus()
        info = h.getInfo()
        sol = h.getSolution()
        has = info.primal_solution_status >= 2  # feasible
        x = np.asarray(sol.col_value) if has else None
        bound = -float(info.mip_dual_bound) if np.isfinite(info.mip_dual_bound) else INF
        if st == highspy.HighsModelStatus.kInfeasible:
            bound = -INF
        return {"x": x, "value": -float(info.objective_function_value) if has else -INF, "bound": bound,
                "status": h.modelStatusToString(st), "infeasible": st == highspy.HighsModelStatus.kInfeasible,
                "optimal": st == highspy.HighsModelStatus.kOptimal}


def _mc(m: _Model, a: int, aL: float, aU: float, x: int, side: str) -> int:
    """P = a * x for binary x and a in [aL, aU] (aL <= 0 <= aU), bounded below or above; exact at binary x."""
    p = m.var(min(aL, 0.0), max(aU, 0.0))
    if side == "lower":  # P >= a - aU (1 - x), P >= aL x
        m.row([(p, 1.0), (a, -1.0), (x, -aU)], lb=-aU)
        m.row([(p, 1.0), (x, -aL)], lb=0.0)
    else:  # P <= a - aL (1 - x), P <= aU x
        m.row([(p, 1.0), (a, -1.0), (x, -aL)], ub=-aL)
        m.row([(p, 1.0), (x, -aU)], ub=0.0)
    return p


def _h2(e: float) -> float:
    return 0.0 if e <= 0 or e >= 1 else float(-e * np.log(e) - (1 - e) * np.log(1 - e))


@dataclass
class _Pairs:
    parcel: np.ndarray  # parcel index of each pair
    use: np.ndarray  # new use
    cell: np.ndarray  # grid cell
    d: dict  # quantity -> change per pair relative to the start plan


class ExactOptimizer:
    """Branch-and-bound over the engine's score, with a certificate. Wraps a Suggester (same data and rules)."""

    def __init__(self, sug: Suggester):
        self.sug = sug
        self.e = sug.e
        self._disk_rows = {}

    # ------------------------------------------------------------------ geometry
    def _rows(self, kernel: np.ndarray) -> list[tuple[int, int]]:
        """(row offset, half-width) of a disk kernel."""
        key = kernel.shape
        if key not in self._disk_rows:
            r = kernel.shape[0] // 2
            out = []
            for i in range(kernel.shape[0]):
                cols = np.nonzero(kernel[i] > 0)[0]
                if len(cols):
                    out.append((i - r, int(cols.max() - r)))
            self._disk_rows[key] = out
        return self._disk_rows[key]

    def _conv(self, weights: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        e = self.e
        r = np.bincount(e.cell, weights=weights, minlength=e.nx * e.ny).reshape(e.ny, e.nx)
        return np.clip(fftconvolve(r, kernel, mode="same").ravel(), 0, None)

    # ------------------------------------------------------------------ objective
    @staticmethod
    def _weights(cfg: SuggestConfig) -> dict[str, float]:
        """Score units per indicator score point, as in Suggester._coefficients and the engine's overall score."""
        if cfg.indicator_weights is not None:
            return {i.key: float(cfg.indicator_weights.get(i.key, 0.0)) for i in INDICATORS}
        pw = cfg.pillar_weights
        wsum = sum(pw.values()) or 1.0
        n_in = {p: sum(1 for i in INDICATORS if i.pillar == p) for p in PILLARS}
        return {i.key: pw.get(i.pillar, 0.0) / wsum / n_in[i.pillar] for i in INDICATORS}

    def objective(self, use: np.ndarray, start: np.ndarray, cfg: SuggestConfig, mask: np.ndarray,
                  spec: dict | None = None) -> float:
        """The exact value of a plan, from the engine's scores: by default J = weighted score - conversion penalty
        (+ fit term). spec as in _build: {"weights": {pillar: w}}, {"epsilon": {"maximize": p, "floors": {q: v}}}
        (-inf when a floor is missed) or {"maxmin": [pillars]}; pillar parts are sum_k w_k score_k."""
        ev = self.e.evaluate(use, mask=mask)
        w = self._weights(cfg)
        pillar_of = {i.key: i.pillar for i in INDICATORS}
        parts = {p: 0.0 for p in PILLARS}
        for r in ev["indicators"]:
            parts[pillar_of[r["key"]]] += w[r["key"]] * r["score"]
        spec = spec or {"weights": None}
        if "weights" in spec:
            lam = spec["weights"] or {}
            val = sum(float(lam.get(p, 1.0)) * v for p, v in parts.items())
        elif "epsilon" in spec:
            sp = spec["epsilon"]
            if any(parts[q] < float(v) - 1e-9 for q, v in sp["floors"].items()):
                return -INF
            rho = float(sp.get("rho", 1e-3))
            val = sum((1.0 if p == sp["maximize"] else rho) * v for p, v in parts.items())
        else:
            val = min(parts[p] for p in spec["maxmin"])
        val -= cfg.conversion_penalty * int((use != start).sum())
        if self.sug.suit is not None and cfg.w_fit > 0:
            lp = np.log(np.clip(self.sug.suit, 1e-4, 1))
            rows = np.arange(self.e.n)
            val += cfg.w_fit * float((lp[rows, use] - lp[rows, start]).sum())
        return float(val)

    # ------------------------------------------------------------------ solve
    def solve(self, cfg: SuggestConfig | None = None, use: np.ndarray | None = None, mask: np.ndarray | None = None,
              budget: int | None = None, time_limit: float = 60.0, gap_tol: float = 1e-4, abs_tol: float = 1e-6,
              k_exact: int = 3,
              d_ratio: float = 1.05, max_rounds: int = 25, incumbent: np.ndarray | None = None,
              objective: dict | None = None, by_pillar: bool = False, likelihood: np.ndarray | None = None,
              min_mean_likelihood: float | None = None, verbose: bool = False) -> dict:
        """Best plan with a certificate. `mask` fixes the scope (a study area); otherwise cfg.scope's mask.

        Returns use, changed, objective (exact J of the plan), bound (upper bound on J over all feasible plans),
        gap = bound - objective, status ("optimal" when gap <= max(abs_tol, gap_tol x |objective|), else "gap"),
        the rounds, seconds and the model size."""
        t_start = time.time()
        cfg = cfg or SuggestConfig()
        if cfg.unanimity_weights:
            raise ValueError("consensus mode has no single objective; use the first-order optimizer")
        e = self.e
        start = (e.base_use if use is None else np.asarray(use)).astype("int16").copy()
        scope_mask, eligible, allowed = self.sug.feasible(cfg, start)
        if mask is None:
            mask = scope_mask
        else:
            eligible &= mask
        if budget is None:
            budget = max(1, int(cfg.max_change_share * eligible.sum() + 1e-9))
        if objective and "weights" not in objective:
            by_pillar = True
        prep = self._prepare(cfg, start, mask, eligible, allowed, budget, by_pillar=by_pillar)
        value = lambda u: self.objective(u, start, cfg, mask, objective)
        if min_mean_likelihood is not None:  # the changed parcels' mean redevelopment probability is at least this
            prep["plaus"] = (np.asarray(likelihood, float), float(min_mean_likelihood))
            ok_plan = lambda u: (u == start).all() or float(np.mean(likelihood[u != start])) >= min_mean_likelihood - 1e-12
            value0 = value
            value = lambda u: value0(u) if ok_plan(u) else -INF
        best_use, best_J = start.copy(), value(start)
        if incumbent is None and mask is scope_mask and not objective:  # a good first plan prunes the tree
            c2 = SuggestConfig(**{**cfg.__dict__, "polish": max(cfg.polish, 30)})
            c2.max_change_share = budget / max(eligible.sum(), 1) + 1e-9
            incumbent = self.sug.suggest(c2, start)["use"]
        if incumbent is not None:
            Ji = value(incumbent)
            if Ji > best_J:
                best_use, best_J = incumbent.astype("int16").copy(), Ji
        tol = lambda: max(abs_tol, gap_tol * abs(best_J)) if np.isfinite(best_J) else abs_tol
        # residents intervals: geometric from the budget-limited minimum to maximum
        lo, hi = prep["D_range"]
        edges = [lo]
        while edges[-1] * d_ratio < hi:
            edges.append(edges[-1] * d_ratio)
        edges.append(hi)
        open_iv = {k: INF for k in range(len(edges) - 1)}  # interval -> its bound
        exact_sets = {"serv": {}, "fac": {}, "land": {}}
        tangents: dict[int, list[np.ndarray]] = {}
        rounds, size = [], {}
        pairs = prep["pairs"]
        for rnd in range(max_rounds):
            todo = [k for k, b in sorted(open_iv.items()) if b > best_J + tol()]  # fewest new residents first
            if not todo:
                break
            added_any = 0
            for k in todo:
                left = time_limit - (time.time() - t_start)
                if left <= 1.0:
                    break
                m, ix = self._build(prep, budget, (edges[k], edges[k + 1]), k_exact, exact_sets, tangents,
                                    objective)
                size = m.size
                warm = None
                D_best = prep["D0"] + float(pairs.d["res"][self._pairs_of(prep, best_use)].sum())
                if edges[k] <= D_best <= edges[k + 1]:
                    on = set(self._pairs_of(prep, best_use).tolist())
                    warm = {int(ix["x"][q]): float(q in on) for q in range(len(pairs.parcel))}
                res = m.solve(min(left, max(left / max(len(todo), 1), 5.0)), rel_gap=gap_tol / 10,
                              cutoff=best_J - ix["const"] + tol() / 2 if np.isfinite(best_J) else None, start=warm)
                if res["infeasible"]:  # nothing in this interval beats the incumbent by tol/2
                    open_iv[k] = best_J + tol() / 2
                    continue
                ub = res["bound"] + ix["const"]
                open_iv[k] = min(open_iv[k], ub)
                if res["x"] is None:
                    continue
                chosen = np.nonzero(res["x"][ix["x"]] > 0.5)[0]
                plan = start.copy()
                plan[pairs.parcel[chosen]] = pairs.use[chosen]
                J = value(plan)
                relaxed = res["value"] + ix["const"]
                if J > best_J + 1e-12:
                    best_use, best_J = plan, J
                added = self._refine(prep, plan, chosen, exact_sets, tangents)
                added_any += added
                rounds.append({"round": rnd + 1, "interval": [round(edges[k]), round(edges[k + 1])],
                               "bound": round(ub, 6), "relaxed_value_of_plan": round(relaxed, 6),
                               "exact_value_of_plan": round(J, 6), "changes": int(len(chosen)), "cuts_added": added,
                               "solver": res["status"], "seconds": round(time.time() - t_start, 2), **size})
                if verbose:
                    print(rounds[-1], flush=True)
            if time.time() - t_start > time_limit - 1.0 or not added_any:
                break
        bound = max(max(open_iv.values()), best_J)
        gap = bound - best_J if np.isfinite(best_J) else INF
        status = "optimal" if gap <= tol() else "gap"
        ev = e.evaluate(best_use, mask=mask)
        return {"use": best_use, "changed": np.nonzero(best_use != start)[0], "objective": best_J, "bound": bound,
                "gap": gap, "rel_gap": gap / abs(best_J) if best_J else (0.0 if gap <= abs_tol else INF),
                "status": status, "rounds": rounds,
                "intervals": len(edges) - 1, "seconds": round(time.time() - t_start, 2), "budget": budget,
                "eligible": int(eligible.sum()), "evaluation": ev, "model": size}

    @staticmethod
    def _pairs_of(prep, plan: np.ndarray) -> np.ndarray:
        """Pair indices that a plan uses."""
        pairs = prep["pairs"]
        return np.nonzero(plan[pairs.parcel] == pairs.use)[0]

    # ------------------------------------------------------------------ data for the model
    def _prepare(self, cfg, start, mask, eligible, allowed, budget, by_pillar: bool = False) -> dict:
        e = self.e
        pu = self.sug.per_use_values()
        st0 = e.parcel_state(start)
        E = np.nonzero(eligible)[0]
        al = allowed[E].copy()
        al[np.arange(len(E)), start[E]] = False  # pairs are changes; staying is "no pair chosen"
        pi, ui = np.nonzero(al)
        parcel, new = E[pi], ui.astype("int16")
        cur = start[parcel]
        d = {k: pu[k][parcel, new] - st0[k][parcel] for k in ADDITIVE}
        d["res"] = pu["residents"][parcel, new] - st0["residents"][parcel]
        d["serv"] = pu["services_fa"][parcel, new] - st0["services_fa"][parcel]
        d["fac"] = pu["pubfac_fa"][parcel, new] - st0["pubfac_fa"][parcel]
        lot = e.lot[parcel]
        d["open"] = lot * ((new == U["opn"]).astype(float) - (cur == U["opn"]))
        gcur = GID[np.clip(cur, 0, None)]
        for j in range(NG):
            d[f"L{j}"] = lot * ((GID[new] == j).astype(float) - (gcur == j))
        d["T"] = sum(d[f"L{j}"] for j in range(NG))
        d["tv"] = 0.5 * (sum(np.abs(d[f"L{j}"]) for j in range(NG)) + np.abs(d["T"]))
        for k in ("res", "T"):  # positive and negative parts, for envelopes that are exact at no change
            d[k + "+"] = np.clip(d[k], 0, None)
            d[k + "-"] = np.clip(d[k], None, 0)
        pairs = _Pairs(parcel=parcel, use=new, cell=e.cell[parcel], d=d)

        w = self._weights(cfg)
        base = e.aggregate(e.baseline_state, e._base_acc if hasattr(e, "_base_acc") else e._cache_base_acc(), mask)
        totals = []  # r_k = dir x 100 x (S_k - B_k) / |B_k|
        for ind in INDICATORS:
            if ind.kind == "share" or not w[ind.key]:
                continue
            b = base[ind.key]
            if not (b and np.isfinite(b) and abs(b) > 1e-9):
                continue
            scale = ind.direction * 100.0 / abs(b)
            r0 = scale * (float(st0[ind.key][mask].sum()) - b)
            totals.append({"key": ind.key, "pillar": ind.pillar, "w": w[ind.key], "r0": r0, "coef": scale * d[ind.key]})
        ws = {k: 100.0 * w[k] for k in SHARES}

        # cells whose access values carry weight: cells of scope parcels that have, or may get, residents
        res0 = st0["residents"]
        R0 = np.bincount(e.cell[mask], weights=res0[mask], minlength=e.nx * e.ny)
        may = np.zeros(e.nx * e.ny, bool)
        may[e.cell[mask & (res0 > 0)]] = True
        may[pairs.cell[(d["res"] + res0[parcel]) > 0]] = True
        cells = np.nonzero(may)[0]
        # start values within the radii, as the engine computes them
        f0 = {"open": self._conv(np.where(start == U["opn"], e.lot, 0.0), e.k_walk),
              "serv": self._conv(st0["services_fa"], e.k_walk), "rw": self._conv(res0, e.k_walk),
              "fac": self._conv(st0["pubfac_fa"], e.k_fac), "rf": self._conv(res0, e.k_fac)}
        g0 = np.where(start >= 0, GID[np.clip(start, 0, None)], -1)
        for j in range(NG):
            f0[f"L{j}"] = self._conv(np.where(g0 == j, e.lot, 0.0), e.k_walk)
        f0["T"] = sum(f0[f"L{j}"] for j in range(NG))
        a0 = self._access(f0)
        D0 = float(res0[mask].sum())
        # the shares enter as one weighted mean, or one per pillar (for trade-offs between pillars)
        pillar_of = {i.key: i.pillar for i in INDICATORS}
        if by_pillar:
            groups = [{"pillar": p, "w": {k: ws[k] for k in SHARES if pillar_of[k] == p and ws[k]}} for p in PILLARS]
            groups = [g for g in groups if g["w"]]
        else:
            groups = [{"pillar": None, "w": {k: ws[k] for k in SHARES if ws[k]}}]
        A0g, tau0g, pconst = [], [], {}
        for g in groups:
            A0 = sum(wk * a0[k] for k, wk in g["w"].items()) if g["w"] else np.zeros_like(R0)
            tau0 = float((R0 * A0).sum() / D0) if D0 > 0 else 0.0
            A0g.append(A0); tau0g.append(tau0)
            key = g["pillar"] or "all"
            pconst[key] = pconst.get(key, 0.0) + tau0 - sum(wk * base[k] for k, wk in g["w"].items()
                                                           if np.isfinite(base[k]))
        const = sum(pconst.values())
        # pairs within each radius of each cell (Euclidean disks on cell centres, as the kernels)
        pc = np.c_[pairs.cell // e.nx, pairs.cell % e.nx].astype(float)
        cc = np.c_[cells // e.nx, cells % e.nx].astype(float)
        near = {}
        for name, kern in (("walk", e.k_walk), ("fac", e.k_fac)):
            rad = max(dy * dy + hw * hw for dy, hw in self._rows(kern)) ** 0.5
            near[name] = (cKDTree(pc).query_ball_point(cc, rad + 1e-9) if len(pc) else [[] for _ in cells])
            near[name] = [np.asarray(v, dtype=int) for v in near[name]]
        prep = {"cfg": cfg, "start": start, "mask": mask, "pairs": pairs, "totals": totals, "ws": ws, "const": const,
                "groups": groups, "A0g": A0g, "tau0g": tau0g, "pillar_const": pconst,
                "cells": cells, "R0": R0, "D0": D0, "f0": f0, "a0": a0, "near": near,
                "budget": budget,
                "fit": None}
        if self.sug.suit is not None and cfg.w_fit > 0:
            lp = np.log(np.clip(self.sug.suit, 1e-4, 1))
            prep["fit"] = cfg.w_fit * (lp[parcel, new] - lp[parcel, start[parcel]])
        prep["ranges"] = self._ranges(prep)
        lo = D0 + self._budget_sum(pairs.parcel, d["res"], budget, low=True)
        hi = D0 + self._budget_sum(pairs.parcel, d["res"], budget, low=False)
        prep["D_range"] = (max(lo, 1e-9), max(hi, lo + 1e-9))
        return prep

    def _access(self, f: dict) -> dict:
        """Access values per cell from the fields within the radii (ImpactEngine.access, per cell)."""
        e = self.e
        park = (f["open"] >= e.park_min).astype(float)
        serv = np.where(f["rw"] > 1, np.clip(np.divide(f["serv"], f["rw"], out=np.zeros_like(f["rw"]),
                                                        where=f["rw"] > 1) / e.t_serv, 0, 1), 0.0)
        fac = np.where(f["rf"] > 1, np.clip(np.divide(f["fac"], f["rf"], out=np.zeros_like(f["rf"]),
                                                       where=f["rf"] > 1) / e.t_fac, 0, 1), 0.0)
        L = np.stack([f[f"L{j}"] for j in range(NG)])
        T = f["T"]
        s = np.divide(L, T, out=np.zeros_like(L), where=T > 0)
        H = -(s * np.log(np.where(s > 0, s, 1.0))).sum(0) / LOG_G
        green = np.divide(L[-1], T, out=np.zeros_like(T), where=T > 0)
        return {"park_access": park, "services_access": serv, "facility_access": fac, "mix": H,
                "green_cover": green}

    @staticmethod
    def _budget_sum(parcels, vals, budget, low: bool) -> float:
        """Most negative (low) or most positive sum of vals over at most `budget` parcels, one value each."""
        if not len(vals):
            return 0.0
        v = np.asarray(vals, float) if low else -np.asarray(vals, float)
        order = np.lexsort((v, parcels))
        p_sorted = np.asarray(parcels)[order]
        first = np.r_[True, p_sorted[1:] != p_sorted[:-1]]
        best = np.minimum(v[order][first], 0.0)
        tot = float(np.sort(best)[:budget].sum())
        return tot if low else -tot

    def _ranges(self, prep) -> dict:
        """Per cell: whether each access value can change, and the range of its change under the budget."""
        e = self.e
        pairs, d, f0, a0, B = prep["pairs"], prep["pairs"].d, prep["f0"], prep["a0"], prep["budget"]
        par = pairs.parcel
        out = {k: [] for k in SHARES}
        for i, c in enumerate(prep["cells"]):
            c = int(c)
            nw, nf = prep["near"]["walk"][i], prep["near"]["fac"][i]
            bs = lambda nn, f, low: self._budget_sum(par[nn], d[f][nn], B, low) if len(nn) else 0.0
            # park
            y0 = a0["park_access"][c]
            if len(nw) and np.any(d["open"][nw] != 0):
                lo, hi = f0["open"][c] + bs(nw, "open", True), f0["open"][c] + bs(nw, "open", False)
                can = (lo < e.park_min) if y0 else (hi >= e.park_min)
                out["park_access"].append((-1.0, 0.0) if (can and y0) else ((0.0, 1.0) if can else None))
            else:
                out["park_access"].append(None)
            # services and facilities
            for key, fld, rfld, nn, t in (("services_access", "serv", "rw", nw, e.t_serv),
                                          ("facility_access", "fac", "rf", nf, e.t_fac)):
                if not len(nn) or not (np.any(d["res"][nn] != 0) or np.any(d[fld][nn] != 0)):
                    out[key].append(None)
                    continue
                F_lo, F_hi = f0[fld][c] + bs(nn, fld, True), f0[fld][c] + bs(nn, fld, False)
                R_lo, R_hi = f0[rfld][c] + bs(nn, "res", True), f0[rfld][c] + bs(nn, "res", False)
                a_hi = 1.0 if R_lo <= 1 else min(1.0, max(F_hi, 0.0) / (t * R_lo))
                a_lo = 0.0 if R_lo <= 1 else float(np.clip(max(F_lo, 0.0) / (t * R_hi), 0, 1))
                out[key].append((min(a_lo - a0[key][c], 0.0), max(a_hi - a0[key][c], 0.0)))
            # mix and green cover
            if not len(nw) or not np.any(d["tv"][nw] != 0):
                out["mix"].append(None)
                out["green_cover"].append(None)
                continue
            T0 = f0["T"][c]
            T_lo, T_hi = T0 + bs(nw, "T", True), T0 + bs(nw, "T", False)
            tv = bs(nw, "tv", False)
            eps = tv / T_lo if T_lo > 0 else 1.0
            if eps <= 1 - 1 / NG:
                dh = (eps * np.log(NG - 1) + _h2(eps)) / LOG_G
            else:
                dh = 1.0
            h0 = a0["mix"][c]
            out["mix"].append((max(-h0, -dh), min(1 - h0, dh)))
            g0 = a0["green_cover"][c]
            L_lo = f0[f"L{NG - 1}"][c] + bs(nw, f"L{NG - 1}", True)
            L_hi = f0[f"L{NG - 1}"][c] + bs(nw, f"L{NG - 1}", False)
            g_hi = 1.0 if T_lo <= 0 else min(1.0, max(L_hi, 0) / T_lo)
            g_lo = 0.0 if T_hi <= 0 else max(0.0, L_lo / T_hi)
            out["green_cover"].append((min(g_lo - g0, 0.0), max(g_hi - g0, 0.0)))
        return out

    # ------------------------------------------------------------------ the model
    def _build(self, prep, budget, interval, k_exact, exact_sets, tangents, objective: dict | None = None,
               cut_share: float = 0.01, n_tangents: int = 4):
        e = self.e
        cfg, pairs = prep["cfg"], prep["pairs"]
        d, nq = pairs.d, len(pairs.parcel)
        par = pairs.parcel
        m = _Model()
        obj_x = -cfg.conversion_penalty * np.ones(nq)
        if prep["fit"] is not None:
            obj_x = obj_x + prep["fit"]
        x = np.array([m.var(0, 1, float(obj_x[q]), integer=True) for q in range(nq)], dtype=int)
        # one change per parcel, and the budget
        order = np.argsort(par, kind="stable")
        cuts = np.r_[0, np.nonzero(np.diff(par[order]))[0] + 1, nq]
        for a_, b_ in zip(cuts[:-1], cuts[1:]):
            if b_ - a_ > 1:
                m.row([(int(x[q]), 1.0) for q in order[a_:b_]], ub=1.0)
        m.row([(int(j), 1.0) for j in x], ub=float(budget))
        if prep.get("plaus") is not None:
            lik, pmin = prep["plaus"]
            m.row([(int(x[q]), float(lik[par[q]] - pmin)) for q in range(nq)], lb=0.0)

        # totals, clipped at +-100; each score enters its pillar's terms
        pillar_terms: dict[str, list] = {p: [] for p in (*PILLARS, "all")}
        for t in prep["totals"]:
            nz = np.nonzero(t["coef"])[0]
            lo = t["r0"] + self._budget_sum(par, t["coef"], budget, low=True)
            hi = t["r0"] + self._budget_sum(par, t["coef"], budget, low=False)
            mvar = m.var(-INF, min(100.0, hi))
            m.row([(mvar, 1.0)] + [(int(x[q]), -float(t["coef"][q])) for q in nz], ub=t["r0"])
            score = mvar
            if lo < -100:  # s = max(m, -100) needs a binary
                score = m.var(-100.0, 100.0)
                b = m.var(0, 1, 0.0, integer=True)
                m.row([(score, 1.0), (mvar, -1.0), (b, -(100.0 - lo))], ub=0.0)
                m.row([(score, 1.0), (b, 200.0)], ub=100.0)
            pillar_terms[t["pillar"]].append((score, t["w"]))

        ws, f0, a0, rg = prep["ws"], prep["f0"], prep["a0"], prep["ranges"]
        cells = prep["cells"]
        fields = ["open", "serv", "res", "fac", "res+", "res-", "T+", "T-"] + [f"L{j}" for j in range(NG)]
        prefix = self._prefix(m, x, pairs, fields)

        def disk(field, c, kernel, scale=1.0):
            out = []
            y0_, x0_ = divmod(int(c), e.nx)
            look = prefix[field]
            for dy, hw in self._rows(kernel):
                yy = y0_ + dy
                if yy < 0 or yy >= e.ny:
                    continue
                hi_, lo_ = look(yy, min(e.nx - 1, x0_ + hw)), look(yy, max(0, x0_ - hw) - 1)
                if hi_ is not None:
                    out.append((hi_, scale))
                if lo_ is not None:
                    out.append((lo_, -scale))
            return out

        groups = prep["groups"]
        alpha = [dict() for _ in groups]  # per group: cell -> (column, lower, upper) of the composite access change
        comps = {}  # cell -> share -> (column, lower, upper[, park start])
        near_w, near_f = prep["near"]["walk"], prep["near"]["fac"]
        for i, c in enumerate(cells):
            c = int(c)
            comp = {}  # share -> (column, lower, upper[, start value of the park binary])
            nw, nf = near_w[i], near_f[i]
            # park
            r = rg["park_access"][i]
            if ws["park_access"] and r is not None:
                y = m.var(0, 1, 0.0, integer=True)
                m.row([(y, e.park_min)] + disk("open", c, e.k_walk, -1.0), ub=float(f0["open"][c]))
                if not a0["park_access"][c]:
                    # cover inequality: a cell gains access only through open space added within its walk, in
                    # proportion to how much of the shortfall each addition covers (tight for one addition)
                    need = e.park_min - float(f0["open"][c])
                    adds = [q for q in nw if d["open"][q] > 0]
                    m.row([(y, 1.0)] + [(int(x[q]), -min(1.0, float(d["open"][q]) / need)) for q in adds], ub=0.0)
                comp["park_access"] = (y, r[0], r[1], float(a0["park_access"][c]))  # alpha_park = y - y0
            # services and facilities: t RW0 alpha + t a0 dRW + t [alpha dRW] - dF <= F0 - t a0 RW0
            for key, fld, rfld, kern, nn, t, ex in (
                    ("services_access", "serv", "rw", e.k_walk, nw, e.t_serv, "serv"),
                    ("facility_access", "fac", "rf", e.k_fac, nf, e.t_fac, "fac")):
                r = rg[key][i]
                if not ws[key] or r is None:
                    continue
                # within this residents interval, residents within the radius rise by at least the interval's
                # minimum minus the most that can be added outside the radius: a tighter cap on the access here
                out_mask = np.ones(len(par), bool)
                out_mask[nn] = False
                out_plus = self._budget_sum(par[out_mask], d["res"][out_mask], budget, low=False)
                in_minus = self._budget_sum(par[nn], d["res"][nn], budget, low=True)
                R_lo = float(f0[rfld][c]) + max(in_minus, interval[0] - prep["D0"] - out_plus)
                F_hi = float(f0[fld][c]) + self._budget_sum(par[nn], d[fld][nn], budget, low=False)
                a_hi = 1.0 if R_lo <= 1 else min(1.0, max(F_hi, 0.0) / (t * R_lo))
                r = (r[0], max(r[0], min(r[1], a_hi - float(a0[key][c]))))
                av = m.var(r[0], r[1])
                qs = nn[d["res"][nn] != 0]
                prod = self._products(m, av, r[0], r[1], x, qs, d["res"], par, budget,
                                      exact_sets[ex].get(c, set()), k_exact,
                                      lambda sg: disk("res" + sg, c, kern, 1.0))
                aa = float(a0[key][c])
                m.row([(av, t * f0[rfld][c])] + disk("res", c, kern, t * aa) + [(j, t * v) for j, v in prod]
                      + disk(fld, c, kern, -1.0), ub=float(f0[fld][c] - t * aa * f0[rfld][c]))
                # conditional bounds: if a pair that adds many residents nearby is chosen, the access here is at
                # most its value with that pair in the plan and the budget's most favourable other changes. Each
                # cut is valid on its own (at x = 0 it is the unconditional bound); together they keep a fractional
                # relaxation from ignoring dilution.
                if cut_share and len(qs):
                    RW0, F0 = float(f0[rfld][c]), float(f0[fld][c])
                    F_more = self._budget_sum(par[nn], d[fld][nn], budget, low=False)
                    R_less = self._budget_sum(par[nn], d["res"][nn], budget, low=True)
                    for q in qs[d["res"][qs] >= cut_share * max(RW0, 1.0)]:
                        R_lo = RW0 + float(d["res"][q]) + R_less
                        F_hi = F0 + float(d[fld][q]) + F_more
                        a_hi = 1.0 if R_lo <= 1 else min(1.0, max(F_hi, 0.0) / (t * R_lo))
                        cap = a_hi - aa
                        if cap < r[1] - 1e-6:
                            m.row([(av, 1.0), (int(x[q]), -(cap - r[1]))], ub=r[1])
                comp[key] = (av, r[0], r[1])
            # mix and green cover: products with the grouped-land change dT
            for key in ("mix", "green_cover"):
                r = rg[key][i]
                if not ws[key] or r is None:
                    continue
                av = m.var(r[0], r[1])
                qs = nw[d["T"][nw] != 0]
                prod = self._products(m, av, r[0], r[1], x, qs, d["T"], par, budget,
                                      exact_sets["land"].get(c, set()), k_exact,
                                      lambda sg: disk("T" + sg, c, e.k_walk, 1.0))
                T0 = float(f0["T"][c])
                dT = [t_ for j in range(NG) for t_ in disk(f"L{j}", c, e.k_walk, 1.0)]
                h = float(a0[key][c])
                if key == "green_cover":
                    m.row([(av, T0)] + [(j, h * v) for j, v in dT] + prod
                          + disk(f"L{NG - 1}", c, e.k_walk, -1.0), ub=float(f0[f"L{NG - 1}"][c] - h * T0))
                else:
                    L0 = np.array([f0[f"L{j}"][c] for j in range(NG)])
                    # tangents at today's shares and at the shares after each of the largest land changes nearby
                    tg = [self._tangent(L0)]
                    big = nw[np.argsort(-d["tv"][nw])][:n_tangents] if len(nw) else []
                    for q in big:
                        if d["tv"][q] > 0:
                            tg.append(self._tangent(L0 + np.array([d[f"L{j}"][q] for j in range(NG)])))
                    for s in tg + tangents.get(c, []):
                        coef = -np.log(s)
                        terms = [(av, LOG_G * T0)] + [(j, LOG_G * h * v) for j, v in dT] + \
                                [(j, LOG_G * v) for j, v in prod]
                        for j in range(NG):
                            terms += disk(f"L{j}", c, e.k_walk, -float(coef[j]))
                        m.row(terms, ub=float((coef * L0).sum() - LOG_G * h * T0))
                comp[key] = (av, r[0], r[1])
            comps[c] = comp
            for gi, g in enumerate(groups):
                terms, cL, cU, rhs = [], 0.0, 0.0, 0.0
                for key, wk in g["w"].items():
                    if wk and key in comp:
                        col, lo_, hi_ = comp[key][:3]
                        terms.append((col, -wk))
                        cL += wk * lo_; cU += wk * hi_
                        if key == "park_access":
                            rhs -= wk * comp[key][3]
                if terms:
                    ac = m.var(cL, cU)
                    m.row([(ac, 1.0)] + terms, lb=rhs, ub=rhs)
                    alpha[gi][c] = (ac, cL, cU)

        # residents within the interval
        R0, D0 = prep["R0"], prep["D0"]
        qres = np.nonzero(d["res"])[0]
        dl, dh = interval
        m.row([(int(x[q]), float(d["res"][q])) for q in qres], lb=dl - D0, ub=dh - D0)
        for gi, g in enumerate(groups):
            A0, tau0 = prep["A0g"][gi], prep["tau0g"][gi]
            # N' = sum_c R0 alpha_c + sum_q dres_q x_q (A0 - tau0) + sum_q dres_q (x_q alpha_cell(q))
            Np = m.var(-INF, INF)
            terms = [(Np, 1.0)]
            NL, NU = 0.0, 0.0
            for c, (ac, cL, cU) in alpha[gi].items():
                if R0[c]:
                    terms.append((ac, -float(R0[c])))
                    NL += R0[c] * cL; NU += R0[c] * cU
            lin = d["res"][qres] * (A0[pairs.cell[qres]] - tau0)
            per_q_lo, per_q_hi = lin.copy(), lin.copy()
            for k, q in enumerate(qres):
                dr = float(d["res"][q])
                terms.append((int(x[q]), -float(lin[k])))
                a = alpha[gi].get(int(pairs.cell[q]))
                if a is not None:
                    ac, cL, cU = a
                    p = _mc(m, ac, cL, cU, int(x[q]), "upper" if dr > 0 else "lower")
                    terms.append((p, -dr))
                    per_q_lo[k] += min(dr * cL, dr * cU); per_q_hi[k] += max(dr * cL, dr * cU)
            m.row(terms, lb=0.0, ub=0.0)
            NL += self._budget_sum(par[qres], per_q_lo, budget, low=True)
            NU += self._budget_sum(par[qres], per_q_hi, budget, low=False)
            # delta <= N' / dl (delta >= 0) or N' / dh (delta <= 0), and exactly delta x D = N' (exact at binary x).
            # The weighted mean share stays within [0, sum of the group's weights], so delta does too.
            Wg = float(sum(g["w"].values()))
            dL = max(min(NL / dl, NL / dh), -tau0)
            dU = min(max(NU / dl, NU / dh), Wg - tau0)
            dL, dU = min(dL, 0.0), max(dU, 0.0)
            delta = m.var(dL, dU)
            terms = [(delta, D0), (Np, -1.0)]
            for q in qres:  # P = delta x_q, bounded on both sides
                pl = _mc(m, delta, min(dL, 0.0), max(dU, 0.0), int(x[q]), "lower")
                m.row([(pl, 1.0), (delta, -1.0), (int(x[q]), -min(dL, 0.0))], ub=-min(dL, 0.0))
                m.row([(pl, 1.0), (int(x[q]), -max(dU, 0.0))], ub=0.0)
                terms.append((pl, float(d["res"][q])))
            m.row(terms, lb=0.0, ub=0.0)
            if dU <= 0:
                m.row([(delta, 1.0), (Np, -1.0 / dh)], ub=0.0)
            elif dL >= 0:
                m.row([(delta, 1.0), (Np, -1.0 / dl)], ub=0.0)
            else:  # sign of delta: s = 1 when delta >= 0; the slack terms are bounded through delta's range
                sg = m.var(0, 1, 0.0, integer=True)
                M1 = -dL * (dh / dl - 1)  # delta <= N' / dl + M1 when delta < 0
                M2 = dU * (1 - dl / dh)  # delta <= N' / dh + M2 when delta >= 0
                m.row([(delta, 1.0), (sg, -dU)], ub=0.0)
                m.row([(delta, 1.0), (sg, dL)], lb=dL)
                m.row([(delta, 1.0), (Np, -1.0 / dl), (sg, M1)], ub=M1)
                m.row([(delta, 1.0), (Np, -1.0 / dh), (sg, -M2)], ub=0.0)
            pillar_terms[g["pillar"] or "all"].append((delta, 1.0))

        # the objective: J (weights), one pillar above floors on the others (epsilon), or the weakest pillar
        consts = prep["pillar_const"]
        spec = objective or {"weights": None}
        const = 0.0
        if "weights" in spec:
            lam = spec["weights"] or {}
            for p_, terms in pillar_terms.items():
                l_ = 1.0 if p_ == "all" else float(lam.get(p_, 1.0))
                for j, v in terms:
                    m.c[j] += l_ * v
                const += l_ * consts.get(p_, 0.0)
        elif "epsilon" in spec:
            sp = spec["epsilon"]
            rho = float(sp.get("rho", 1e-3))
            for p_, terms in pillar_terms.items():
                l_ = 1.0 if p_ == sp["maximize"] else rho
                for j, v in terms:
                    m.c[j] += l_ * v
                const += l_ * consts.get(p_, 0.0)
            for q_, val in sp["floors"].items():
                m.row(pillar_terms[q_], lb=float(val) - consts.get(q_, 0.0))
        else:
            z = m.var(-INF, INF, 1.0)
            for p_ in spec["maxmin"]:
                m.row(pillar_terms[p_] + [(z, -1.0)], lb=-consts.get(p_, 0.0))
        return m, {"x": x, "alpha": alpha, "comps": comps, "const": const, "pillar_terms": pillar_terms}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _tangent(L: np.ndarray) -> np.ndarray:
        """A strictly positive distribution near the shares L / sum(L) (Gibbs' inequality holds for any)."""
        tot = L.sum()
        s = L / tot if tot > 0 else np.full(len(L), 1.0 / len(L))
        s = np.maximum(s, 1e-6)
        return s / s.sum()

    def _products(self, m, a, aL, aU, x, qs, dq, par, budget, exact, k_exact, disk_terms):
        """Terms for a x sum_{q in qs} dq[q] x[q], to appear with a positive coefficient on the <= side: exact
        products for the exact set (the given pairs plus the k_exact parcels with the largest |dq| near the cell)
        and a McCormick lower envelope of a x (the rest), the rest being the disk sum minus the exact pairs."""
        if not len(qs):
            return []
        mag = np.abs(dq[qs])
        top_parcels = []
        for q in qs[np.argsort(-mag)]:
            p = int(par[q])
            if p not in top_parcels:
                top_parcels.append(p)
            if len(top_parcels) >= k_exact:
                break
        tp = set(top_parcels)
        ex = [int(q) for q in qs if int(par[q]) in tp or int(q) in exact]
        exs = set(ex)
        rest = [int(q) for q in qs if int(q) not in exs]
        out = []
        for q in ex:
            v = float(dq[q])
            out.append((_mc(m, a, aL, aU, int(x[q]), "lower" if v > 0 else "upper"), v))
        rest = np.asarray(rest, dtype=int)
        for sg in ("+", "-"):
            part = rest[(dq[rest] > 0) if sg == "+" else (dq[rest] < 0)] if len(rest) else rest
            if not len(part):
                continue
            # X = this sign's part of the disk sum minus its exact pairs, in [0, XU] or [XL, 0]; lower envelope of
            # a x X, exact when X = 0: z >= aL X + XL a - aL XL and z >= aU X + XU a - aU XU
            XL = self._budget_sum(par[part], dq[part], budget, low=True) if sg == "-" else 0.0
            XU = self._budget_sum(par[part], dq[part], budget, low=False) if sg == "+" else 0.0
            Xterms = disk_terms(sg) + [(int(x[q]), -float(dq[q])) for q in ex
                                       if (dq[q] > 0 if sg == "+" else dq[q] < 0)]
            z = m.var(-INF, INF)
            m.row([(z, 1.0), (a, -XL)] + [(j, -aL * v) for j, v in Xterms], lb=-aL * XL)
            m.row([(z, 1.0), (a, -XU)] + [(j, -aU * v) for j, v in Xterms], lb=-aU * XU)
            out.append((z, 1.0))
        return out

    def _prefix(self, m, x, pairs, fields):
        """Row prefix sums of each change field: P[y, x] = sum of the field's changes in cells (y, 0..x).
        Returns field -> lookup(y, x) giving the column of P[y, x] (None when it is zero)."""
        e = self.e
        out = {}
        for f in fields:
            dv = pairs.d[f]
            nz = np.nonzero(dv)[0]
            by_cell: dict[int, list[int]] = {}
            for q in nz:
                by_cell.setdefault(int(pairs.cell[q]), []).append(int(q))
            table: dict[int, tuple[list, list]] = {}
            for c in sorted(by_cell):
                yy, xx = divmod(c, e.nx)
                cols, vars_ = table.setdefault(yy, ([], []))
                P = m.var(-INF, INF)
                terms = [(P, 1.0)] + ([(vars_[-1], -1.0)] if vars_ else [])
                terms += [(int(x[q]), -float(dv[q])) for q in by_cell[c]]
                m.row(terms, lb=0.0, ub=0.0)
                cols.append(xx); vars_.append(P)
            table = {k: (np.asarray(v[0]), v[1]) for k, v in table.items()}

            def look(yy, xx, table=table):
                t = table.get(yy)
                if t is None or xx < 0:
                    return None
                k = int(np.searchsorted(t[0], xx, side="right")) - 1
                return t[1][k] if k >= 0 else None

            out[f] = look
        return out

    # ------------------------------------------------------------------ refinement
    def _refine(self, prep, plan, chosen, exact_sets, tangents) -> int:
        """Exact products for the plan's pairs near every cell, and entropy tangents at the plan's shares.
        Returns how many were added."""
        e = self.e
        d = prep["pairs"].d
        act = set(int(q) for q in chosen)
        added = 0
        g = np.where(plan >= 0, GID[np.clip(plan, 0, None)], -1)
        lots = [self._conv(np.where(g == j, e.lot, 0.0), e.k_walk) for j in range(NG)]
        for i, c in enumerate(prep["cells"]):
            c = int(c)
            nw = [q for q in prep["near"]["walk"][i] if int(q) in act]
            nf = [q for q in prep["near"]["fac"][i] if int(q) in act]
            for ex, nn, key in (("serv", nw, "res"), ("fac", nf, "res"), ("land", nw, "T")):
                new = {int(q) for q in nn if d[key][q] != 0} - exact_sets[ex].get(c, set())
                if new:
                    exact_sets[ex].setdefault(c, set()).update(new)
                    added += len(new)
            if nw and prep["ws"]["mix"] and any(d["tv"][q] != 0 for q in nw):
                s = self._tangent(np.array([lots[j][c] for j in range(NG)]))
                have = tangents.setdefault(c, [])
                if not any(np.allclose(s, h, atol=1e-5) for h in have):
                    have.append(s)
                    added += 1
        return added
