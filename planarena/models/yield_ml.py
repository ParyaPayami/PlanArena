"""Learned correction of the engine's homes, value and emissions estimates, and calibrated prediction intervals.

The engine (planarena.indicators.engine) predicts what a change does from transparent rules. On held-out Manhattan
lots (planarena.models.impact_test) it overstates homes added 1.47-fold, mostly in conversions to mixed use, and its
sensitivity ranges are not prediction intervals. This module tests two learned additions on the same change events,
spatial folds and pre-period coefficients as impact_test:

* Residual correction: gradient boosting (LightGBM) of the engine's error, from the engine's own prediction and the
  lot information the baselines use (floor area before and after, lot area, uses, homes and value before). The loss
  (squared or Huber) is chosen by cross-fitting within the selection folds; the model is trained on the selection
  folds and evaluated on the held-out folds. It is adopted only if it lowers the held-out mean absolute error and
  absolute bias without lowering the correlation.
* Conformal intervals: conformalized quantile regression (Romano et al. 2019) of the engine's error, with quantile
  models fitted on one selection fold and calibrated on the other, for 90% intervals. Coverage and width are measured
  on the held-out folds and compared with how often the engine's sensitivity range contains the observed change.

The models of the adopted indicators are then refitted for the Studio (fit_deploy): the correction on every event,
the quantile models on the selection folds, calibrated on the held-out folds. The parcel inspector shows, for each
new use, the learned estimate and its 90% interval beside the engine's.

Run:  python -I -m planarena.models.yield_ml [deploy]  -> results/validation/yield_ml.json, data/processed/yield_ml.pkl
"""
from __future__ import annotations

import json
import sys

import numpy as np

from planarena.config import PROCESSED, ROOT

OUT = ROOT / "results" / "validation" / "yield_ml.json"
DEPLOY = PROCESSED / "yield_ml.pkl"
KEYS = ("homes", "value", "ghg")
ALPHA = 0.10
GBM = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=20, reg_lambda=1.0, verbose=-1,
           random_state=0)


def _events() -> dict:
    """Events, observed changes, the deployed engine's predictions (and its low/high variants), features, folds."""
    from planarena.indicators.engine import load_engine
    from planarena.models.common import spatial_folds
    from planarena.models.impact_test import SELECTION_FOLDS, _apply, pre_period_coefficients
    from planarena.validate import P15, _change_events

    d = _change_events()
    ev, p0 = d["ev"].reset_index(drop=True), d["p0"]
    folds = spatial_folds(p0.iloc[ev.i0.map(lambda ii: ii[0])].reset_index(drop=True), k=5)
    obs = {"homes": ev.d_homes.to_numpy(float), "value": ev.d_value.to_numpy(float), "ghg": ev.d_ghg.to_numpy(float)}
    e = load_engine(P15)
    _apply(e, pre_period_coefficients(p0, e))
    e.delta_form, e.unit_rule = "hybrid", "stock"  # the engine as deployed
    use, far = e.base_use.copy(), np.full(e.n, np.nan)
    for r in ev.itertuples():
        ii = np.array(r.i0)
        use[ii] = r.use1
        far[ii] = r.fa1 / max(r.lot0, 1.0)
    pred = {}
    for v in ("mid", "a", "b"):
        e.variant = v
        base = e.parcel_state(e.base_use)
        st = e.parcel_state(use, far)
        pred[v] = {k: ev.i0.map(lambda ii, k=k: float((st[k][ii] - base[k][ii]).sum())).to_numpy() for k in KEYS}
    e.variant = "mid"
    units0 = ev.i0.map(lambda ii: float(p0.units_res.iloc[ii].sum())).to_numpy()
    value0 = ev.i0.map(lambda ii: float(p0.assess_tot.iloc[ii].sum())).to_numpy()
    X = np.c_[np.log1p(ev.fa0), np.log1p(ev.fa1), np.log1p(ev.lot0), ev.use0, ev.use1, units0, np.log1p(value0),
              (ev.kind == "use change").to_numpy(float)]
    return {"ev": ev, "obs": obs, "pred": pred, "X": X, "folds": folds,
            "sel": np.isin(folds, SELECTION_FOLDS), "sel_folds": SELECTION_FOLDS}


def _features(X: np.ndarray, engine_pred: np.ndarray) -> np.ndarray:
    return np.c_[X, np.sign(engine_pred) * np.log1p(np.abs(engine_pred))]


def _fit(Xf, y, loss: str):
    import lightgbm as lgb

    kw = dict(GBM, objective="huber", alpha=float(np.quantile(np.abs(y), 0.9)) or 1.0) if loss == "huber" else \
        dict(GBM, objective="regression")
    return lgb.LGBMRegressor(**kw).fit(Xf, y)


