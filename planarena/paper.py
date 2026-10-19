"""The paper, with every number and table taken from the result files (like planarena/report.py for the docs).

paper/paper.tex.in holds the text; each @@name@@ in it is filled from values() or tables() below, which read only
results/validation/*.json. A test fails if paper/paper.tex is out of date, if a placeholder is left unfilled, or if a
citation is not in docs/refs.bib.

Run:  python -I -m planarena.paper            -> paper/paper.tex (and paper/paper.pdf when tectonic is installed)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import numpy as np

from planarena.config import ROOT

RES = ROOT / "results" / "validation"
PAPER = ROOT / "paper"
TEMPLATE = PAPER / "paper.tex.in"
OUT = PAPER / "paper.tex"

# the test cities, in the order of the tables
CITY = {"0644000": "Los Angeles", "4819000": "Dallas", "3651000": "New York", "5553000": "Milwaukee",
        "0455000": "Phoenix", "0666000": "San Diego", "1714000": "Chicago"}
OUTCOME = {"0644000": "new building or floor area +25\\%", "4819000": "new building or floor area +25\\%",
           "3651000": "new building or floor area +25\\%", "5553000": "new building",
           "0455000": "change of use group", "0666000": "change of use group", "1714000": "new-construction permit"}
OUTCOME_SOURCE = {"0644000": "county assessor rolls", "4819000": "appraisal district files", "3651000": "MapPLUTO",
                  "5553000": "MPROP", "0455000": "MAG land-use inventory", "0666000": "SANDAG land-use inventory",
                  "1714000": "building permits"}
# the ten cities: short source descriptions (README, "Cities")
TEN = {"3651000": ("New York", "MapPLUTO (City Planning)", "none citywide"),
       "0644000": ("Los Angeles", "SCAG 2020; county assessor", "General Plan (SCAG 2019)"),
       "1714000": ("Chicago", "CMAP 2023; county assessor", "none citywide"),
       "4835000": ("Houston", "City (appraisal codes)", "none"),
       "0455000": ("Phoenix", "County assessor; MAG", "General Plan"),
       "4260000": ("Philadelphia", "City Planning Commission; OPA", "district plans (digitised PDF)"),
       "4865000": ("San Antonio", "Bexar Appraisal District", "adopted area plans"),
       "0666000": ("San Diego", "SANDAG 2025; county assessor", "General and community plans"),
       "4819000": ("Dallas", "City 2026; DCAD", "forwardDallas! 2.0"),
       "5553000": ("Milwaukee", "MPROP", "PDF only (not included)")}


def _load(name: str):
    return json.loads((RES / f"{name}.json").read_text())


def _f(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}"


def _sg(x: float, d: int = 3) -> str:
    if round(abs(x), d) == 0:
        return f"{0:.{d}f}"
    return ("+" if x >= 0 else "$-$") + f"{abs(x):.{d}f}"


def _num(x: float, d: int = 2) -> str:
    """A signed number with a typographic minus, and no negative zero."""
    if round(abs(x), d) == 0:
        return f"{0:.{d}f}"
    return ("$-$" if x < 0 else "") + f"{abs(x):.{d}f}"


WORDS = "zero one two three four five six seven eight nine ten".split()


def _w(n: int) -> str:
    return WORDS[n] if 0 <= n <= 10 else str(n)


def _of(k: int, n: int) -> str:
    """'four of seven', or 'all five' when every case qualifies."""
    return f"all {_w(n)}" if k == n else f"{_w(k)} of {_w(n)}"


def _ratio(x: float) -> str:
    return f"{x:.1f}" if x < 10 else f"{x:.0f}"


def _n(x: float) -> str:
    return f"{x:,.0f}".replace(",", "{,}")


def _pct(x: float, d: int = 0) -> str:
    return f"{100 * x:.{d}f}\\%"


def _times(x: float) -> str:
    return f"{x:.2f}$\\times$" if x < 10 else f"{x:.0f}$\\times$"


def _list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _gain(g: dict | None, key: str):
    """(value, low, high, significant) of a gain in AUC, or None."""
    if not g or key not in g:
        return None
    v, (lo, hi) = g[key]["auc"]
    return v, lo, hi, lo > 0 or hi < 0


def _gtex(t) -> str:
    if t is None:
        return "--"
    v, lo, hi, sig = t
    s = f"{_sg(v)} [{_f(lo) if lo >= 0 else _sg(lo)}, {_f(hi) if hi >= 0 else _sg(hi)}]"
    return f"\\textbf{{{s}}}" if sig else s


def _data():
    integ = _load("integration_cities")
    cities = [g for g in CITY if g in integ]
    return integ, cities


# ----------------------------------------------------------------------------- values
def values() -> dict[str, str]:
    integ, cities = _data()
    T = {g: integ[g]["temporal"] for g in cities}
    layers = _load("cities_layers")
    V: dict[str, str] = {}

    # ten cities
    parcels = sum(v["parcels"] for v in layers.values())
    V["n_cities"] = str(len(layers))
    V["parcels_total"] = _n(parcels)
    V["parcels_total_m"] = f"{parcels / 1e6:.1f}"
    ratios = [v["homes_twin"] / v["homes_census_2020"] for v in layers.values() if v.get("homes_census_2020")]
    V["homes_ratio_lo"], V["homes_ratio_hi"] = _f(min(ratios), 2), _f(max(ratios), 2)
    with_plan = [g for g, v in layers.items() if v["plan"] > 0]
    with_zone = [g for g, v in layers.items() if v["zoning"] > 0]
    V["n_with_plan"], V["n_with_zoning"] = str(len(with_plan)), str(len(with_zone))
    match = [v["plan_matches_existing_group"] for g, v in layers.items() if v.get("plan_matches_existing_group")]
    V["plan_match_lo"], V["plan_match_hi"] = _pct(min(match)), _pct(max(match))

    # Philadelphia's digitised plan
    phl = layers["4260000"]
    dig = phl["plan_digitised"]
    used = {k: v for k, v in dig.items() if v.get("used")}
    n_plans = sum(len(k.split(" + ")) for k in dig)  # districts
    V["phl_districts"] = str(n_plans)
    V["phl_districts_used"] = str(sum(len(k.split(" + ")) for k in used))
    V["phl_maps"], V["phl_maps_used"] = str(len(dig)), str(len(used))
    V["phl_not_used"] = _list(sorted(k for k, v in dig.items() if not v.get("used")))
    V["phl_share"] = _pct(phl["plan"])
    err = [v["median_error_ft"] for v in used.values()]
    V["phl_err_lo"], V["phl_err_hi"] = _f(min(err), 1), _f(max(err), 1)
    V["phl_err_median"] = _f(float(np.median(err)), 1)
    cov = [v["coverage"] for v in used.values()]
    V["phl_cov_lo"], V["phl_cov_hi"] = _pct(min(cov)), _pct(max(cov))
    ag = [v["agreement_with_existing"] for v in used.values()]
    sh = [v["agreement_if_shifted_300ft"] for v in used.values()]
    V["phl_agree_lo"], V["phl_agree_hi"] = _pct(min(ag)), _pct(max(ag))
    V["phl_shift_lo"], V["phl_shift_hi"] = _pct(min(sh)), _pct(max(sh))
    V["phl_margin_min"] = _f(100 * min(a - b for a, b in zip(ag, sh)), 0)

    # test panels
    V["n_test"] = str(len(cities))
    V["test_lots"] = _n(sum(T[g]["n_lots"] for g in cities))
    V["test_developed"] = _n(sum(T[g]["developed"] for g in cities))
    br = [T[g]["sets"]["E"]["base_rate"] for g in cities]
    V["base_lo"], V["base_hi"] = _pct(min(br), 2), _pct(max(br), 1)
    aucE = [T[g]["sets"]["E"]["auc"] for g in cities]
    V["auc_E_lo"], V["auc_E_hi"] = _f(min(aucE)), _f(max(aucE))
    V["auc_E_lo_city"] = CITY[cities[int(np.argmin(aucE))]]
    rest = [a for a in aucE if a != min(aucE)]
    V["auc_E_rest_lo"] = _f(min(rest))
    full = {g: T[g]["sets"].get("E+C+Z+P", T[g]["sets"].get("E+C+Z"))["auc"] for g in cities}
    V["auc_full_lo"], V["auc_full_hi"] = _f(min(full.values())), _f(max(full.values()))

    # gains over the out-of-time test
    ctx = {g: _gain(T[g]["gains"], "E+C vs E") for g in cities}
    sig_pos = lambda d: [g for g, t in d.items() if t and t[3] and t[0] > 0]
    sig_neg = lambda d: [g for g, t in d.items() if t and t[3] and t[0] < 0]
    c_sig = sig_pos(ctx)
    V["n_ctx_sig"] = str(len(c_sig))
    V["ctx_sig_cities"] = _list([CITY[g] for g in c_sig])
    V["ctx_gain_lo"], V["ctx_gain_hi"] = _f(min(ctx[g][0] for g in c_sig)), _f(max(ctx[g][0] for g in c_sig))
    c_ns = [g for g in cities if g not in c_sig]
    V["ctx_ns_cities"] = _list([CITY[g] for g in c_ns])
    phx = ctx.get("0455000")
    V["phx_ctx"], V["phx_ctx_lo"], V["phx_ctx_hi"] = _sg(phx[0]), _sg(phx[1]), _sg(phx[2])
    zg = {g: _gain(T[g]["gains"], "E+C+Z vs E+C") for g in cities}
    pg = {g: _gain(T[g]["gains"], "E+C+P vs E+C") for g in cities}
    zg = {g: t for g, t in zg.items() if t}
    pg = {g: t for g, t in pg.items() if t}
    z_sig, p_sig = sig_pos(zg), sig_pos(pg)
    V["n_z"], V["n_p"] = str(len(zg)), str(len(pg))
    V["n_z_sig"], V["n_p_sig"] = str(len(z_sig)), str(len(p_sig))
    V["z_sig_cities"], V["p_sig_cities"] = _list([CITY[g] for g in z_sig]), _list([CITY[g] for g in p_sig])
    V["z_sig_lo"], V["z_sig_hi"] = _f(min(zg[g][0] for g in z_sig)), _f(max(zg[g][0] for g in z_sig))
    V["p_sig_lo"], V["p_sig_hi"] = _f(min(pg[g][0] for g in p_sig)), _f(max(pg[g][0] for g in p_sig))
    small = [zg[g][0] for g in z_sig if g != "0455000"] + [pg[g][0] for g in p_sig if g != "0455000"]
    V["zp_small_max"] = _f(max(small))
    V["phx_z"], V["phx_p"] = _f(zg["0455000"][0]), _f(pg["0455000"][0])
    V["z_ns_cities"] = _list([CITY[g] for g in zg if g not in z_sig])
    V["p_ns_cities"] = _list([CITY[g] for g in pg if g not in p_sig])
    V["n_neg_sig"] = str(len(sig_neg(zg)) + len(sig_neg(pg)))
    la = T["0644000"]["gains"]
    V["la_zp"] = _sg(la["E+C+Z+P vs E+C"]["auc"][0])
    # best block set per city (out of time)
    best = {g: max(T[g]["sets"], key=lambda k: T[g]["sets"][k]["auc"]) for g in cities}
    V["n_best_has_C"] = str(sum("C" in best[g] for g in cities))
    phx_sets = T["0455000"]["sets"]
    V["phx_best_set"] = best["0455000"].replace("+", "{+}")
    V["phx_best_auc"] = _f(phx_sets[best["0455000"]]["auc"])

    # zoning and plan without context, and what distinguishes developed lots
    zE = {g: _gain(T[g]["gains"], "E+Z vs E") for g in cities}
    zE = {g: t for g, t in zE.items() if t}
    zE_sig = sig_pos(zE)
    V["n_zE_sig"], V["n_zE"] = str(len(zE_sig)), str(len(zE))
    V["zE_lo"], V["zE_hi"] = _f(min(zE[g][0] for g in zE_sig)), _f(max(zE[g][0] for g in zE_sig))
    prof = _load("integration_profile")
    zr = [prof[g]["zone_differs"]["developed"] / prof[g]["zone_differs"]["all"] for g in cities if "zone_differs" in prof[g]]
    vr = [prof[g]["vacant"]["developed"] / prof[g]["vacant"]["all"] for g in cities]
    V["zdiff_ratio_lo"], V["zdiff_ratio_hi"] = _ratio(min(zr)), _ratio(max(zr))
    V["vac_ratio_lo"], V["vac_ratio_hi"] = _ratio(min(vr)), _ratio(max(vr))
    ph = prof["0455000"]
    V["phx_vac_dev"], V["phx_vac_all"] = _pct(ph["vacant"]["developed"]), _pct(ph["vacant"]["all"])
    V["phx_zd_dev"], V["phx_zd_all"] = _pct(ph["zone_differs"]["developed"]), _pct(ph["zone_differs"]["all"])
    V["phx_pd_dev"], V["phx_pd_all"] = _pct(ph["plan_differs"]["developed"]), _pct(ph["plan_differs"]["all"])
    V["mke_dev"] = _n(T["5553000"]["developed"])
    V["existing_min"] = _pct(min(v["existing"] for v in layers.values()))
    V["neg_sentence"] = ("No layer significantly reduced performance once context was included."
                         if not sig_neg(zg) and not sig_neg(pg) else "")

    # conservative variant
    cons = {g: integ[g]["temporal_conservative"] for g in cities if integ[g].get("temporal_conservative")}
    V["n_cons"] = str(len(cons))
    V["cons_cities"] = _list([CITY[g] for g in cons])
    held, lost = {}, {}
    for g, c in cons.items():
        for key, main, name in (("E+C+Z vs E+C", zg, "zoning"), ("E+C+P vs E+C", pg, "plan")):
            if g in main and main[g][3] and main[g][0] > 0:
                t = _gain(c["gains"], key)
                (held if t and t[3] and t[0] > 0 else lost).setdefault(g, []).append(name)
    phrase = lambda d: _list([f"the {' and '.join(v)} gain{'s' if len(v) > 1 else ''} in {CITY[g]}" for g, v in d.items()])
    cap = lambda x: x[:1].upper() + x[1:]
    V["cons_held"], V["cons_lost"] = cap(phrase(held)), cap(phrase(lost))
    V["n_cons_lost"] = str(sum(len(v) for v in lost.values()))

    # spatial cross-fitting
    sp = {g: integ[g]["spatial"]["sets"] for g in cities}
    V["n_ctx_spatial_pos"] = str(sum(sp[g]["E+C"]["auc"] > sp[g]["E"]["auc"] for g in cities))
    zsp = [g for g in cities if "E+C+Z" in sp[g]]
    V["n_z_spatial_pos"] = str(sum(sp[g]["E+C+Z"]["auc"] > sp[g]["E+C"]["auc"] for g in zsp))
    V["n_z_spatial"] = str(len(zsp))

    # destination
    D = {g: T[g].get("destination") for g in cities if T[g].get("destination") and T[g]["destination"]["n"]}
    V["n_dest"] = str(len(D))
    better_z = [g for g, d in D.items() if d["layers"].get("zoning class", {}).get("coverage")
                and d["layers"]["zoning class"]["class"] > d["layers"]["existing (no change)"]["class"]]
    V["n_dest_z_better"] = str(len(better_z))
    V["n_dest_z"] = str(sum(1 for d in D.values() if d["layers"].get("zoning class", {}).get("coverage")))
    dz = [D[g]["layers"]["zoning class"]["class"] - D[g]["layers"]["existing (no change)"]["class"] for g in better_z]
    V["dest_z_lo"], V["dest_z_hi"] = _f(100 * min(dz), 0), _f(100 * max(dz), 0)
    dal = D["4819000"]["layers"]
    V["dal_plan_dest"], V["dal_zone_dest"] = _pct(dal["plan class"]["class"]), _pct(dal["zoning class"]["class"])
    V["dal_none_dest"] = _pct(dal["existing (no change)"]["class"])
    mod = {g: d["models"].get("E+C+Z+P") or d["models"].get("E+Z") for g, d in D.items()}
    best_layer = {g: max(v["class"] for k, v in d["layers"].items() if v.get("coverage")) for g, d in D.items()}
    V["n_model_beats_layers"] = str(sum(mod[g]["class"] >= best_layer[g] for g in D))

    # homes
    S = {g: T[g]["scenario"] for g in cities if T[g].get("scenario")}
    V["n_homes"] = str(len(S))
    V["homes_cities"] = _list([CITY[g] for g in S])
    bo = [S[g][k]["ratio_total"] for g in S for k in ("zoning_buildout", "plan_buildout") if k in S[g]]
    lk = [S[g][k]["ratio_total"] for g in S for k in ("likely_zoning", "likely_plan") if k in S[g]]
    V["bo_lo"], V["bo_hi"] = f"{min(bo):.0f}", f"{max(bo):.0f}"
    V["lk_lo"], V["lk_hi"] = _f(min(lk), 2), _f(max(lk), 2)
    tr_rho = [S[g]["trend"]["district_spearman"] for g in S]
    lk_rho = [max(S[g][k]["district_spearman"] for k in ("likely_zoning", "likely_plan") if k in S[g]) for g in S]
    V["trend_rho_lo"], V["trend_rho_hi"] = _num(min(tr_rho)), _num(max(tr_rho))
    V["lk_rho_lo"], V["lk_rho_hi"] = _num(min(lk_rho)), _num(max(lk_rho))
    V["n_trend_better"] = str(sum(t > l for t, l in zip(tr_rho, lk_rho)))
    tr_tot = [S[g]["trend"]["ratio_total"] for g in S]
    V["trend_tot_lo"], V["trend_tot_hi"] = _f(min(tr_tot), 2), _f(max(tr_tot), 2)

    # transfer
    tr = integ["transfer"]
    tc = [g for g in CITY if g in tr]
    worse = [g for g in tc if tr[g]["E+C+Z+P"]["other_cities"]["auc"] < tr[g]["E+C+Z+P"]["own_city"]["auc"]]
    V["n_transfer"], V["n_transfer_worse"] = str(len(tc)), str(len(worse))
    V["transfer_better_city"] = _list([CITY[g] for g in tc if g not in worse]) if len(worse) < len(tc) else "none"
    ctx_t = [tr[g]["E+C"]["other_cities"]["auc"] - tr[g]["E"]["other_cities"]["auc"] for g in tc]
    V["n_transfer_ctx_pos"] = str(sum(x > 0 for x in ctx_t))
    gap = [tr[g]["E+C+Z+P"]["own_city"]["auc"] - tr[g]["E+C+Z+P"]["other_cities"]["auc"] for g in worse]
    V["transfer_gap_lo"], V["transfer_gap_hi"] = _f(min(gap)), _f(max(gap))

    # Manhattan rezonings and the redevelopment model
    G = _load("integration_replay")["rezonings"]
    h = lambda k: sum(v["homes_added_by_2025"][k] for v in G.values())
    V["g_n"] = str(len(G))
    V["g_observed"], V["g_capacity"] = _n(h("observed")), _n(h("capacity"))
    V["g_prorated"], V["g_likely"] = _n(h("capacity_prorated_to_2025")), _n(h("likelihood_weighted"))
    V["g_cap_ratio"] = f"{h('capacity') / h('observed'):.0f}"
    V["g_inside"] = str(sum(v["homes_added_by_2025"]["likelihood_weighted_95pct"][0] <= v["homes_added_by_2025"]["observed"]
                            <= v["homes_added_by_2025"]["likelihood_weighted_95pct"][1] for v in G.values()))
    V["g_soho_built"] = _n(G["SoHo/NoHo (2021)"]["homes_added_by_2025"]["observed"])
    V["feis_eh"] = _f(_load("east_harlem_rezoning")["ratio_same_far_to_feis"], 2)
    V["feis_sn"] = _f(_load("soho_noho_rezoning")["ratio_to_feis"], 2)
    ro = _load("rolling_origin")["origins"]
    auc = [o["lightgbm"]["auc"] for o in ro]
    base = [max(b["auc"] for b in o["baselines"].values()) for o in ro]
    V["ro_n"], V["ro_auc_lo"], V["ro_auc_hi"] = str(len(ro)), _f(min(auc)), _f(max(auc))
    V["ro_beats"] = str(sum(a > b for a, b in zip(auc, base)))
    tm = _load("transition_2020_2025")["development"]
    V["tm_auc"] = _f(tm["LightGBM"]["auc"])
    # counts in the prose are words ("seven cities", "all five", "four of seven")
    pairs = {"zE": ("n_zE_sig", "n_zE"), "z": ("n_z_sig", "n_z"), "p": ("n_p_sig", "n_p"),
             "ctx_spatial": ("n_ctx_spatial_pos", "n_test"), "z_spatial": ("n_z_spatial_pos", "n_z_spatial"),
             "dest_z": ("n_dest_z_better", "n_dest_z"), "model_layers": ("n_model_beats_layers", "n_dest"),
             "trend": ("n_trend_better", "n_homes"), "transfer": ("n_transfer_worse", "n_transfer"),
             "transfer_ctx": ("n_transfer_ctx_pos", "n_transfer"), "g": ("g_inside", "g_n")}
    for name, (k, n) in pairs.items():
        V[f"of_{name}"] = _of(int(V[k]), int(V[n]))
    for k in list(V):
        if (k.startswith("n_") or k in ("g_n", "g_inside")) and V[k].isdigit() and int(V[k]) <= 10:
            V[k] = _w(int(V[k]))
    return V


# ----------------------------------------------------------------------------- tables
def _tab(caption: str, label: str, spec: str, head: list[str], rows: list[list[str]], note: str = "",
         size: str = "\\small", sep: str = "4pt", pos: str = "t") -> str:
    L = [f"\\begin{{table}}[{pos}]", "\\centering", size, f"\\setlength{{\\tabcolsep}}{{{sep}}}", f"\\caption{{{caption}}}",
         f"\\label{{{label}}}",
         f"\\begin{{tabular}}{{{spec}}}", "\\toprule", " & ".join(head) + " \\\\", "\\midrule"]
    L += [" & ".join(r) + " \\\\" for r in rows]
    L += ["\\bottomrule", "\\end{tabular}"]
    if note:
        L += ["\\par\\smallskip", f"\\begin{{minipage}}{{0.95\\linewidth}}\\footnotesize {note}\\end{{minipage}}"]
    L += ["\\end{table}"]
    return "\n".join(L)


def tables() -> dict[str, str]:
    integ, cities = _data()
    T = {g: integ[g]["temporal"] for g in cities}
    layers = _load("cities_layers")
    out = {}

    rows = []
    for g, (name, src, plan) in TEN.items():
        v = layers[g]
        cov = lambda k: _pct(v[k]) if v[k] > 0 else "--"
        rows.append([name, _n(v["parcels"]), src, cov("existing"), plan, cov("plan"), cov("zoning"),
                     _f(v["homes_twin"] / v["homes_census_2020"], 2)])
    total = sum(v["parcels"] for v in layers.values())
    rows.append(["\\textit{All}", _n(total), "", "", "", "", "", ""])
    out["table_cities"] = _tab(
        "The ten cities: official parcel layers on one schema. Shares are of the city's parcels.", "tab:cities",
        "lrllllll", ["City", "Parcels", "Existing use (source)", "Share", "Adopted plan", "Share", "Zoning",
                     "Homes / Census"], rows,
        "Existing use is the city's or regional agency's parcel land use, refined by assessor records where the layer "
        "groups uses. Homes / Census: homes in the twin over Census 2020 housing units. Houston has no zoning. "
        "Milwaukee's area plans are published as PDFs that could not be downloaded by script.", size="\\scriptsize")

    rows = []
    for g in cities:
        t = T[g]
        rows.append([CITY[g], OUTCOME[g], OUTCOME_SOURCE[g], f"{t['train'][0]}--{t['train'][1]}",
                     f"{t['test'][0]}--{t['test'][1]}", _n(t["n_lots"]), _n(t["developed"]),
                     _pct(t["sets"]["E"]["base_rate"], 2)])
    out["table_panels"] = _tab(
        "Test panels. Models are fitted on the training window and scored on the test window.", "tab:panels",
        "lllllrrr", ["City", "Development", "Source", "Train", "Test", "Lots", "Developed", "Rate"], rows,
        "Lots already under construction at the start of a window are left out. Floor area +25\\% also requires "
        "+2,000 sq ft. Change of use group: the lot changes to a built use of another of the nine groups, or gains "
        "homes.", size="\\scriptsize")

    rows = []
    for g in cities:
        s = T[g]["sets"]
        c = lambda k: _f(s[k]["auc"]) if k in s else "--"
        best = max(s, key=lambda k: s[k]["auc"])
        cells = [c(k) for k in ("E", "E+C", "E+C+Z", "E+C+P", "E+C+Z+P")]
        rows.append([CITY[g]] + cells + [best])
    out["table_auc"] = _tab(
        "Where development happens: out-of-time AUC by block set. E existing conditions, C neighbourhood context, "
        "Z zoning, P adopted plan; -- where the city has no such layer.", "tab:auc", "lrrrrrl",
        ["City", "E", "E+C", "E+C+Z", "E+C+P", "E+C+Z+P", "Best set (any)"], rows,
        "Best set: the highest AUC among all fitted combinations, including those without context.")

    rows = []
    for g in cities:
        gg = T[g]["gains"]
        c = integ[g].get("temporal_conservative")
        rows.append([CITY[g], _gtex(_gain(gg, "E+C vs E")), _gtex(_gain(gg, "E+C+Z vs E+C")),
                     _gtex(_gain(gg, "E+C+P vs E+C")),
                     _gtex(_gain(c["gains"], "E+C+Z vs E+C")) if c else "",
                     _gtex(_gain(c["gains"], "E+C+P vs E+C")) if c else ""])
    out["table_gains"] = _tab(
        "Gain in out-of-time AUC from adding a block, with 95\\% bootstrap intervals over 2 km tiles. Bold: the "
        "interval excludes zero.", "tab:gains", "llllll",
        ["City", "C over E", "Z over E+C", "P over E+C", "Z, conservative", "P, conservative"], rows,
        "Conservative: in each window, lots whose zoning or plan dates from the window's start or later are left "
        "out; possible where a current layer records those dates (Phoenix, San Diego, Chicago). Dallas's current "
        "layers carry no dates, so its zoning and plan gains are upper bounds.", size="\\scriptsize", sep="2.5pt")

    rows = []
    for g in cities:
        d = T[g].get("destination")
        if not d or not d["n"]:
            continue
        f = lambda x: f"{_pct(x['class'])} / {_pct(x['group'])}" if x and x.get("coverage") else "--"
        st = next(k for k in ("E+C+Z+P", "E+Z+P", "E+Z", "E+C", "E") if k in d["models"])
        rows.append([CITY[g], _n(d["n"]), f(d["layers"].get("existing (no change)")), f(d["layers"].get("zoning class")),
                     f(d["layers"].get("plan class")), f(d["models"][st]) + f" ({st})"])
    out["table_dest"] = _tab(
        "What developed lots became: share named correctly, as one of 16 classes / one of nine groups.", "tab:dest",
        "lrllll", ["City", "Developed", "No change", "Zoning class", "Plan class", "Model (blocks)"], rows,
        "In Phoenix and San Diego development is a change of class (to another group, or to more homes), so ``no "
        "change'' is never right at class level there. Models are cross-fitted over 2 km tiles among the developed "
        "lots. Chicago's permits do not record the new use.", size="\\scriptsize")

    rows = []
    for g in cities:
        sc = T[g].get("scenario")
        if not sc:
            continue
        f = lambda k: f"{_times(sc[k]['ratio_total'])} ({_num(sc[k]['district_spearman'])})" if k in sc else "--"
        rows.append([CITY[g], _n(sc["city_total"]["observed"]), f("zoning_buildout"), f("plan_buildout"),
                     f("likely_zoning"), f("likely_plan"), f("trend")])
    out["table_homes"] = _tab(
        "Homes added in the test window: projection over observed total (Spearman correlation across districts).",
        "tab:homes", "lrlllll", ["City", "Observed", "Zoning build-out", "Plan build-out", "Likely $\\times$ zoning",
                                  "Likely $\\times$ plan", "Five-year trend"], rows,
        "Build-out: every lot at the homes per acre that the 90th percentile of lots of its zoning (or plan) class "
        "reaches in the city today. Likely: the build-out increment times the out-of-time probability of "
        "development (blocks E+C+Z+P where available). Trend: homes completed in the five years before the window, "
        "scaled to its length.", size="\\scriptsize")

    tr = integ["transfer"]
    rows = []
    for g in [c for c in CITY if c in tr]:
        f = lambda k: f"{_f(tr[g][k]['other_cities']['auc'])} / {_f(tr[g][k]['own_city']['auc'])}" if k in tr[g] else "--"
        rows.append([CITY[g], f("E"), f("E+C"), f("E+C+Z"), f("E+C+Z+P")])
    out["table_transfer"] = _tab(
        "Transfer: AUC of a model fitted on the other cities' training windows / the city's own model, on the city's "
        "test window.", "tab:transfer", "lllll", ["City", "E", "E+C", "E+C+Z", "E+C+Z+P"], rows,
        "Cities whose outcome is a building or a permit. A missing plan layer is coded as unknown.")

    G = _load("integration_replay")["rezonings"]
    rows = []
    for name, v in G.items():
        h = v["homes_added_by_2025"]
        lo, hi = h["likelihood_weighted_95pct"]
        rows.append([name, str(v["sites"]), _n(h["observed"]), _n(h["capacity"]), _n(h["capacity_prorated_to_2025"]),
                     f"{_n(h['likelihood_weighted'])} ({_n(lo)}--{_n(hi)})"])
    k = lambda key: _n(sum(v["homes_added_by_2025"][key] for v in G.values()))
    rows.append(["\\textit{All three}", "", k("observed"), k("capacity"), k("capacity_prorated_to_2025"),
                 k("likelihood_weighted")])
    out["table_replay"] = _tab(
        "Three Manhattan rezonings: homes on development sites by 2025, observed and projected.", "tab:replay",
        "lrrrrl", ["Rezoning (adopted)", "Sites", "Built by 2025", "Capacity", "Pro-rated to 2025",
                   "Likelihood-weighted (95\\%)"], rows,
        "Capacity is full build-out by the review's build year; pro-rated scales it linearly to 2025. The "
        "likelihood comes from a redevelopment model trained only on outcomes known by the adoption year.")

    rows = []
    for g in cities:
        s = T[g]["sets"]
        k = "E+C+Z+P" if "E+C+Z+P" in s else "E+C+Z"
        rows.append([CITY[g], _pct(s["E"]["base_rate"], 2), _f(s["E"]["ap"]), _f(s[k]["ap"]), k,
                     _pct(s["E"]["p_top1"], 1), _pct(s[k]["p_top1"], 1)])
    out["table_ap"] = _tab(
        "Out-of-time average precision and precision among the top 1\\% of lots.", "tab:ap", "lrrrlrr",
        ["City", "Base rate", "AP, E", "AP, all", "All blocks", "Top 1\\%, E", "Top 1\\%, all"], rows, pos="h!")
    return out


# ----------------------------------------------------------------------------- render
def render() -> str:
    text = TEMPLATE.read_text()
    fill = {**values(), **tables()}

    def sub(m):
        k = m.group(1)
        if k not in fill:
            raise KeyError(f"no value for @@{k}@@")
        return fill[k]
    return re.sub(r"@@(\w+)@@", sub, text)


def outputs() -> dict:
    return {OUT: render()}


def citations(text: str) -> set[str]:
    keys = set()
    for m in re.finditer(r"\\cite[tp]?\*?(?:\[[^\]]*\])*\{([^}]*)\}", text):
        keys |= {k.strip() for k in m.group(1).split(",")}
    return keys


def main() -> None:
    for p, text in outputs().items():
        p.write_text(text)
        print("written", p.relative_to(ROOT))
    if shutil.which("tectonic"):
        r = subprocess.run(["tectonic", "--keep-logs", OUT.name], cwd=PAPER, capture_output=True, text=True)
        print("paper.pdf" if r.returncode == 0 else r.stderr[-3000:])


if __name__ == "__main__":
    main()
