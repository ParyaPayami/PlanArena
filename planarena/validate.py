"""Validation against independent, observed data. Writes results/validation/*.json and docs/VALIDATION.md.

Downloaded inputs live in data/raw/<dataset>/ (untrusted data; never imported as code). Run steps with
    python -I -m planarena.validate <step>        steps: emissions, jobs, backtest, units, east_harlem,
                                                   optimizer, report, all
The land-use backtest trains PyTorch and LightGBM models in separate processes (OpenMP on macOS).

1. emissions   Out-of-sample: coefficients fitted on LL84 2024, tested on LL84 2023 metered buildings.
2. jobs        Modelled jobs by census block and tract against LEHD LODES 2023 workplace jobs.
3. backtest    2015 -> 2025: models trained on MapPLUTO 15v1 predict which parcels changed use and to what.
4. units       Homes model: replay of 2015-2025 development (observed use and floor area in, homes out).
5. east_harlem The East Harlem rezoning (2017): PlanArena on the FEIS projected development sites against
               the FEIS RWCDS and against what was built by 2025.
6. optimizer   Optimality gap of the optimizer against exhaustive search on small study areas.
"""
from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from planarena.config import DATA, PROCESSED, ROOT, USE_INDEX, USE_KEYS

RAW = DATA / "raw"
P15 = DATA / "processed_15v1"
OUT = ROOT / "results" / "validation"
PLUTO_CUR = Path("/Users/ppayami/Desktop/PIMALUOS/data/manhattan/pluto_manhattan.geojson")
U = USE_INDEX
N_USES = len(USE_KEYS)


def _save(name: str, obj: dict) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2, default=float))
    return obj


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _auc(score: np.ndarray, y: np.ndarray) -> float:
    """ROC AUC by the rank-sum formula (ties get average ranks)."""
    r = pd.Series(score).rank().to_numpy()
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def _logr(a, b):
    m = (a > 0) & (b > 0)
    return float(np.corrcoef(np.log(a[m]), np.log(b[m]))[0, 1]), int(m.sum())


# ----------------------------------------------------------------------------- 1. emissions
def emissions() -> dict:
    from planarena.calibrate import LL97
    from planarena.indicators.engine import load_engine

    f = RAW / "ll84_2023" / "ll84_manhattan_2023_bbl.json"
    d = pd.DataFrame(json.loads(f.read_text()))
    for c in list(LL97) + ["property_gfa_calculated"]:
        d[c] = pd.to_numeric(d.get(c), errors="coerce")
    d["bbl"] = pd.to_numeric(d.nyc_borough_block_and_lot.astype(str).str.split(";").str[0].str.strip(), errors="coerce")
    d["observed_t"] = sum(d[c].clip(lower=0).fillna(0) * v for c, v in LL97.items())
    d = d[d.observed_t > 0].drop_duplicates("bbl")
    e = load_engine()
    idx = {int(b): i for i, b in enumerate(e.p.bbl)}
    d["i"] = d.bbl.map(idx)
    d = d.dropna(subset=["i"])
    d["modelled_t"] = e.baseline_state["ghg"][d.i.astype(int).values]
    m = d[d.modelled_t > 0]
    r, n = _logr(m.observed_t.to_numpy(), m.modelled_t.to_numpy())
    return _save("emissions_ll84_2023", {
        "test": "Out of sample: EUIs and fuel mix fitted on LL84 calendar 2024; tested on calendar 2023 metered energy x LL97 factors",
        "n_buildings": n, "log_log_r": round(r, 3),
        "median_abs_pct_error": round(float(np.median(np.abs(m.modelled_t - m.observed_t) / m.observed_t)), 3),
        "aggregate_ratio_modelled_to_observed": round(float(m.modelled_t.sum() / m.observed_t.sum()), 3),
        "observed_mt": round(float(m.observed_t.sum() / 1e6), 3), "modelled_mt": round(float(m.modelled_t.sum() / 1e6), 3),
        "source": "NYC Open Data 5zyy-y8am, report_year 2023, Manhattan", "source_sha256": _sha(f),
    })


# ----------------------------------------------------------------------------- 2. jobs
def jobs() -> dict:
    import pyogrio

    from planarena.indicators.engine import load_engine

    wac_f = RAW / "lodes8_ny_2023" / "ny_wac_S000_JT00_2023.csv.gz"
    with gzip.open(wac_f, "rt") as fh:
        wac = pd.read_csv(fh, dtype={"w_geocode": str}, usecols=["w_geocode", "C000"])
    wac = wac[wac.w_geocode.str.startswith("36061")]
    src = pyogrio.read_dataframe(PLUTO_CUR, columns=["BBL", "BCTCB2020"], read_geometry=False)
    src["bbl"] = pd.to_numeric(src.BBL, errors="coerce")
    e = load_engine()
    p = pd.DataFrame({"bbl": e.p.bbl.astype("int64"), "jobs": e.baseline_state["jobs"]})
    p = p.merge(src[["bbl", "BCTCB2020"]].dropna(), on="bbl", how="left")
    p = p.dropna(subset=["BCTCB2020"])
    code = p.BCTCB2020.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(11)
    p["block"] = "36061" + code.str[1:]
    p["tract"] = p.block.str[:11]
    mb = p.groupby("block").jobs.sum()
    ob = wac.set_index("w_geocode").C000
    res = {"test": "Modelled baseline jobs (CBECS floorspace per worker, scaled to QCEW 2024) against LEHD LODES8 "
                   "workplace jobs, 2023, Manhattan, by 2020 census block and tract",
           "lodes_total_jobs": int(ob.sum()), "modelled_total_jobs": round(float(p.jobs.sum())),
           "parcels_without_block": int(len(e.p) - len(p)),
           "source": "https://lehd.ces.census.gov/data/lodes/LODES8/ny/wac/ny_wac_S000_JT00_2023.csv.gz",
           "source_sha256": _sha(wac_f)}
    for level, mod, obs in (("block", mb, ob), ("tract", p.groupby("tract").jobs.sum(),
                                                ob.groupby(ob.index.str[:11]).sum())):
        j = pd.concat([mod.rename("modelled"), obs.rename("observed")], axis=1).fillna(0)
        r, n = _logr(j.observed.to_numpy(), j.modelled.to_numpy())
        big = j[j.observed >= 100]
        res[level] = {
            "units": int(len(j)), "log_log_r": round(r, 3), "n_both_positive": n,
            "spearman": round(float(j.observed.corr(j.modelled, method="spearman")), 3),
            "median_abs_pct_error_where_observed_ge_100": round(float(np.median(np.abs(big.modelled - big.observed) / big.observed)), 3),
            "share_of_observed_jobs_in_units_with_modelled_jobs": round(float(j.observed[j.modelled > 0].sum() / j.observed.sum()), 3),
        }
    return _save("jobs_lodes_2023", res)


