"""A graph neural network that proposes the optimal plan of an area at once, trained on exact optima.

The exact optimizer (planarena.optimize.exact) certifies the optimal plan of an area in seconds to a minute; the
Studio needs a plan while the planner drags the trade-off handle. This network learns the optimizer's answers
("learning to optimize", as in neural diving, Nair et al. 2020): for an area, pillar weights and a budget it scores
every eligible parcel's options, and the plan is the top-scoring changes within the budget. It is used for previews
and as the exact search's first plan; the plan the Studio reports is always the exact one.

Data: exact optima of random areas (150-300 m around a random parcel, the area's parcels eligible as in the Studio,
a budget of 5-15% of eligible parcels and at least two, pillar weights drawn uniformly from the simplex), only
certified ones kept.
Areas in districts 101-108 train; areas in 109-112, which the network never sees, test.

Network: GraphSAGE layers over the parcel graph (adjacent, near, same zoning; planarena.models.gnn) of the area's
study area, with per-parcel inputs: lot and floor area, residents, current use, the redevelopment model's
probabilities and likely new use, the pattern model's use fit, whether the parcel is in the area and which uses are
allowed, the pillar weights, and the first-order gain of each use under those weights (planarena.optimize.pareto).
where the first-order estimate ranks each parcel's best change against the budget, and which use that is. Output: for
each eligible parcel, logits over "stay" and the nine uses. The plan is the best, by exact score, of the network's
most likely changes (at two thresholds) and the top first-order changes: a few exact evaluations.

Test: on held-out areas, the exact score of the network's plan as a share of the optimum, against the first-order
search without and with exact polishing, the time to a plan, and the exact search's time when started from the
network's plan instead of the first-order plan.

Run:  python -I -m planarena.models.policy generate | train | test     -> results/validation/policy_test.json
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

from planarena.config import PILLARS, PROCESSED, ROOT, USE_KEYS

N_USES = len(USE_KEYS)
DIR = PROCESSED / "policy"
OUT = ROOT / "results" / "validation" / "policy_test.json"
TRAIN_CD, TEST_CD = tuple(range(101, 109)), tuple(range(109, 113))
HIDDEN, LAYERS = 64, 3


def _runtime():
    from planarena.indicators.engine import load_engine
    from planarena.optimize.exact import ExactOptimizer
    from planarena.optimize.suggest import Suggester

    e = load_engine()
    sug = Suggester(e, None)
    sug.per_use_values()
    return e, sug, ExactOptimizer(sug)


def instance(e, sug, ex, sel: np.ndarray, weights: dict, budget_share: float = 0.05, time_limit: float = 60.0,
             solve: bool = True) -> dict | None:
    """Inputs of one area (and its certified optimum when solve=True)."""
    from planarena.optimize.pareto import pillar_gain_matrices
    from planarena.optimize.suggest import SuggestConfig

    mask = e.study_area(sel)
    cfg = SuggestConfig(scope="affected", candidate_parcels=sel, w_fit=0.0, pillar_weights=dict(weights), mask=mask)
    _, elig, allowed = sug.feasible(cfg, e.base_use)
    dec = np.nonzero(elig)[0]
    if len(dec) < 4:
        return None
    budget = max(2, int(budget_share * len(dec)))
    nodes = np.nonzero(mask)[0]
    G = pillar_gain_matrices(sug, dec, cfg, e.base_use, mask)  # (3, n_dec, N_USES)
    lam = np.array([weights[p] for p in PILLARS]) / max(sum(weights.values()), 1e-9)
    out = {"nodes": nodes, "decision": dec, "allowed": allowed[dec], "gains": np.tensordot(lam, G, 1),
           "weights": lam, "budget": budget, "sel": np.asarray(sel)}
    if not solve:
        return out
    cfg.max_change_share = budget / len(dec) + 1e-9
    t0 = time.time()
    fast = sug.suggest(SuggestConfig(**{**cfg.__dict__, "polish": 0}))["use"]
    t_fast = time.time() - t0
    t0 = time.time()
    pol = sug.suggest(SuggestConfig(**{**cfg.__dict__, "polish": 30}))["use"]
    t_pol = time.time() - t0
    r = ex.solve(cfg, mask=mask, budget=budget, time_limit=time_limit, incumbent=fast)
    if r["status"] != "optimal":
        return None
    label = np.zeros(len(dec), dtype=np.int64)  # 0 = stay, else 1 + new use
    ch = r["use"][dec] != e.base_use[dec]
    label[ch] = 1 + r["use"][dec][ch]
    start = e.base_use
    J = lambda u: ex.objective(u, start, cfg, mask)
    out.update(label=label, J_opt=r["objective"], J_fast=J(fast), J_polish=J(pol), t_exact=r["seconds"],
               t_fast=t_fast, t_polish=t_pol, use_fast=fast[dec], use_polish=pol[dec])
    return out


def generate(n: int, districts=TRAIN_CD, seed: int = 0, tag: str = "train") -> int:
    e, sug, ex = _runtime()
    DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    xy = np.c_[e.p.cx.to_numpy(), e.p.cy.to_numpy()].astype(float)
    pool = np.nonzero(np.isin(e.cd, districts) & (e.base_use >= 0))[0]
    k = 0
    while k < n:
        c = int(rng.choice(pool))
        rad = rng.uniform(150, 300) / 50.0  # cells of 50 m
        sel = np.nonzero((((xy - xy[c]) ** 2).sum(1) <= rad ** 2) & np.isin(e.cd, districts))[0]
        w = dict(zip(PILLARS, rng.dirichlet(np.ones(3))))
        inst = instance(e, sug, ex, sel, w, budget_share=float(rng.uniform(0.05, 0.15)))
        if inst is None:
            continue
        np.savez_compressed(DIR / f"{tag}_{seed}_{k:04d}.npz", **{kk: np.asarray(v) for kk, v in inst.items()})
        k += 1
        print(tag, k, "decision parcels", len(inst["decision"]), "budget", inst["budget"], "J*", round(inst["J_opt"], 4),
              "fast", round(inst["J_fast"], 4), "s", inst["t_exact"], flush=True)
    return k


# ------------------------------------------------------------------------- network
def _static(e) -> np.ndarray:
    """Per-parcel inputs that do not depend on the area."""
    st = e.baseline_state
    oh = np.zeros((e.n, N_USES))
    ok = e.base_use >= 0
    oh[np.nonzero(ok)[0], e.base_use[ok]] = 1.0
    cols = [np.log1p(e.lot), np.log1p(e.bldg), np.log1p(st["residents"]), oh]
    z = np.load(PROCESSED / "redevelopment.npz")
    cols += [z["p"][:, None] * 10, z["q"]]
    pat = np.load(PROCESSED / "pattern.npy") if (PROCESSED / "pattern.npy").exists() else np.zeros((e.n, N_USES))
    cols.append(pat)
    X = np.column_stack([c if c.ndim == 2 else c[:, None] for c in cols]).astype(np.float32)
    return (X - X.mean(0)) / (X.std(0) + 1e-6)


def _inputs(e, static, graph, inst):
    """Node inputs, edges of the study area's subgraph, decision rows."""
    import torch

    nodes = inst["nodes"]
    pos = -np.ones(e.n, dtype=np.int64)
    pos[nodes] = np.arange(len(nodes))
    dec = pos[inst["decision"]]
    n = len(nodes)
    inst_x = np.zeros((n, 3 + N_USES * 3 + 3 + 1 + 3), dtype=np.float32)
    insel = np.zeros(e.n, bool)
    insel[inst["sel"]] = True
    inst_x[:, 0] = insel[nodes]
    inst_x[dec, 1] = 1.0
    g = inst["gains"]
    scale = np.abs(g).max() or 1.0
    inst_x[dec, 3:3 + N_USES] = inst["allowed"]
    inst_x[dec, 3 + N_USES:3 + 2 * N_USES] = np.where(inst["allowed"], g / scale, 0.0)
    # where the first-order estimate ranks each parcel's best change against the budget, and which use it is
    gm = np.where(inst["allowed"], g, -np.inf)
    best = gm.max(1)
    best = np.where(np.isfinite(best), best, 0.0)
    rank = np.empty(len(best))
    rank[np.argsort(-best)] = np.arange(len(best))
    B = max(int(inst["budget"]), 1)
    arg = np.zeros((len(best), N_USES), dtype=np.float32)
    ok = np.isfinite(gm).any(1)
    arg[np.nonzero(ok)[0], gm[ok].argmax(1)] = 1.0
    o = 3 + 2 * N_USES
    inst_x[dec, o:o + N_USES] = arg
    inst_x[:, o + N_USES:o + N_USES + 3] = inst["weights"]
    inst_x[:, o + N_USES + 3] = inst["budget"] / max(len(dec), 1)
    inst_x[dec, o + N_USES + 4] = np.minimum(rank / B, 3.0)
    inst_x[dec, o + N_USES + 5] = (rank < B) & (best > 0)
    inst_x[dec, o + N_USES + 6] = best / scale
    x = np.concatenate([static[nodes], inst_x], 1)
    edges = {}
    for r, ei in graph.items():
        keep = (pos[ei[0]] >= 0) & (pos[ei[1]] >= 0)
        edges[("parcel", r, "parcel")] = torch.as_tensor(np.stack([pos[ei[0][keep]], pos[ei[1][keep]]]), dtype=torch.long)
    return torch.as_tensor(x), edges, torch.as_tensor(dec)