def _quantile(Xf, y, q: float):
    import lightgbm as lgb

    return lgb.LGBMRegressor(**dict(GBM, objective="quantile", alpha=q)).fit(Xf, y)


def main() -> dict:
    from planarena.models.impact_test import _metrics

    D = _events()
    obs, pred, X, folds, sel = D["obs"], D["pred"], D["X"], D["folds"], D["sel"]
    evl = ~sel
    f0, f1 = D["sel_folds"]
    res = {"test": __doc__.strip().split("\n\n")[0].replace("\n", " "), "events": int(len(folds)),
           "selection_events": int(sel.sum()), "evaluation_events": int(evl.sum()), "alpha": ALPHA,
           "indicators": {}}
    for k in KEYS:
        y, p = obs[k], pred["mid"][k]
        ok = np.isfinite(y) & np.isfinite(p)
        Xf = _features(X, p)
        r = y - p
        # loss chosen by cross-fitting within the selection folds (fold f0 -> f1 and f1 -> f0)
        cv = {}
        for loss in ("l2", "huber"):
            err = []
            for a, b in ((f0, f1), (f1, f0)):
                tr, te = ok & (folds == a), ok & (folds == b)
                m = _fit(Xf[tr], r[tr], loss)
                err.append(np.mean(np.abs(p[te] + m.predict(Xf[te]) - y[te])))
            cv[loss] = float(np.mean(err))
        loss = min(cv, key=cv.get)
        tr = ok & sel
        model = _fit(Xf[tr], r[tr], loss)
        corrected = p + model.predict(Xf)
        te = ok & evl
        m_engine, m_corr = _metrics(p[te], y[te]), _metrics(corrected[te], y[te])
        adopt = (m_corr["mae"] < m_engine["mae"] and abs(m_corr["bias"]) < abs(m_engine["bias"])
                 and (m_corr.get("pearson_r") or 0) >= (m_engine.get("pearson_r") or 0) - 1e-9)
        # conformalized quantile regression of the error: fit on fold f0, calibrate on fold f1
        fit_, cal = ok & (folds == f0), ok & (folds == f1)
        lo_m, hi_m = _quantile(Xf[fit_], r[fit_], ALPHA / 2), _quantile(Xf[fit_], r[fit_], 1 - ALPHA / 2)
        score = np.maximum(lo_m.predict(Xf[cal]) - r[cal], r[cal] - hi_m.predict(Xf[cal]))
        n = int(cal.sum())
        Q = float(np.quantile(score, min(1.0, np.ceil((1 - ALPHA) * (n + 1)) / n)))
        lo, hi = p + lo_m.predict(Xf) - Q, p + hi_m.predict(Xf) + Q
        cover = (y >= lo) & (y <= hi)
        rng_lo = np.minimum.reduce([pred[v][k] for v in ("mid", "a", "b")])
        rng_hi = np.maximum.reduce([pred[v][k] for v in ("mid", "a", "b")])
        in_range = (y >= rng_lo) & (y <= rng_hi)
        res["indicators"][k] = {
            "loss_chosen": loss, "selection_cv_mae": cv,
            "engine": m_engine, "engine_plus_residual_model": m_corr, "adopted": bool(adopt),
            "conformal": {"calibration_events": n, "quantile_of_scores": Q,
                          "coverage_heldout": float(cover[te].mean()), "target": 1 - ALPHA,
                          "median_width": float(np.median((hi - lo)[te])),
                          "median_abs_observed": float(np.median(np.abs(y[te])))},
            "sensitivity_range_coverage_heldout": float(in_range[te].mean()),
            "sensitivity_range_median_width": float(np.median((rng_hi - rng_lo)[te])),
        }
        print(k, "engine MAE %.2f bias %.2f r %.3f | corrected MAE %.2f bias %.2f r %.3f | adopt %s | CQR cover %.3f "
              "| range cover %.3f" % (m_engine["mae"], m_engine["bias"], m_engine.get("pearson_r") or 0,
                                     m_corr["mae"], m_corr["bias"], m_corr.get("pearson_r") or 0, adopt,
                                     cover[te].mean(), in_range[te].mean()), flush=True)
    OUT.write_text(json.dumps(res, indent=1))
    return res