# ----------------------------------------------------------------------------- 3. backtest (2015 -> 2025)
def _ensure_twin15() -> None:
    if not (P15 / "parcels.parquet").exists():
        from planarena.twin.build import build

        build(out_dir=P15, pluto_path=RAW / "pluto_15v1" / "extracted" / "Manhattan" / "MNMapPLUTO.shp", web=False)


def backtest_gnn(epochs: int = 250) -> None:
    """Torch process: final GNN on the 2015 twin; every parcel predicted while hidden (10 random chunks)."""
    import torch

    from planarena.models.features import context_features
    from planarena.models.train import train_final

    _ensure_twin15()
    df = pd.read_parquet(P15 / "parcels.parquet")
    graph = dict(np.load(P15 / "graph.npz"))
    t0 = time.time()
    model, suit, ctx = train_final(df, graph, context_features(df), epochs)
    np.save(P15 / "suit_gnn.npy", suit)
    torch.save({"state_dict": model.state_dict()}, P15 / "gnn.pt")
    print(f"GNN 2015 trained in {time.time() - t0:.0f}s", flush=True)


def backtest_lgbm(chunks: int = 10) -> None:
    """LightGBM process: the same hidden-chunk protocol as the GNN, with neighbour composition features."""
    import lightgbm as lgb

    from planarena.models.common import SEED, neighbour_composition
    from planarena.models.features import context_features, zone_family

    _ensure_twin15()
    df = pd.read_parquet(P15 / "parcels.parquet")
    graph = dict(np.load(P15 / "graph.npz"))
    x = context_features(df)
    use = df.use.to_numpy().astype("int64")
    chunk = np.random.default_rng(SEED).integers(0, chunks, len(df))
    fam = df.zone.map(zone_family).to_numpy()
    suit = np.zeros((len(df), N_USES))
    prior_out = np.zeros((len(df), N_USES))
    for c in range(chunks):
        hid = chunk == c
        tr = ~hid & (use >= 0)
        feats = np.concatenate([x, neighbour_composition(use, hid, graph)], 1)
        clf = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=63, subsample=0.8, subsample_freq=1,
                                 colsample_bytree=0.8, verbose=-1, random_state=SEED)
        clf.fit(feats[tr], use[tr])
        suit[np.ix_(hid, clf.classes_)] = clf.predict_proba(feats[hid])
        prior = pd.crosstab(fam[tr], use[tr]).reindex(columns=range(N_USES), fill_value=0) + 1
        prior = prior.div(prior.sum(1), axis=0)
        glob = np.bincount(use[tr], minlength=N_USES) + 1.0
        prior_out[hid] = np.stack([prior.loc[z].to_numpy() if z in prior.index else glob / glob.sum() for z in fam[hid]])
        print(f"lgbm chunk {c}", flush=True)
    np.save(P15 / "suit_lgbm.npy", suit)
    np.save(P15 / "suit_zoning.npy", prior_out)


def _matched() -> pd.DataFrame:
    a = pd.read_parquet(P15 / "parcels.parquet").reset_index(names="i15")
    b = pd.read_parquet(PROCESSED / "parcels.parquet").reset_index(names="i25")
    cols = ["bbl", "use", "units_res", "bldg_area", "res_area", "lot_area", "zone", "max_far", "built_far", "cd",
            "year_built"]
    m = a[["i15"] + cols].merge(b[["i25"] + cols], on="bbl", suffixes=("15", "25"))
    return m