def _net(in_dim: int, hidden: int = None, layers: int = None):
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import HeteroConv, SAGEConv

    from planarena.models.gnn import RELATIONS

    hidden, layers = hidden or HIDDEN, layers or LAYERS

    class PolicyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.inp = nn.Linear(in_dim, hidden)
            self.convs = nn.ModuleList([HeteroConv({("parcel", r, "parcel"): SAGEConv(hidden, hidden)
                                                    for r in RELATIONS}, aggr="sum") for _ in range(layers)])
            self.norms = nn.ModuleList([nn.LayerNorm(hidden) for _ in range(layers)])
            self.head = nn.Sequential(nn.Linear(hidden + in_dim, hidden), nn.ReLU(), nn.Linear(hidden, 1 + N_USES))

        def forward(self, x, edges, dec):
            h = F.relu(self.inp(x))
            for conv, norm in zip(self.convs, self.norms):
                h = norm(h + F.relu(conv({"parcel": h}, edges)["parcel"]))
            return self.head(torch_cat(h[dec], x[dec]))

    def torch_cat(a, b):
        import torch

        return torch.cat([a, b], 1)

    return PolicyNet()


def _masked_logits(logits, allowed):
    import torch

    m = torch.cat([torch.ones(len(allowed), 1, dtype=torch.bool), torch.as_tensor(allowed, dtype=torch.bool)], 1)
    return logits.masked_fill(~m, -1e9)