def fit_deploy() -> dict:
    """Refit the adopted corrections (all events) and the interval models (selection folds, calibrated on the
    held-out folds) for the Studio."""
    import pickle

    adopted = {k: v["adopted"] for k, v in json.loads(OUT.read_text())["indicators"].items()}
    D = _events()
    obs, pred, X, sel = D["obs"], D["pred"], D["X"], D["sel"]
    models = {}
    for k, ok_k in adopted.items():
        if not ok_k:
            continue
        y, p = obs[k], pred["mid"][k]
        ok = np.isfinite(y) & np.isfinite(p)
        Xf, r = _features(X, p), y - p
        loss = json.loads(OUT.read_text())["indicators"][k]["loss_chosen"]
        corr = _fit(Xf[ok], r[ok], loss)
        lo_m, hi_m = _quantile(Xf[ok & sel], r[ok & sel], ALPHA / 2), _quantile(Xf[ok & sel], r[ok & sel], 1 - ALPHA / 2)
        cal = ok & ~sel
        score = np.maximum(lo_m.predict(Xf[cal]) - r[cal], r[cal] - hi_m.predict(Xf[cal]))
        n = int(cal.sum())
        Q = float(np.quantile(score, min(1.0, np.ceil((1 - ALPHA) * (n + 1)) / n)))
        models[k] = {"correction": _trees(corr), "lo": _trees(lo_m), "hi": _trees(hi_m), "Q": Q, "events": int(ok.sum())}
    DEPLOY.write_bytes(pickle.dumps(models))  # plain arrays: the Studio server, which loads torch, never loads LightGBM
    return {k: {"Q": v["Q"], "events": v["events"]} for k, v in models.items()}


def _trees(model) -> list[dict]:
    """A LightGBM model as arrays per tree (split feature, threshold, children, leaf values), so that it can be
    evaluated without LightGBM."""
    out = []
    for t in model.booster_.dump_model()["tree_info"]:
        feat, thr, left, right, dleft, leaf = [], [], [], [], [], []

        def walk(node) -> int:
            i = len(feat)
            feat.append(-1); thr.append(0.0); left.append(-1); right.append(-1); dleft.append(True); leaf.append(0.0)
            if "leaf_value" in node:
                leaf[i] = float(node["leaf_value"])
                return i
            assert node.get("decision_type", "<=") == "<=", "numeric splits only"
            feat[i], thr[i], dleft[i] = int(node["split_feature"]), float(node["threshold"]), bool(node["default_left"])
            left[i] = walk(node["left_child"])
            right[i] = walk(node["right_child"])
            return i

        walk(t["tree_structure"])
        out.append({"feat": np.array(feat), "thr": np.array(thr), "left": np.array(left), "right": np.array(right),
                    "dleft": np.array(dleft), "leaf": np.array(leaf)})
    return out


def _predict_trees(trees: list[dict], X: np.ndarray) -> np.ndarray:
    out = np.zeros(len(X))
    for t in trees:
        for r in range(len(X)):
            i = 0
            while t["feat"][i] >= 0:
                v = X[r, t["feat"][i]]
                go_left = t["dleft"][i] if np.isnan(v) else v <= t["thr"][i]
                i = t["left"][i] if go_left else t["right"][i]
            out[r] += t["leaf"][i]
    return out


def load_deployed():
    import pickle

    return pickle.loads(DEPLOY.read_bytes()) if DEPLOY.exists() else None


def predict(engine, models, i: int) -> dict:
    """For each other use of parcel i: the engine's change in homes / value, the learned estimate and its 90%
    interval (the change in the parcel's homes and assessed value, as the held-out test measured it)."""
    from planarena.config import USE_KEYS

    out = {}
    base = engine.baseline_state
    u0 = int(engine.base_use[i])
    units0 = float(engine.obs_units[i])
    value0 = float(engine.obs_value[i])
    for u in range(len(USE_KEYS)):
        if u == u0:
            continue
        use = engine.base_use.copy()
        use[i] = u
        st = engine.parcel_state(use)
        fa1 = float(st["fa_total"][i])
        x = np.array([[np.log1p(engine.bldg[i]), np.log1p(fa1), np.log1p(engine.lot[i]), u0, u, units0,
                       np.log1p(value0), 1.0]])
        row = {}
        for k, m in models.items():
            p = float(st[k][i] - base[k][i])
            xf = _features(x, np.array([p]))
            row[k] = {"engine": p, "learned": p + float(_predict_trees(m["correction"], xf)[0]),
                      "lo": p + float(_predict_trees(m["lo"], xf)[0]) - m["Q"],
                      "hi": p + float(_predict_trees(m["hi"], xf)[0]) + m["Q"]}
        out[USE_KEYS[u]] = row
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        print(fit_deploy())
    else:
        main()