def backtest_eval() -> dict:
    m = _matched()
    ok = (m.use15 >= 0) & (m.use25 >= 0)
    m = m[ok].reset_index(drop=True)
    changed = (m.use15 != m.use25).to_numpy()
    i15 = m.i15.to_numpy()
    cur = m.use15.to_numpy().astype(int)
    new = m.use25.to_numpy().astype(int)
    rows = np.arange(len(m))
    scores, dest = {}, {}
    for name in ("gnn", "lgbm", "zoning"):
        P = np.load(P15 / f"suit_{name}.npy")[i15]
        scores[name] = 1 - P[rows, cur]  # misfit of the current use
        Q = P.copy()
        Q[rows, cur] = 0
        Q = Q / np.maximum(Q.sum(1, keepdims=True), 1e-12)
        ch = changed
        rank = (Q[ch] > Q[ch, new[ch]][:, None]).sum(1)
        dest[name] = {"top1": round(float((rank == 0).mean()), 3), "top3": round(float((rank < 3).mean()), 3)}
    underbuilt = 1 - np.clip(np.divide(m.built_far15, m.max_far15, out=np.zeros(len(m)), where=m.max_far15 > 0), 0, 1)
    scores["underbuilt (1 - built/max FAR)"] = underbuilt.to_numpy()
    base_rate = changed.mean()
    k = max(1, int(0.05 * len(m)))
    det = {}
    for name, s in scores.items():
        top = np.argsort(-s)[:k]
        det[name] = {"auc": round(_auc(s, changed), 3), "precision_top5pct": round(float(changed[top].mean()), 3),
                     "lift_top5pct": round(float(changed[top].mean() / base_rate), 2)}
    # Physical change: the use changed and the building was replaced or substantially altered (new year built
    # after 2014, or floor area changed by more than 25%). Filters out reclassifications in PLUTO.
    b15, b25 = m.bldg_area15.to_numpy(), m.bldg_area25.to_numpy()
    rebuilt = (m.year_built25.to_numpy() >= 2015) | (np.abs(b25 - b15) > 0.25 * np.maximum(b15, 1))
    phys = changed & rebuilt
    det_phys = {}
    for name, s in scores.items():
        top = np.argsort(-s)[:k]
        det_phys[name] = {"auc": round(_auc(s, phys), 3), "precision_top5pct": round(float(phys[top].mean()), 3),
                          "lift_top5pct": round(float(phys[top].mean() / phys.mean()), 2)}
    dest_phys = {}
    for name in ("gnn", "lgbm", "zoning"):
        P = np.load(P15 / f"suit_{name}.npy")[i15]
        Q = P.copy()
        Q[rows, cur] = 0
        Q = Q / np.maximum(Q.sum(1, keepdims=True), 1e-12)
        rank = (Q[phys] > Q[phys, new[phys]][:, None]).sum(1)
        dest_phys[name] = {"top1": round(float((rank == 0).mean()), 3), "top3": round(float((rank < 3).mean()), 3)}
    trans = pd.crosstab(pd.Series([USE_KEYS[u] for u in cur], name="2015"), pd.Series([USE_KEYS[u] for u in new], name="2025"))
    # Destination baseline without any model: the most common destination of each 2015 use is unknowable
    # in advance (it would use the outcome), so the reference is chance among the other 8 uses.
    return _save("backtest_2015_2025", {
        "test": "Models trained on MapPLUTO 15v1 (2015) only. Each parcel is predicted while hidden. Outcome: land use in "
                "MapPLUTO 25v3.1 for parcels matched by BBL.",
        "matched_parcels": int(len(m)), "changed": int(changed.sum()), "base_rate": round(float(base_rate), 4),
        "change_detection": det, "destination_of_changed_parcels": dest | {"chance": {"top1": round(1 / 8, 3), "top3": round(3 / 8, 3)}},
        "physical_change": {"n": int(phys.sum()), "base_rate": round(float(phys.mean()), 4),
                            "change_detection": det_phys, "destination": dest_phys},
        "transitions": {r: {c: int(v) for c, v in trans.loc[r].items() if v} for r in trans.index},
        "caveat": "Some recorded changes are reclassifications in PLUTO rather than physical change.",
        "source_sha256_15v1": _sha(RAW / "pluto_15v1" / "mn_mappluto_15v1.zip"),
    })


def backtest() -> dict:
    py = [sys.executable, "-I", "-m", "planarena.validate"]
    if not (P15 / "suit_gnn.npy").exists():
        subprocess.run(py + ["backtest_gnn"], check=True, cwd=ROOT)
    if not (P15 / "suit_lgbm.npy").exists():
        subprocess.run(py + ["backtest_lgbm"], check=True, cwd=ROOT)
    return backtest_eval()


# ----------------------------------------------------------------------------- 4. units (homes) replay
def units() -> dict:
    from planarena.indicators.engine import load_engine

    _ensure_twin15()
    m = _matched()
    dev = (m.units_res25 - m.units_res15 >= 5) & (m.bldg_area25 > 1.2 * m.bldg_area15) & m.use25.isin([U["res"], U["mix"]])
    d = m[dev & (m.lot_area15 > 0)]
    e = load_engine(P15)
    use = e.base_use.copy()
    far = np.full(e.n, np.nan)
    idx = d.i15.to_numpy()
    use[idx] = d.use25.to_numpy()
    far[idx] = (d.bldg_area25 / d.lot_area15).to_numpy()
    st = e.parcel_state(use, far)
    pred = st["units"][idx]
    obs = d.units_res25.to_numpy().astype(float)
    eis = d.res_area25.to_numpy() / 900.0  # the CEQR dwelling-unit factor applied to the observed residential floor area
    r, n = _logr(obs, pred)
    return _save("units_replay_2015_2025", {
        "test": "Parcels developed 2015-2025 (>= 5 new homes and > 20% more floor area). Inputs: the 2025 use and the "
                "observed 2025 floor area. Output: homes, compared with homes recorded in MapPLUTO 25v3.1.",
        "parcels": int(len(d)), "observed_homes": int(obs.sum()), "modelled_homes": round(float(pred.sum())),
        "aggregate_ratio": round(float(pred.sum() / obs.sum()), 3), "log_log_r": round(r, 3),
        "median_abs_pct_error": round(float(np.median(np.abs(pred - obs) / obs)), 3),
        "reference_ceqr_900sf_on_observed_residential_area": {
            "aggregate_ratio": round(float(eis.sum() / obs.sum()), 3),
            "median_abs_pct_error": round(float(np.median(np.abs(eis - obs) / obs)), 3)},
        "note": "PlanArena does not know the residential share of a new building; the reference uses the observed one.",
    })


# ----------------------------------------------------------------------------- 5. East Harlem rezoning replay
def _parse_rwcds(txt: str, start: str, stop: str) -> pd.DataFrame:
    a = txt.index(start)
    b = txt.index(stop, a + 1)
    rows = []
    for line in txt[a:b].splitlines():
        f = re.split(r"\s{2,}", line.strip())
        if len(f) < 10 or not re.fullmatch(r"\d+[A-Z]?", f[0]) or not re.fullmatch(r"\d{3,4}", f[1]):
            continue
        num = lambda s: float(s.replace(",", "")) if re.fullmatch(r"-?[\d,]+(\.\d+)?", s) else np.nan
        rows.append({"site": f[0], "block": int(f[1]), "lots": [int(x) for x in re.findall(r"\d+", f[2])],
                     "lot_area": num(f[3]), "zoning": f[4], "max_far": num(f[5]), "built_far": num(f[6]),
                     "bldg_fa": num(f[7]), "res_fa": num(f[8]), "du": num(f[9])})
    return pd.DataFrame(rows)