def decode(logits, allowed, budget: int, threshold: float = 0.5) -> np.ndarray:
    """Plan from the network's scores: the most likely changes, up to the budget; returns 0 (stay) or 1 + use."""
    import torch

    lg = _masked_logits(logits, allowed)
    p = torch.softmax(lg, 1).detach().numpy()
    change = 1.0 - p[:, 0]
    best = 1 + p[:, 1:].argmax(1)
    out = np.zeros(len(p), dtype=np.int64)
    for i in np.argsort(-change)[:budget]:
        if change[i] > threshold:
            out[i] = best[i]
    return out


def candidates(logits, inst) -> list[np.ndarray]:
    """Plans to score exactly: the network's most likely changes (two thresholds) and the plan of the top changes by
    first-order gain (the network's input), each within the budget; labels 0 (stay) or 1 + use."""
    allowed, budget = inst["allowed"], int(inst["budget"])
    out = [decode(logits, allowed, budget), decode(logits, allowed, budget, threshold=0.3)]
    g = np.where(allowed, inst["gains"], -np.inf)
    best, arg = g.max(1), g.argmax(1)
    lab = np.zeros(len(g), dtype=np.int64)
    for i in np.argsort(-best)[:budget]:
        if best[i] > 0:
            lab[i] = 1 + arg[i]
    out.append(lab)
    return out


def best_plan(e, ex, cfg, mask, inst, labels: list[np.ndarray]) -> tuple[np.ndarray, float]:
    """The candidate with the highest exact score."""
    best_u, best_J = None, -np.inf
    for lab in labels:
        u = e.base_use.copy()
        ch = lab > 0
        u[inst["decision"][ch]] = lab[ch] - 1
        J = ex.objective(u, e.base_use, cfg, mask)
        if J > best_J:
            best_u, best_J = u, J
    return best_u, best_J


