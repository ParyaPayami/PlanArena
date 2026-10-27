"""The learned components: the policy's plans respect the budget and the allowed uses, the learned correction is
adopted only when it improves on held-out lots, and conformal intervals reach their coverage."""
import json

import numpy as np

from planarena.config import ROOT


def test_policy_plan_respects_budget_and_allowed_uses():
    import torch

    from planarena.models.policy import N_USES, decode

    rng = np.random.default_rng(0)
    n, budget = 40, 5
    allowed = rng.random((n, N_USES)) < 0.4
    logits = torch.as_tensor(rng.normal(0, 3, (n, 1 + N_USES)), dtype=torch.float32)
    plan = decode(logits, allowed, budget)
    changed = np.nonzero(plan > 0)[0]
    assert len(changed) <= budget
    assert all(allowed[i, plan[i] - 1] for i in changed)


def test_learned_correction_is_adopted_only_when_it_improves_heldout_error():
    r = json.loads((ROOT / "results" / "validation" / "yield_ml.json").read_text())
    for k, v in r["indicators"].items():
        e, c = v["engine"], v["engine_plus_residual_model"]
        better = c["mae"] < e["mae"] and abs(c["bias"]) < abs(e["bias"]) and (c["pearson_r"] or 0) >= (e["pearson_r"] or 0) - 1e-9
        assert v["adopted"] == better, k


_COVERAGE = """
import numpy as np
from planarena.models.yield_ml import ALPHA, _quantile
rng = np.random.default_rng(1)
n = 3000
X = rng.normal(size=(n, 4))
y = X[:, 0] * 2 + rng.standard_t(3, n) * (1 + np.abs(X[:, 1]))
fit, cal, test = np.split(rng.permutation(n), [1000, 2000])
lo, hi = _quantile(X[fit], y[fit], ALPHA / 2), _quantile(X[fit], y[fit], 1 - ALPHA / 2)
s = np.maximum(lo.predict(X[cal]) - y[cal], y[cal] - hi.predict(X[cal]))
Q = np.quantile(s, np.ceil((1 - ALPHA) * (len(cal) + 1)) / len(cal))
print(((y[test] >= lo.predict(X[test]) - Q) & (y[test] <= hi.predict(X[test]) + Q)).mean())
"""


def test_conformal_intervals_reach_their_coverage_on_exchangeable_data():
    """Run apart from torch: LightGBM and torch must not share a process."""
    import subprocess
    import sys

    out = subprocess.run([sys.executable, "-I", "-c", _COVERAGE], capture_output=True, text=True, check=True)
    cover = float(out.stdout.strip().splitlines()[-1])
    assert 0.87 <= cover <= 0.95


_TREES = """
import numpy as np, lightgbm as lgb
from planarena.models.yield_ml import GBM, _predict_trees, _trees
rng = np.random.default_rng(0)
X = rng.normal(size=(400, 6)); y = X[:, 0] * 3 + np.sin(X[:, 1]) + rng.normal(size=400)
X[rng.random(X.shape) < 0.05] = np.nan
m = lgb.LGBMRegressor(**GBM).fit(X, y)
print(float(np.abs(_predict_trees(_trees(m), X[:60]) - m.predict(X[:60])).max()))
"""


def test_deployed_trees_reproduce_lightgbm():
    """The Studio evaluates the learned correction from plain arrays (no LightGBM next to torch)."""
    import subprocess
    import sys

    out = subprocess.run([sys.executable, "-I", "-c", _TREES], capture_output=True, text=True, check=True)
    assert float(out.stdout.strip().splitlines()[-1]) < 1e-9