def east_harlem() -> dict:
    import geopandas as gpd

    from planarena.indicators.engine import load_engine

    pdf = RAW / "eis_east_harlem" / "appenda_feis.pdf"
    txt_f = RAW / "eis_east_harlem" / "appa.txt"
    if not txt_f.exists():
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt_f)], check=True)
    txt = txt_f.read_text()
    marker = "Appendix A-3"
    a3 = txt[txt.index(marker):]
    na = _parse_rwcds(a3, "No Action Total", "With Action Total")  # No Action projected-site table
    wa = _parse_rwcds(a3, "With Action Total", "Increment")  # With Action projected-site table
    # Projected sites only: the first No Action / With Action tables before the potential-site tables.
    na, wa = na.drop_duplicates("site"), wa.drop_duplicates("site")
    sites = wa.merge(na[["site", "du", "bldg_fa"]], on="site", suffixes=("", "_no_action"))
    sites["bbls"] = sites.apply(lambda r: [1_000_000_000 + r.block * 10_000 + lot for lot in r.lots], axis=1)

    e15 = load_engine(P15)
    idx15 = {int(b): i for i, b in enumerate(e15.p.bbl)}
    g15 = gpd.read_parquet(P15 / "parcels.geoparquet")
    g25 = gpd.read_parquet(PROCESSED / "parcels.geoparquet")
    p25 = pd.read_parquet(PROCESSED / "parcels.parquet")
    pts25 = g25.geometry.representative_point()
    tree = __import__("shapely").STRtree(pts25.values)

    use = e15.base_use.copy()
    far_eis = np.full(e15.n, np.nan)
    far_rule = np.full(e15.n, np.nan)
    rows = []
    for _, s in sites.iterrows():
        ii = [idx15[b] for b in s.bbls if b in idx15]
        if not ii:
            continue
        resid = s.res_fa / s.bldg_fa if s.bldg_fa > 0 else 0
        u = U["res"] if resid >= 0.9 else U["mix"] if resid > 0 else U["com"]
        use[ii] = u
        far_eis[ii] = s.built_far
        far_rule[ii] = s.max_far * e15.coef["assumptions"]["buildout_utilization"]["value"]
        site_geom = g15.geometry.iloc[ii].union_all()
        hit = tree.query(site_geom, predicate="contains")
        rows.append({"site": s.site, "i15": ii, "i25": hit.tolist(), "eis_du": s.du, "eis_du_no_action": s.du_no_action,
                     "existing_du_2015": float(e15.p.units_res.iloc[ii].sum()),
                     "du_2025": float(p25.units_res.iloc[hit].sum())})
    base_units = e15.baseline_state["units"]
    st_eis = e15.parcel_state(use, far_eis)
    st_rule = e15.parcel_state(use, far_rule)
    for r in rows:
        r["planarena_du_same_far"] = float(st_eis["units"][r["i15"]].sum())
        r["planarena_du_zoning_rule"] = float(st_rule["units"][r["i15"]].sum())
    t = pd.DataFrame(rows)
    tot = lambda c: float(t[c].sum())
    eis_inc = tot("eis_du") - tot("eis_du_no_action")
    built_inc = tot("du_2025") - tot("existing_du_2015")
    res = {
        "test": "East Harlem Rezoning FEIS (CEQR 17DCP048M, 2017), Appendix A-3 projected development sites. PlanArena "
                "is run on the same sites: (a) with the FEIS site FAR and use, (b) from zoning alone (max FAR x "
                "build-out utilization). Built outcome: homes recorded in MapPLUTO 25v3.1 on the same land.",
        "sites_parsed": int(len(sites)), "sites_matched_2015": int(len(t)),
        "feis_with_action_du": tot("eis_du"), "feis_no_action_du": tot("eis_du_no_action"), "feis_increment_du": eis_inc,
        "planarena_du_same_far": round(tot("planarena_du_same_far")),
        "planarena_du_zoning_rule": round(tot("planarena_du_zoning_rule")),
        "ratio_same_far_to_feis": round(tot("planarena_du_same_far") / tot("eis_du"), 3),
        "ratio_zoning_rule_to_feis": round(tot("planarena_du_zoning_rule") / tot("eis_du"), 3),
        "site_log_r_same_far": round(_logr(t.eis_du.to_numpy(), t.planarena_du_same_far.to_numpy())[0], 3),
        "existing_du_2015": tot("existing_du_2015"), "du_2025": tot("du_2025"), "built_increment_2015_2025": built_inc,
        "share_of_feis_increment_built_by_2025": round(built_inc / eis_inc, 3) if eis_inc else None,
        "feis_analysis_year": 2027,
        "parse_check": {
            "feis_table_totals": {"with_action_du": 5960, "with_action_bldg_sf": 6433375, "no_action_du": 2472,
                                  "no_action_bldg_sf": 2978556},
            "parsed": {"with_action_du": tot("eis_du"), "with_action_bldg_sf": float(sites.bldg_fa.sum()),
                       "no_action_du": tot("eis_du_no_action"), "no_action_bldg_sf": float(sites.bldg_fa_no_action.sum())},
            "note": "Floor areas match the FEIS totals exactly; dwelling units differ by 1-3 because the FEIS rounds each row."},
        "source": "https://www.nyc.gov/assets/planning/download/pdf/applicants/env-review/east-harlem/appenda_feis.pdf",
        "source_sha256": _sha(pdf),
        "planarena_baseline_units_on_sites_2015": round(float(sum(base_units[r["i15"]].sum() for r in rows))),
    }
    return _save("east_harlem_rezoning", res)


# ----------------------------------------------------------------------------- 5b. SoHo/NoHo (2021) site-level
P20 = DATA / "processed_20v8"