def _load(tag: str) -> list[dict]:
    return [dict(np.load(f, allow_pickle=False)) for f in sorted(DIR.glob(f"{tag}_*.npz"))]


def train(epochs: int = 60, seed: int = 0, n_val: int = 20) -> dict:
    """Cross-entropy on the certified optima; the epoch with the lowest loss on n_val held-back training areas is kept."""
    import copy

    import torch

    torch.manual_seed(seed)
    from planarena.indicators.engine import load_engine

    e = load_engine()
    static = _static(e)
    graph = dict(np.load(PROCESSED / "graph.npz"))
    data = [(_inputs(e, static, graph, d), d) for d in _load("train")]
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(data))
    val, fit = [data[k] for k in order[:n_val]], [data[k] for k in order[n_val:]]
    net = _net(data[0][0][0].shape[1])
    opt = torch.optim.Adam(net.parameters(), lr=2e-3, weight_decay=1e-5)
    w = torch.ones(1 + N_USES)
    w[1:] = 5.0  # changes are rare; weigh them up
    loss_of = lambda m, item: torch.nn.functional.cross_entropy(
        _masked_logits(m(*item[0]), item[1]["allowed"]), torch.as_tensor(item[1]["label"]), weight=w)
    log, best, best_state = [], np.inf, None
    for ep in range(epochs):
        net.train()
        tot = 0.0
        for k in rng.permutation(len(fit)):
            loss = loss_of(net, fit[k])
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss)
        net.eval()
        with torch.no_grad():
            v = float(np.mean([float(loss_of(net, it)) for it in val]))
        log.append({"train": tot / len(fit), "validation": v})
        if v < best:
            best, best_state, best_ep = v, copy.deepcopy(net.state_dict()), ep + 1
        print("epoch", ep + 1, "train", round(log[-1]["train"], 4), "validation", round(v, 4), flush=True)
    torch.save({"state_dict": best_state, "in_dim": data[0][0][0].shape[1], "train_instances": len(fit),
                "validation_instances": len(val), "epochs": epochs, "best_epoch": best_ep, "loss": log}, DIR / "policy.pt")
    return {"epochs": epochs, "best_epoch": best_ep, "train_instances": len(fit), "validation_instances": len(val)}


def load_policy():
    import torch

    ck = torch.load(DIR / "policy.pt", map_location="cpu")
    net = _net(ck["in_dim"])
    net.load_state_dict(ck["state_dict"])
    net.eval()
    return net


def propose(e, sug, net, static, graph, sel, weights: dict, budget_share: float = 0.05):
    """The network's plan for an area (no exact search): (use array, seconds)."""
    import torch

    t0 = time.time()
    inst = instance(e, sug, None, np.asarray(sel), weights, budget_share, solve=False)
    if inst is None:
        return e.base_use.copy(), time.time() - t0
    from planarena.optimize.exact import ExactOptimizer
    from planarena.optimize.suggest import SuggestConfig

    x, edges, dec = _inputs(e, static, graph, inst)
    with torch.no_grad():
        logits = net(x, edges, dec)
    mask = e.study_area(np.asarray(sel))
    cfg = SuggestConfig(scope="affected", w_fit=0.0, pillar_weights=dict(weights), mask=mask)
    use, _ = best_plan(e, ExactOptimizer(sug), cfg, mask, inst, candidates(logits, inst))
    return use, time.time() - t0


