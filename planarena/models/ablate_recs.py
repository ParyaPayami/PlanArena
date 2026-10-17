"""Ablation of the realism layers: do recommended plans look more like what actually gets built?

The optimizer is run on the 2020 Manhattan snapshot in every community district (balanced weights, 2% change
budget, exact re-scoring of the top 30 moves), under three settings:
* no realism layer: conversions without precedent are allowed;
* precedent filter (the default): conversions of existing buildings never observed before 2020 at that size are
  skipped (precedent table as of 2020);
* precedent filter + likelihood layer: candidates restricted to the fifth of parcels most likely to be redeveloped
  within five years (redevelopment model trained on 2015->2020 only).
Recommended parcels are then compared with what happened by 2025 (redevelopment label; 2025 land use). This tests
plausibility, not desirability: a plan can be good without resembling the market.

Run:  python -I -m planarena.models.ablate_recs
"""
from __future__ import annotations

import json

import numpy as np

from planarena.config import ROOT
from planarena.models.common import SEED

OUT = ROOT / "results" / "validation" / "realism_ablation.json"
T0, T1 = 2020, 2025


def main() -> dict:
    import pandas as pd

    from planarena.indicators.engine import load_engine
    from planarena.models import rolling
    from planarena.models.history import snapshot_dir
    from planarena.models.transition import precedent
    from planarena.optimize.suggest import SuggestConfig, Suggester

    e = load_engine(snapshot_dir(T0))
    e.set_precedent(precedent(as_of=T0, write=False))
    sug = Suggester(e)
    lab = rolling._y(T0, T1)
    developed = lab.developed.to_numpy()
    p25 = pd.read_parquet(snapshot_dir(T1) / "parcels.parquet", columns=["use"]).use.to_numpy()
    use25 = np.where(lab.j1.to_numpy() >= 0, p25[np.clip(lab.j1.to_numpy(), 0, None)], -1)
    X, y = rolling._pool([(2015, 2020)])
    model = rolling._fit(X, y, SEED)
    p = model.predict_proba(rolling._x(T0))[:, 1]
    likely = np.nonzero(p >= np.quantile(p, 0.8))[0]

    settings = {"no realism layer": {"require_precedent": False},
                "precedent filter (default)": {"require_precedent": True},
                "precedent filter + likelihood layer": {"require_precedent": True, "candidate_parcels": likely}}
    res = {"test": __doc__.strip().split("\n\n")[1], "snapshot": T0, "outcome_year": T1, "settings": {}}
    for name, kw in settings.items():
        rec, new_use, score = [], [], []
        for cd in range(101, 113):
            cfg = SuggestConfig(scope=f"cd:{cd}", max_change_share=0.02, polish=30, **kw)
            out = sug.suggest(cfg)
            ch = np.asarray(out["changed"], dtype=int)  # indices of changed parcels
            rec.append(ch)
            new_use.append(out["use"][ch])
            score.append(out["evaluation"]["overall"])
        rec, new_use = np.concatenate(rec), np.concatenate(new_use)
        prec_ok = e.has_precedent(rec, new_use)
        res["settings"][name] = {
            "recommended_parcels": int(len(rec)),
            "share_without_precedent": round(float(1 - prec_ok.mean()), 3) if len(rec) else None,
            "share_redeveloped_by_2025": round(float(developed[rec].mean()), 4) if len(rec) else None,
            "share_with_recommended_use_in_2025": round(float((use25[rec] == new_use).mean()), 4) if len(rec) else None,
            "share_redeveloped_into_recommended_use": round(float((developed[rec] & (use25[rec] == new_use)).mean()), 4) if len(rec) else None,
            "median_district_plan_score": round(float(np.median(score)), 3),
        }
        print(name, res["settings"][name], flush=True)
    rows = (lab.matched & (lab.use0 >= 0)).to_numpy()
    res["reference"] = {"share_of_all_lots_redeveloped": round(float(developed[rows].mean()), 4),
                        "share_of_likely_fifth_redeveloped": round(float(developed[likely].mean()), 4)}
    OUT.write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    main()