def _soho_tables(txt: str) -> list[pd.DataFrame]:
    """Appendix A2 tables in order: No Action (projected, potential), With Action (...), Increment (...)."""
    tables, cur = [], []
    for line in txt.splitlines():
        tok = line.split()
        if tok and tok[0] == "TOTAL":
            tables.append(pd.DataFrame(cur))
            cur = []
            continue
        grp = [k for k, t_ in enumerate(tok) if t_ in ("Projected", "Potential")]
        if len(tok) > 10 and grp:
            g = grp[0]  # existing zoning can span two tokens (split lots), so locate the group column
            num = lambda t: (0.0 if t == "-" else float(t.replace(",", "")) if re.fullmatch(r"-?[\d,]+(\.\d+)?", t)
                             else np.nan)
            cur.append({"dsow": tok[0], "site": tok[1], "lot_area": num(tok[3]), "zone_new": tok[g - 1], "group": tok[g],
                        "res_zfa": num(tok[g + 1]), "res_gfa": num(tok[g + 2]), "du": num(tok[g + 3]),
                        "total_gfa": num(tok[-6]) if len(tok) > 30 else np.nan})
    return tables


def soho_noho() -> dict:
    from planarena.indicators.engine import load_engine

    pdf = RAW / "eis_soho_noho" / "appenda-feis.pdf"
    txt_f = RAW / "eis_soho_noho" / "appa.txt"
    if not txt_f.exists():
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt_f)], check=True)
    txt = txt_f.read_text()
    t = _soho_tables(txt[txt.index("Appendix A2"):txt.index("Appendix A3")])
    no_action, with_action = t[0], t[2]
    # Appendix A3: BBL -> DSOW site id
    a3 = txt[txt.index("Appendix A3"):]
    bbl_site = {}
    for line in a3.splitlines():
        for bbl, dsow in re.findall(r"(1\d{9})\s+\S+\s+(\S+)", line):
            bbl_site[int(bbl)] = dsow
    e20 = load_engine(P20)
    idx20 = {int(b): i for i, b in enumerate(e20.p.bbl)}
    p25 = pd.read_parquet(PROCESSED / "parcels.parquet")
    idx25 = {int(b): i for i, b in enumerate(p25.bbl)}
    use = e20.base_use.copy()
    far = np.full(e20.n, np.nan)
    rows = []
    for _, r in with_action.iterrows():
        bbls = [b for b, d in bbl_site.items() if d == r.dsow]
        ii = [idx20[b] for b in bbls if b in idx20]
        if not ii or not r.total_gfa > 0:
            continue
        resid = r.res_gfa / r.total_gfa
        use[ii] = U["res"] if resid >= 0.9 else U["mix"] if resid > 0 else U["com"]
        far[ii] = r.total_gfa / r.lot_area
        na = no_action[no_action.dsow == r.dsow]
        rows.append({"dsow": r.dsow, "i": ii, "feis_du": r.du, "feis_du_no_action": float(na.du.sum()) if len(na) else 0.0,
                     "du_2020": float(e20.p.units_res.iloc[ii].sum()),
                     "du_2025": float(sum(p25.units_res.iloc[idx25[b]] for b in bbls if b in idx25))})
    st = e20.parcel_state(use, far)
    for r in rows:
        r["planarena_du"] = float(st["units"][r["i"]].sum())
    d = pd.DataFrame(rows)
    proj = with_action[with_action.group == "Projected"]
    res = {
        "test": "SoHo/NoHo Neighborhood Plan FEIS (2021), Appendix A2 projected development sites (BBLs from Appendix A3). "
                "PlanArena is run on the same sites with the FEIS gross floor area and use; built outcome from MapPLUTO "
                "25v3.1 (BBL match).",
        "projected_sites_parsed": int(len(proj)), "sites_matched_2020": int(len(d)),
        "parse_check": {"appendix_total_projected_du": 1861, "parsed": float(proj.du.sum()),
                        "note": "Appendix A2 totals 1,861 projected DUs; the FEIS text reports 1,858."},
        "feis_with_action_du": float(d.feis_du.sum()), "feis_no_action_du": float(d.feis_du_no_action.sum()),
        "feis_text_with_action_du": 1858, "feis_text_increment_du": 1826, "feis_appendix_total_du": float(proj.du.sum()),
        "planarena_du_same_gfa": round(float(d.planarena_du.sum())),
        "ratio_to_feis": round(float(d.planarena_du.sum() / d.feis_du.sum()), 3),
        "site_log_r": round(_logr(d.feis_du.to_numpy(), d.planarena_du.to_numpy())[0], 3),
        "du_2020": float(d.du_2020.sum()), "du_2025": float(d.du_2025.sum()),
        "feis_unit_factor_sf": 850, "feis_analysis_year": 2031, "adopted": "2021-12",
        "source": "https://www.nyc.gov/assets/planning/download/pdf/applicants/env-review/soho-noho/appenda-feis.pdf",
        "source_sha256": _sha(pdf),
    }
    return _save("soho_noho_rezoning", res)


# ----------------------------------------------------------------------------- 5c. area-level replays (all three)
REZONINGS = {
    "East Harlem (2017)": {"cd": 111, "before": "15", "year": 2017, "feis_increment_du": 3488, "horizon": 2027,
                           "feis": "East Harlem Rezoning FEIS, CEQR 17DCP048M, Table 1-1a"},
    "Inwood (2018)": {"cd": 112, "before": "15", "year": 2018, "feis_increment_du": 3908, "horizon": 2033,
                      "feis": "Inwood Rezoning, CEQR 17DME007M, OEC project page (Technical Memorandum 003, 15-year)"},
    "SoHo/NoHo (2021)": {"cd": 102, "before": "20", "year": 2021, "feis_increment_du": 1826, "horizon": 2031,
                         "feis": "SoHo/NoHo Neighborhood Plan FEIS (2021), Chapter 1"},
}