def test(n_warm: int = 20) -> dict:
    import torch

    from planarena.optimize.suggest import SuggestConfig

    e, sug, ex = _runtime()
    static = _static(e)
    graph = dict(np.load(PROCESSED / "graph.npz"))
    net = load_policy()
    rows = []
    for k, d in enumerate(_load("test")):
        lam = dict(zip(PILLARS, d["weights"].tolist()))
        mask = e.study_area(d["sel"])
        cfg = SuggestConfig(scope="affected", candidate_parcels=d["sel"], w_fit=0.0, pillar_weights=lam, mask=mask)
        cfg.max_change_share = int(d["budget"]) / len(d["decision"]) + 1e-9
        x, edges, dec = _inputs(e, static, graph, d)
        t0 = time.time()
        with torch.no_grad():
            logits = net(x, edges, dec)
        lab = decode(logits, d["allowed"], int(d["budget"]))
        t_net_alone = time.time() - t0
        use, Jn = best_plan(e, ex, cfg, mask, d, candidates(logits, d))
        t_net = time.time() - t0
        u1 = e.base_use.copy()
        u1[d["decision"][lab > 0]] = lab[lab > 0] - 1
        J_alone = ex.objective(u1, e.base_use, cfg, mask)
        t0 = time.time()
        fast_u = sug.suggest(SuggestConfig(**{**cfg.__dict__, "polish": 0}))["use"]
        t_fast = time.time() - t0
        t0 = time.time()
        pol_u = sug.suggest(SuggestConfig(**{**cfg.__dict__, "polish": 30}))["use"]
        t_pol = time.time() - t0
        row = {"J_opt": float(d["J_opt"]), "J_net": Jn, "J_net_alone": J_alone, "t_net_alone": t_net_alone,
               "J_fast": ex.objective(fast_u, e.base_use, cfg, mask),
               "J_polish": ex.objective(pol_u, e.base_use, cfg, mask), "t_net": t_net, "t_fast": t_fast, "t_polish": t_pol,
               "exact_labels_matched": float((lab == d["label"]).mean()), "decision": int(len(d["decision"]))}
        if k < n_warm:  # the exact search started from the network's plan, against starting from the fast plan
            r1 = ex.solve(cfg, mask=mask, budget=int(d["budget"]), time_limit=120, incumbent=use)
            r0 = ex.solve(cfg, mask=mask, budget=int(d["budget"]), time_limit=120, incumbent=fast_u)
            row.update(t_exact_from_net=r1["seconds"], t_exact_from_fast=r0["seconds"],
                       optimal_from_net=r1["status"] == "optimal", optimal_from_fast=r0["status"] == "optimal")
        rows.append(row)
        print(k, {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in row.items()}, flush=True)
    pos = [r for r in rows if r["J_opt"] > 1e-9]
    share = lambda key: float(np.median([max(r[key], 0.0) / r["J_opt"] for r in pos]))
    mean_share = lambda key: float(np.mean([max(r[key], 0.0) / r["J_opt"] for r in pos]))
    warm = [r for r in rows if "t_exact_from_net" in r]
    res = {"test": __doc__.strip().split("\n\n")[1].replace("\n", " "), "test_instances": len(rows),
           "train_instances": int(torch.load(DIR / "policy.pt", map_location="cpu")["train_instances"]),
           "layers": LAYERS, "hidden": HIDDEN,
           "positive_optimum": len(pos),
           "share_of_optimum": {"median": {"network": share("J_net"), "first_order": share("J_fast"),
                                           "first_order_polished": share("J_polish")},
                                "mean": {"network": mean_share("J_net"), "first_order": mean_share("J_fast"),
                                         "first_order_polished": mean_share("J_polish")}},
           "network_alone": {"median_share": share("J_net_alone"), "mean_share": mean_share("J_net_alone"),
                             "optimum_reached": float(np.mean([r["J_net_alone"] >= r["J_opt"] - 1e-6 for r in pos])),
                             "median_seconds": float(np.median([r["t_net_alone"] for r in rows]))},
           "optimum_reached": {"network": float(np.mean([r["J_net"] >= r["J_opt"] - 1e-6 for r in pos])),
                               "first_order": float(np.mean([r["J_fast"] >= r["J_opt"] - 1e-6 for r in pos])),
                               "first_order_polished": float(np.mean([r["J_polish"] >= r["J_opt"] - 1e-6 for r in pos]))},
           "median_seconds": {"network": float(np.median([r["t_net"] for r in rows])),
                              "first_order": float(np.median([r["t_fast"] for r in rows])),
                              "first_order_polished": float(np.median([r["t_polish"] for r in rows]))},
           "warm_start": {"instances": len(warm),
                          "median_exact_seconds_from_network": float(np.median([r["t_exact_from_net"] for r in warm])) if warm else None,
                          "median_exact_seconds_from_first_order": float(np.median([r["t_exact_from_fast"] for r in warm])) if warm else None},
           "rows": rows}
    OUT.write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "generate":
        tag = sys.argv[2] if len(sys.argv) > 2 else "train"
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        generate(n, TRAIN_CD if tag == "train" else TEST_CD, seed, tag)
    elif cmd == "train":
        print(train())
    else:
        r = test()
        print({k: v for k, v in r.items() if k != "rows"})
