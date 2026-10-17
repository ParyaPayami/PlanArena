"""Land use of Tier A pseudo-lots, learned from Tier B cities and tested on a city it has not seen.

Inputs are only what Tier A has everywhere (planarena.cities.tier_a.lot_features: building size and height, Overture
building classes, places and land-use polygons, census-block housing and population, and the rule-based label).
Labels are the Tier B parcel use under each built pseudo-lot's representative point. Leave-one-city-out: train on the
other Tier B cities, test on the held-out one, next to the rules on the same lots. The deployed model is trained on
all Tier B cities and used by the Tier A builder only if it beats the rules in every held-out city.

Run:  python -I -m planarena.cities.landuse_model      (after planarena.cities.compare has built the Tier A twins)
"""
from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from planarena.config import DATA, ROOT, USE_KEYS
from planarena.models.common import SEED
from planarena.national.common import NATIONAL



def cities() -> list[str]:
    """Tier B cities with a Tier A test twin (built by planarena.cities.compare)."""
    return sorted(d.name[len("tierA_"):] for d in (DATA / "cities").glob("tierA_*") if (d / "lot_features.parquet").exists())
MODEL = NATIONAL / "landuse_model.txt"
META = NATIONAL / "landuse_model.json"
OUT = ROOT / "results" / "validation" / "landuse_model.json"


def dataset(city: str) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Features, Tier B label and rule label of the built pseudo-lots of the Tier A twin of a Tier B city."""
    work = DATA / "cities" / f"tierA_{city}"
    f = pd.read_parquet(work / "lot_features.parquet")
    pa = pd.read_parquet(work / "parcels.parquet")
    from planarena.cities.compare import config

    tb = config(city)["dir"]
    gb = gpd.read_parquet(tb / "parcels.geoparquet")
    pb = pd.read_parquet(tb / "parcels.parquet")
    ga = gpd.read_parquet(work / "parcels.geoparquet").to_crs(gb.crs)
    a, k = shapely.STRtree(gb.geometry.values).query(ga.geometry.representative_point().values, predicate="within")
    truth = np.full(len(pa), -1)
    truth[a] = pb.use.to_numpy()[k]
    rule = f[[f"rule_{u}" for u in USE_KEYS]].to_numpy().argmax(1)
    keep = (truth >= 0) & (pa.bldg_area.to_numpy() > 0)
    return f[keep].reset_index(drop=True), truth[keep], rule[keep]


def _fit(X: pd.DataFrame, y: np.ndarray):
    import lightgbm as lgb

    m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=63, min_child_samples=30, subsample=0.8,
                           subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=SEED)
    m.fit(X, y)
    return m


def _scores(y: np.ndarray, p: np.ndarray) -> dict:
    f1 = []
    for c in sorted(set(y)):
        tp = np.sum((p == c) & (y == c))
        prec, rec = tp / max(np.sum(p == c), 1), tp / max(np.sum(y == c), 1)
        f1.append(0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec))
    per = {USE_KEYS[c]: round(float(np.mean(p[y == c] == c)), 3) for c in sorted(set(y))}
    return {"accuracy": round(float(np.mean(y == p)), 3), "macro_f1": round(float(np.mean(f1)), 3), "recall_by_use": per}


def evaluate() -> dict:
    data = {c: dataset(c) for c in cities()}
    res = {"test": __doc__.strip().split("\n\n")[1], "held_out": {},
           "variants_tried": ["LightGBM with balanced class weights (2026-10-17): worse than the rules in both held-out "
                              "cities (Manhattan accuracy 0.455, Milwaukee 0.372)",
                              "LightGBM unweighted with two Tier B cities (2026-10-17): worse than the rules in Milwaukee "
                              "(0.595 vs 0.908), not deployed",
                              "LightGBM unweighted with all Tier B cities with a Tier A test twin (reported here)"]}
    for test in data:
        train = [c for c in data if c != test]
        if not train:
            continue
        X = pd.concat([data[c][0] for c in train], ignore_index=True)
        y = np.concatenate([data[c][1] for c in train])
        m = _fit(X, y)
        Xt, yt, rt = data[test]
        pred = m.classes_[m.predict_proba(Xt[X.columns]).argmax(1)]
        res["held_out"][test] = {"trained_on": train, "n": int(len(yt)),
                                 "model": _scores(yt, pred), "rules": _scores(yt, rt),
                                 "majority_class_accuracy": round(float(np.bincount(yt).max() / len(yt)), 3)}
    ho = res["held_out"].values()
    res["model_beats_rules_everywhere"] = bool(ho) and all(
        h["model"]["macro_f1"] > h["rules"]["macro_f1"] and h["model"]["accuracy"] >= h["rules"]["accuracy"] - 0.01 for h in ho)
    OUT.write_text(json.dumps(res, indent=2))
    if res["model_beats_rules_everywhere"]:
        X = pd.concat([d[0] for d in data.values()], ignore_index=True)
        y = np.concatenate([d[1] for d in data.values()])
        m = _fit(X, y)
        m.booster_.save_model(str(MODEL))
        META.write_text(json.dumps({"features": list(X.columns), "classes": [int(c) for c in m.classes_],
                                    "trained_on": list(data), "evaluation": str(OUT.relative_to(ROOT))}, indent=2))
    else:
        MODEL.unlink(missing_ok=True)
        META.unlink(missing_ok=True)
    return res


def predict(feats: pd.DataFrame) -> np.ndarray | None:
    """Most likely use of every lot, or None when no model passed its held-out test."""
    if not MODEL.exists():
        return None
    import lightgbm as lgb

    meta = json.loads(META.read_text())
    b = lgb.Booster(model_file=str(MODEL))
    p = b.predict(feats.reindex(columns=meta["features"], fill_value=0.0).to_numpy())
    return np.array(meta["classes"])[p.argmax(1)]


if __name__ == "__main__":
    r = evaluate()
    for c, h in r["held_out"].items():
        print(c, "model", h["model"]["accuracy"], h["model"]["macro_f1"], "| rules", h["rules"]["accuracy"], h["rules"]["macro_f1"],
              "| majority", h["majority_class_accuracy"])
    print("deployed:", r["model_beats_rules_everywhere"])