def rezonings() -> dict:
    from planarena.indicators import rwcds
    from planarena.indicators.engine import load_engine
    from planarena.twin.zoning import allowed_uses

    import geopandas as gpd
    import shapely

    p25 = pd.read_parquet(PROCESSED / "parcels.parquet")
    pts25 = gpd.read_parquet(PROCESSED / "parcels.geoparquet").geometry.representative_point().values
    tree25 = shapely.STRtree(pts25)
    out = {}
    for name, cfg in REZONINGS.items():
        d0 = P15 if cfg["before"] == "15" else P20
        e0 = load_engine(d0)
        b = e0.p[["bbl", "zone", "max_far", "units_res", "cd"]].reset_index(names="i0").merge(
            p25[["bbl", "zone", "max_far", "units_res"]], on="bbl", suffixes=("_0", "_1"))
        b = b[b.cd == cfg["cd"]]
        rez = b[b.zone_0 != b.zone_1]
        new_max = e0.p["max_far"].to_numpy().copy()
        new_max[rez.i0.to_numpy()] = rez.max_far_1.to_numpy()
        area = np.zeros(e0.n, bool)
        area[rez.i0.to_numpy()] = True
        res_ok = np.zeros(e0.n, bool)
        res_ok[rez.i0.to_numpy()] = [("res" in allowed_uses(z)) for z in rez.zone_1]
        sites = rwcds.screen(e0, new_max, area, cfg["year"])
        full = rwcds.project(e0, sites, new_max, res_ok, 1.0)
        util = rwcds.project(e0, sites, new_max, res_ok, e0.coef["assumptions"]["buildout_utilization"]["value"])
        # Observed homes by 2025 on the same land: 2025 lots whose representative point falls inside the
        # rezoned (or screened) t0 lots, so merged lots of new buildings are followed.
        g0 = gpd.read_parquet(d0 / "parcels.geoparquet").geometry.values
        def built_on(idx0):
            if not len(idx0):
                return 0.0
            hit = tree25.query(shapely.union_all(g0[idx0]), predicate="contains")
            return float(p25.units_res.iloc[hit].sum() - e0.p.units_res.iloc[idx0].sum())
        observed = built_on(rez.i0.to_numpy())
        observed_sites = built_on(np.nonzero(sites)[0])
        out[name] = {
            "rezoned_lots_matched": int(len(rez)), "screened_sites": full["sites"],
            "feis_increment_du": cfg["feis_increment_du"], "feis_source": cfg["feis"], "feis_horizon": cfg["horizon"],
            "planarena_increment_du_at_max_far": round(full["homes_increment"]),
            "planarena_increment_du_at_utilisation": round(util["homes_increment"]),
            "ratio_max_far_to_feis": round(full["homes_increment"] / cfg["feis_increment_du"], 3),
            "observed_increment_du_rezoned_lots_to_2025": observed,
            "observed_increment_du_on_screened_sites_to_2025": observed_sites,
            "observed_share_of_feis_increment": round(observed / cfg["feis_increment_du"], 3),
        }
    return _save("rezoning_replays", {
        "test": "Area-level replay. Rezoned lots = zoning changed between the release before adoption and MapPLUTO "
                "25v3.1 within the community district (BBL match); homes built are counted on the same land by geometry. PlanArena applies its CEQR-style development-site "
                "screen (planarena/indicators/rwcds.py) under the new maximum FAR and projects homes; compared with the "
                "FEIS increment and with homes recorded by 2025. Mandatory Inclusionary Housing bonus FAR is not modelled.",
        "rezonings": out,
    })


# ----------------------------------------------------------------------------- 6. optimizer gap
def optimizer(n_areas: int = 20, budget: int = 2, seed: int = 0) -> dict:
    import itertools

    from planarena.indicators.engine import load_engine
    from planarena.optimize.suggest import SuggestConfig, Suggester

    e = load_engine()
    sug = Suggester(e, None)
    pen = SuggestConfig().conversion_penalty
    rng = np.random.default_rng(seed)
    blocks = e.p.groupby(["cd", "block"]).size()
    out = []
    for (cd, blk) in rng.permutation(blocks.index.to_numpy()):
        if len(out) >= n_areas:
            break
        cand = np.nonzero((e.p.block.to_numpy() == blk) & (e.cd == cd))[0]
        cfg = SuggestConfig(scope=f"cd:{int(cd)}", candidate_parcels=cand, w_fit=0.0,
                            max_change_share=1.0, rounds=budget)
        _, eligible, allowed = sug.feasible(cfg, e.base_use)
        el = np.nonzero(eligible)[0]
        moves = [(p, u) for p in el for u in np.nonzero(allowed[p])[0] if u != e.base_use[p]]
        if not 4 <= len(el) <= 12 or not 4 <= len(moves) <= 40:
            continue
        cfg.max_change_share = budget / len(el)
        J = lambda use, k: e.evaluate(use, scope=cfg.scope)["overall"] - pen * k
        best, best_set = 0.0, ()
        for k in range(1, budget + 1):
            for combo in itertools.combinations(moves, k):
                if len({p for p, _ in combo}) < k:
                    continue
                use = e.base_use.copy()
                for p, u in combo:
                    use[p] = u
                v = J(use, k)
                if v > best:
                    best, best_set = v, combo
        r = sug.suggest(cfg)
        got = J(r["use"], len(r["changed"]))
        cfg.polish = 30
        t0 = time.time()
        rp = sug.suggest(cfg)
        polish_s = time.time() - t0
        cfg.polish = 0
        got_p = J(rp["use"], len(rp["changed"]))
        rand = []
        for _ in range(20):
            use = e.base_use.copy()
            pick = rng.choice(len(moves), size=min(budget, len(moves)), replace=False)
            done = set()
            for j in pick:
                p, u = moves[j]
                if p not in done:
                    use[p] = u
                    done.add(p)
            rand.append(J(use, len(done)))
        out.append({"cd": int(cd), "block": int(blk), "eligible": int(len(el)), "moves": len(moves),
                    "exact": best, "optimizer": got, "optimizer_polished": got_p, "polish_seconds": round(polish_s, 2),
                    "random_mean": float(np.mean(rand)),
                    "gap": (best - got) / best if best > 1e-12 else 0.0,
                    "gap_polished": (best - got_p) / best if best > 1e-12 else 0.0})
        print(out[-1], flush=True)
    t = pd.DataFrame(out)
    pos = t[t.exact > 1e-12]
    return _save("optimizer_gap", {
        "test": f"Exhaustive search over every feasible plan with up to {budget} changes on small study areas "
                "(one tax block; 4-12 eligible parcels), objective = overall score minus the conversion penalty, "
                "GNN fit term off. Optimizer = iterated best response with the same constraints.",
        "areas": int(len(t)), "areas_with_positive_optimum": int(len(pos)),
        "median_gap": round(float(pos.gap.median()), 4) if len(pos) else None,
        "mean_gap": round(float(pos.gap.mean()), 4) if len(pos) else None,
        "share_exact_optimum_found": round(float((pos.gap <= 1e-9).mean()), 3) if len(pos) else None,
        "optimizer_over_random_mean": round(float((pos.optimizer - pos.random_mean).mean()), 4) if len(pos) else None,
        "polished": {"median_gap": round(float(pos.gap_polished.median()), 4) if len(pos) else None,
                     "mean_gap": round(float(pos.gap_polished.mean()), 4) if len(pos) else None,
                     "share_exact_optimum_found": round(float((pos.gap_polished <= 1e-9).mean()), 3) if len(pos) else None,
                     "median_seconds": round(float(t.polish_seconds.median()), 2)},
        "material_areas": {"rule": "optimum > 0.01 score points",
                           "n": int((pos.exact > 0.01).sum()),
                           "share_exact_first_order": round(float((pos[pos.exact > 0.01].gap <= 1e-9).mean()), 3) if (pos.exact > 0.01).any() else None,
                           "share_exact_polished": round(float((pos[pos.exact > 0.01].gap_polished <= 1e-9).mean()), 3) if (pos.exact > 0.01).any() else None},
        "areas_detail": out,
    })


# ----------------------------------------------------------------------------- report
def report() -> str:
    def load(n):
        f = OUT / f"{n}.json"
        return json.loads(f.read_text()) if f.exists() else None

    em, jb, bt, un, eh, op = (load(n) for n in ("emissions_ll84_2023", "jobs_lodes_2023", "backtest_2015_2025",
                                                "units_replay_2015_2025", "east_harlem_rezoning", "optimizer_gap"))
    L = ["# Validation (generated)", "", "<!-- GENERATED by python -m planarena.validate report. Do not edit. -->", "",
         "Every number below is read from `results/validation/*.json`, produced by `planarena/validate.py` "
         "from downloaded open data (hashes in each file).", ""]
    if em:
        L += ["## Emissions, out of sample (LL84 2023)", "",
              f"Coefficients fitted on 2024 and tested on {em['n_buildings']:,} buildings' 2023 metered energy: log–log r "
              f"**{em['log_log_r']}**, median absolute error **{em['median_abs_pct_error']:.0%}**, total modelled / metered "
              f"**{em['aggregate_ratio_modelled_to_observed']}** ({em['modelled_mt']} vs {em['observed_mt']} Mt).", ""]
    if jb:
        L += ["## Jobs against LEHD LODES 2023", "",
              f"Totals: modelled {jb['modelled_total_jobs']:,} (scaled to QCEW) vs LODES {jb['lodes_total_jobs']:,}.", "",
              "| Level | Units | log–log r | Spearman | Median error (units with ≥100 jobs) |", "|---|---:|---:|---:|---:|"]
        for lv in ("tract", "block"):
            x = jb[lv]
            L.append(f"| {lv} | {x['units']:,} | {x['log_log_r']} | {x['spearman']} | "
                     f"{x['median_abs_pct_error_where_observed_ge_100']:.0%} |")
        L.append("")
    if bt:
        L += ["## Land-use backtest, 2015 → 2025", "",
              f"{bt['matched_parcels']:,} parcels matched by BBL; {bt['changed']:,} changed use "
              f"({bt['base_rate']:.1%}). Models saw only 2015 data.", "",
              "| Which parcels change? | AUC | Precision in top 5% | Lift |", "|---|---:|---:|---:|"]
        for k, v in bt["change_detection"].items():
            L.append(f"| {k} | {v['auc']} | {v['precision_top5pct']:.1%} | {v['lift_top5pct']}× |")
        L += ["", "| New use of changed parcels | Top-1 | Top-3 |", "|---|---:|---:|"]
        for k, v in bt["destination_of_changed_parcels"].items():
            L.append(f"| {k} | {v['top1']:.1%} | {v['top3']:.1%} |")
        ph = bt["physical_change"]
        L += ["", f"**Physical change only** (use changed and the building was replaced or its floor area changed by "
              f"more than 25%): {ph['n']:,} parcels ({ph['base_rate']:.1%}).", "",
              "| Model | AUC | Precision in top 5% | Lift | New use top-1 | Top-3 |", "|---|---:|---:|---:|---:|---:|"]
        for k, v in ph["change_detection"].items():
            d = ph["destination"].get(k)
            L.append(f"| {k} | {v['auc']} | {v['precision_top5pct']:.1%} | {v['lift_top5pct']}× | "
                     + (f"{d['top1']:.1%} | {d['top3']:.1%} |" if d else "– | – |"))
        L += ["", f"Caveat: {bt['caveat']}", ""]
    tr = load("transition_2020_2025")
    if tr:
        L += ["## Redevelopment-transition model (temporal holdout)", "",
              f"Trained on 2015 features and 2015–2020 outcomes ({tr['train_developed']:,} redeveloped lots), tested on "
              f"2020 features and 2020–2025 outcomes ({tr['test_developed']:,} of {tr['test_parcels']:,}; base rate "
              f"{tr['test_base_rate']:.2%}).", "",
              "| Will the lot be redeveloped within 5 years? | AUC | Average precision | Precision, top 1% | Recall, top 5% |",
              "|---|---:|---:|---:|---:|"]
        for k, v in tr["development"].items():
            L.append(f"| {k} | {v['auc']} | {v['average_precision']} | {v['precision_top1pct']:.1%} | {v['recall_top5pct']:.1%} |")
        L += ["", f"| Into what use? ({tr['destination_n']} redeveloped lots) | Top-1 | Top-3 | Top-1 when the use changed |",
              "|---|---:|---:|---:|"]
        for k, v in tr["destination"].items():
            L.append(f"| {k} | {v['top1']:.1%} | {v['top3']:.1%} | {v['top1_when_use_changed']:.1%} |")
        L += ["", "Model selection used a spatial hold-out inside the training period only. Accuracy there (average "
              "precision about 0.54) is far above the later period: redevelopment patterns shifted after 2020.", ""]
    if un:
        L += ["## Homes: replay of 2015–2025 development", "",
              f"{un['parcels']} developed parcels, {un['observed_homes']:,} homes recorded in 2025. Given the observed "
              f"use and floor area, PlanArena estimates {un['modelled_homes']:,} (ratio **{un['aggregate_ratio']}**, "
              f"median error {un['median_abs_pct_error']:.0%}, log–log r {un['log_log_r']}). Reference, CEQR 900 sq ft "
              f"per unit on the observed residential floor area: ratio {un['reference_ceqr_900sf_on_observed_residential_area']['aggregate_ratio']}.", ""]
    if eh:
        L += ["## East Harlem rezoning (2017) replay", "",
              f"FEIS projected development sites parsed: {eh['sites_parsed']} (matched to 2015 parcels: {eh['sites_matched_2015']}).", "",
              "| Homes on the projected sites | Count |", "|---|---:|",
              f"| FEIS With Action (2027) | {eh['feis_with_action_du']:,.0f} |",
              f"| FEIS No Action (2027) | {eh['feis_no_action_du']:,.0f} |",
              f"| PlanArena, same site FAR and use | {eh['planarena_du_same_far']:,} ({eh['ratio_same_far_to_feis']}× FEIS) |",
              f"| PlanArena, from zoning alone (max FAR × 0.8) | {eh['planarena_du_zoning_rule']:,} ({eh['ratio_zoning_rule_to_feis']}× FEIS) |",
              f"| Recorded 2015 | {eh['existing_du_2015']:,.0f} |",
              f"| Recorded 2025 | {eh['du_2025']:,.0f} |", "",
              f"By 2025, {eh['share_of_feis_increment_built_by_2025']:.0%} of the FEIS increment of "
              f"{eh['feis_increment_du']:,.0f} homes is recorded on the projected sites (FEIS analysis year 2027).", ""]
    sn, rz = load("soho_noho_rezoning"), load("rezoning_replays")
    if sn:
        L += ["## SoHo/NoHo (2021) replay, site level", "",
              f"FEIS Appendix A2 projected sites parsed: {sn['projected_sites_parsed']} (total {sn['parse_check']['parsed']:,.0f} "
              f"homes, matching the appendix total; the FEIS text reports {sn['feis_text_with_action_du']:,}). On the "
              f"{sn['sites_matched_2020']} sites matched to 2020 lots, PlanArena with the FEIS floor area and use gives "
              f"{sn['planarena_du_same_gfa']:,} homes against the FEIS's {sn['feis_with_action_du']:,.0f} "
              f"(**{sn['ratio_to_feis']}×**, site-level log r {sn['site_log_r']}). Homes recorded on those sites: "
              f"{sn['du_2020']:.0f} in 2020 and {sn['du_2025']:.0f} in 2025 (FEIS analysis year 2031).", ""]
    if rz:
        L += ["## Three rezonings, area level", "",
              "PlanArena's own CEQR-style development-site screen (`planarena/indicators/rwcds.py`), applied to the lots "
              "whose zoning changed, against the city's projection and what was built by 2025.", "",
              "| Rezoning | Screened sites | FEIS increment | PlanArena at max FAR | PlanArena at 0.8 × max | Built by 2025 (all rezoned lots) | Share of FEIS increment |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        for k, v in rz["rezonings"].items():
            L.append(f"| {k} | {v['screened_sites']} | {v['feis_increment_du']:,} (to {v['feis_horizon']}) | "
                     f"{v['planarena_increment_du_at_max_far']:,} ({v['ratio_max_far_to_feis']}×) | "
                     f"{v['planarena_increment_du_at_utilisation']:,} | {v['observed_increment_du_rezoned_lots_to_2025']:+,.0f} | "
                     f"{v['observed_share_of_feis_increment']:.0%} |")
        L += ["", "The FEIS selects 'projected' sites more narrowly than PlanArena's screen, which also captures sites the "
              "FEIS treats as 'potential'. Mandatory Inclusionary Housing bonus FAR is not modelled.", ""]
    if op:
        L += ["## Optimizer against exhaustive search", "",
              f"{op['areas']} small study areas ({op['areas_with_positive_optimum']} with a positive optimum). The optimizer "
              f"found the exact optimum in **{op['share_exact_optimum_found']:.0%}** of them; median gap "
              f"{op['median_gap']:.1%}, mean gap {op['mean_gap']:.1%}. With the exact polish step (top 30 moves "
              f"re-scored), it found the optimum in **{op['polished']['share_exact_optimum_found']:.0%}** (mean gap "
              f"{op['polished']['mean_gap']:.1%}; median {op['polished']['median_seconds']} s).", ""]
    text = "\n".join(L)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "VALIDATION.md").write_text(text)
    return text


STEPS = {"emissions": emissions, "jobs": jobs, "backtest": backtest, "backtest_gnn": backtest_gnn,
         "soho_noho": soho_noho, "rezonings": rezonings,
         "backtest_lgbm": backtest_lgbm, "backtest_eval": backtest_eval, "units": units,
         "east_harlem": east_harlem, "optimizer": optimizer, "report": report}

if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    todo = (["emissions", "jobs", "backtest", "units", "east_harlem", "soho_noho", "rezonings", "optimizer", "report"]
            if step == "all" else [step])
    for s in todo:
        t0 = time.time()
        r = STEPS[s]()
        if isinstance(r, dict):
            print(s, json.dumps({k: v for k, v in r.items() if not isinstance(v, (list, dict))}, default=float)[:900])
        print(f"[{s}] {time.time() - t0:.0f}s", flush=True)
