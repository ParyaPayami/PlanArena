"""Impact engine: social, economic and environmental indicators for a land-use state.

Design:
* Calibrated baseline: an unchanged parcel keeps its observed MapPLUTO values.
  Only parcels whose land use changes are modelled, so undoing a change returns
  exactly to the baseline.
* Additive indicators (homes, jobs, value, emissions, runoff, green space) are
  per-parcel sums.
* Access indicators use a 50 m raster convolved with walk-radius disks, so a
  full city recompute takes milliseconds.
* Scores are relative changes within a scope (the affected area, a district or
  the whole city), signed so that a positive score is always a gain.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.signal import fftconvolve

from planarena.config import LAND_USES, PILLARS, PROCESSED, USE_INDEX, USE_KEYS

U = USE_INDEX
N_USES = len(USE_KEYS)
BUILT = np.array([u.built for u in LAND_USES])
COEF_PATH = Path(__file__).with_name("coefficients.yaml")
SQFT_PER_ACRE = 43560.0


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    unit: str
    pillar: str
    direction: int  # +1: more is better, -1: less is better
    kind: str       # "total" or "share"
    provisional: bool
    additive: bool


INDICATORS: tuple[Indicator, ...] = (
    Indicator("homes", "Homes", "units", "economic", 1, "total", False, True),
    Indicator("jobs", "Jobs", "jobs", "economic", 1, "total", True, True),
    Indicator("value", "Tax base (assessed value)", "USD", "economic", 1, "total", False, True),
    Indicator("park_access", "Park within 5-min walk", "% of residents", "social", 1, "share", False, False),
    Indicator("services_access", "Shops & services within 5-min walk", "adequacy 0-1", "social", 1, "share", False, False),
    Indicator("facility_access", "Community facilities within 10-min walk", "adequacy 0-1", "social", 1, "share", False, False),
    Indicator("mix", "Land-use mix around homes", "index 0-1", "social", 1, "share", False, False),
    Indicator("green_space", "Green & open space", "acres", "environmental", 1, "total", False, True),
    Indicator("runoff", "Stormwater runoff", "impervious-equiv. acres", "environmental", -1, "total", True, True),
    Indicator("ghg", "Building emissions", "tCO2e / yr", "environmental", -1, "total", True, True),
    Indicator("green_cover", "Green cover near homes", "% of land within 400 m", "environmental", 1, "share", False, False),
)
IND_KEYS = tuple(i.key for i in INDICATORS)
ADDITIVE = tuple(i.key for i in INDICATORS if i.additive)


def _disk(radius_cells: float) -> np.ndarray:
    r = int(np.ceil(radius_cells))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return (xx ** 2 + yy ** 2 <= radius_cells ** 2).astype("float64")


class ImpactEngine:
    def __init__(self, parcels: pd.DataFrame, meta: dict, coef_path: Path = COEF_PATH):
        self.p = parcels.reset_index(drop=True)
        self.meta = meta
        self.coef = yaml.safe_load(coef_path.read_text())
        self.n = len(self.p)
        self.base_use = self.p["use"].to_numpy().astype("int16")
        self.lot = self.p["lot_area"].to_numpy()
        self.bldg = self.p["bldg_area"].to_numpy()
        self.cd = self.p["cd"].to_numpy()
        self.allowed = self.p["allowed"].to_numpy().astype("int64")
        self.protected = (self.p["landmark"] | self.p["historic"]).to_numpy()
        self._derive()
        self._observed_components()
        self._grid()
        self.baseline_state = self.parcel_state(self.base_use)
        raw = self._raw_ratios(self.baseline_state)
        has = self.baseline_state["residents"] > 0
        self.t_serv = float(np.median(raw["serv"][has]))
        self.t_fac = float(np.median(raw["fac"][has]))
        self.value_model = None  # optional ML model: f(use_array, idx) -> values

    # ------------------------------------------------------------- derived coefficients
    def _derive(self) -> None:
        p = self.p
        res = p[p.use == U["res"]]
        ratio = res.res_area / res.units_res.replace(0, np.nan)
        self.sqft_per_unit = float(ratio[(ratio > 150) & (ratio < 10000)].median())
        mix = p[(p.use == U["mix"]) & (p.bldg_area > 0)]
        self.mix_res_share = float((mix.res_area / mix.bldg_area).clip(0, 1).median())
        com = p[p.use == U["com"]]
        tot = max(com.com_area.sum(), 1.0)
        self.com_mix = {
            "office": com.office_area.sum() / tot,
            "retail": com.retail_area.sum() / tot,
        }
        self.com_mix["other"] = max(0.0, 1 - self.com_mix["office"] - self.com_mix["retail"])
        ind = p[p.use == U["ind"]]
        it = max((ind.factory_area + ind.storage_area).sum(), 1.0)
        self.ind_mix = {"factory": ind.factory_area.sum() / it, "storage": ind.storage_area.sum() / it}
        # Value per sq ft, by use and district, from assessed values.
        built = p[p.bldg_area > 0]
        bpsf = ((built.assess_tot - built.assess_land).clip(lower=0) / built.bldg_area)
        self.bldg_psf = bpsf.groupby([built.use, built.cd]).median().to_dict()
        self.bldg_psf_use = bpsf.groupby(built.use).median().to_dict()
        self.bldg_psf_all = float(bpsf.median())
        lpsf = (p.assess_land / p.lot_area.replace(0, np.nan))
        self.land_psf_cd = lpsf.groupby(p.cd).median().to_dict()
        self.land_psf_all = float(lpsf.median())
        a = self.coef["assumptions"]
        self.util = float(a["buildout_utilization"]["value"])
        self.pph = float(a["persons_per_household"]["value"])
        far = np.zeros((self.n, N_USES))
        rf, cf, ff = (p[c].to_numpy() for c in ("resid_far", "comm_far", "facil_far"))
        mx = np.maximum.reduce([rf, cf, ff])
        far[:, U["res"]] = np.where(rf > 0, rf, mx)
        far[:, U["mix"]] = np.maximum(rf, cf)
        for k in ("com", "ind", "tra"):
            far[:, U[k]] = np.where(cf > 0, cf, mx)
        far[:, U["pub"]] = np.where(ff > 0, ff, mx)
        self.far = far

    def derived_summary(self) -> dict:
        return {
            "sqft_per_unit": round(self.sqft_per_unit, 1),
            "mixed_res_share": round(self.mix_res_share, 3),
            "commercial_mix": {k: round(v, 3) for k, v in self.com_mix.items()},
            "industrial_mix": {k: round(v, 3) for k, v in self.ind_mix.items()},
            "median_building_value_psf": round(self.bldg_psf_all, 1),
            "median_land_value_psf": round(self.land_psf_all, 1),
            "services_sqft_per_resident_target": round(self.t_serv, 1),
            "facility_sqft_per_resident_target": round(self.t_fac, 1),
        }

    # ------------------------------------------------------------- floor-area components
    COMPONENTS = ("res", "office", "retail", "other", "factory", "storage", "pubfac", "trafac")

    def _observed_components(self) -> None:
        p = self.p
        comp = {
            "res": p.res_area.to_numpy(),
            "office": p.office_area.to_numpy(),
            "retail": p.retail_area.to_numpy(),
            "other": p.other_area.to_numpy(),
            "factory": p.factory_area.to_numpy(),
            "storage": p.storage_area.to_numpy(),
        }
        nonres = np.clip(self.bldg - comp["res"], 0, None)
        use = self.base_use
        comp["pubfac"] = np.where(use == U["pub"], nonres, 0.0)
        comp["trafac"] = np.where(use == U["tra"], nonres, 0.0)
        # Commercial area with no recorded breakdown: allocate by the city's commercial mix.
        sub = comp["office"] + comp["retail"] + comp["other"] + comp["factory"] + comp["storage"]
        com_area = p.com_area.to_numpy()
        gap = np.where(np.isin(use, [U["com"], U["mix"]]) & (sub <= 0), com_area, 0.0)
        for k in ("office", "retail", "other"):
            comp[k] = comp[k] + gap * self.com_mix[k]
        # Public and transport lots: all non-residential floor area is counted once, as pubfac/trafac.
        facility_lot = np.isin(use, [U["pub"], U["tra"]])
        for k in ("office", "retail", "other", "factory", "storage"):
            comp[k] = np.where(facility_lot, 0.0, comp[k])
        self.obs = comp
        self.obs_units = p.units_res.to_numpy().astype("float64")
        # A changed building keeps its own observed unit size when it has one (calibration);
        # otherwise the city median applies.
        own = np.divide(p.res_area.to_numpy(), self.obs_units, out=np.zeros(self.n), where=self.obs_units > 0)
        self.unit_size = np.where((own > 250) & (own < 5000), own, self.sqft_per_unit)
        self.obs_value = p.assess_tot.to_numpy().astype("float64")

    def modelled_floor_area(self, use: np.ndarray, idx: np.ndarray) -> np.ndarray:
        """Total floor area of parcels ``idx`` under their new uses."""
        u = use[idx]
        keep = (self.bldg[idx] > 0) & BUILT[u]
        build_new = (self.bldg[idx] <= 0) & BUILT[u]
        fa = np.zeros(len(idx))
        fa[keep] = self.bldg[idx][keep]
        fa[build_new] = (self.lot[idx] * self.far[idx, u] * self.util)[build_new]
        return fa

    def _model_components(self, use: np.ndarray, idx: np.ndarray) -> dict[str, np.ndarray]:
        u = use[idx]
        fa = self.modelled_floor_area(use, idx)
        c = {k: np.zeros(len(idx)) for k in self.COMPONENTS}
        s = self.mix_res_share
        c["res"] = np.where(u == U["res"], fa, 0) + np.where(u == U["mix"], s * fa, 0)
        c["retail"] = np.where(u == U["mix"], (1 - s) * fa, 0) + np.where(u == U["com"], self.com_mix["retail"] * fa, 0)
        c["office"] = np.where(u == U["com"], self.com_mix["office"] * fa, 0)
        c["other"] = np.where(u == U["com"], self.com_mix["other"] * fa, 0)
        c["factory"] = np.where(u == U["ind"], self.ind_mix["factory"] * fa, 0)
        c["storage"] = np.where(u == U["ind"], self.ind_mix["storage"] * fa, 0)
        c["pubfac"] = np.where(u == U["pub"], fa, 0)
        c["trafac"] = np.where(u == U["tra"], fa, 0)
        c["_fa"] = fa
        return c

    def _model_value(self, use: np.ndarray, idx: np.ndarray, fa: np.ndarray) -> np.ndarray:
        land = np.array([self.land_psf_cd.get(int(d), self.land_psf_all) for d in self.cd[idx]])
        bpsf = np.array([
            self.bldg_psf.get((int(uu), int(d)), self.bldg_psf_use.get(int(uu), self.bldg_psf_all))
            for uu, d in zip(use[idx], self.cd[idx])
        ])
        return self.lot[idx] * np.nan_to_num(land) + fa * np.nan_to_num(bpsf)

    # ------------------------------------------------------------- per-parcel state
    def parcel_state(self, use: np.ndarray) -> dict[str, np.ndarray]:
        use = np.asarray(use, dtype="int16")
        changed = np.nonzero(use != self.base_use)[0]
        comp = {k: v.copy() for k, v in self.obs.items()}
        units = self.obs_units.copy()
        value = self.obs_value.copy()
        fa_total = self.bldg.copy()
        if len(changed):
            m = self._model_components(use, changed)
            for k in self.COMPONENTS:
                comp[k][changed] = m[k]
            units[changed] = m["res"] / self.unit_size[changed]
            fa_total[changed] = m["_fa"]
            if self.value_model is not None:
                v_new = self.value_model(use, changed)
                v_old = self.value_model(self.base_use, changed)
            else:
                v_new = self._model_value(use, changed, m["_fa"])
                old_fa = self.bldg[changed]
                v_old = self._model_value(self.base_use, changed, old_fa)
            value[changed] = np.clip(self.obs_value[changed] + v_new - v_old, 0, None)
        jc = self.coef["jobs_sqft_per_worker"]
        jobs = (comp["office"] / jc["office"]["value"] + comp["retail"] / jc["retail"]["value"]
                + comp["other"] / jc["other_commercial"]["value"] + comp["factory"] / jc["factory"]["value"]
                + comp["storage"] / jc["storage"]["value"] + comp["pubfac"] / jc["public_facility"]["value"]
                + comp["trafac"] / jc["transport_utility"]["value"])
        eui = self.coef["energy_site_eui_kbtu_per_sqft"]
        eui_by_use = np.array([eui[k]["value"] if k in eui else 0.0 for k in USE_KEYS])
        ghg = fa_total * eui_by_use[use] * self.coef["emissions_tco2e_per_kbtu"]["value"]
        rc = self.coef["runoff_coefficient_c"]
        c_by_use = np.array([rc[k]["value"] for k in USE_KEYS])
        safe_use = np.where(use >= 0, use, U["vac"])
        runoff = self.lot * c_by_use[safe_use] / SQFT_PER_ACRE
        green = np.where(use == U["opn"], self.lot, 0.0) / SQFT_PER_ACRE
        return {
            "use": use, "units": units, "residents": units * self.pph, "value": value,
            "jobs": jobs, "ghg": ghg, "runoff": runoff, "green_space": green,
            "homes": units, "services_fa": comp["retail"] + comp["other"], "pubfac_fa": comp["pubfac"],
            "fa_total": fa_total,
        }

    # ------------------------------------------------------------- access raster
    def _grid(self) -> None:
        g = self.meta["grid"]
        self.nx, self.ny = g["nx"], g["ny"]
        self.cell = (self.p["cy"].to_numpy() * self.nx + self.p["cx"].to_numpy()).astype("int64")
        acc = self.coef["access"]
        cm = g["cell_m"]
        self.k_walk = _disk(acc["walk_radius_m"] / cm)
        self.k_fac = _disk(acc["facility_radius_m"] / cm)
        self.park_min = acc["park_min_sqft"]

    def _raster(self, weights: np.ndarray) -> np.ndarray:
        r = np.bincount(self.cell, weights=weights, minlength=self.nx * self.ny)
        return r.reshape(self.ny, self.nx)

    def _within(self, weights: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """Value within the kernel around each parcel's cell."""
        conv = fftconvolve(self._raster(weights), kernel, mode="same")
        return np.clip(conv.ravel()[self.cell], 0, None)

    def _raw_ratios(self, st: dict) -> dict[str, np.ndarray]:
        """Floor area within the walk radius per resident within the same radius."""
        res_walk = self._within(st["residents"], self.k_walk)
        res_fac = self._within(st["residents"], self.k_fac)
        serv = np.divide(self._within(st["services_fa"], self.k_walk), res_walk,
                         out=np.zeros(self.n), where=res_walk > 1)
        fac = np.divide(self._within(st["pubfac_fa"], self.k_fac), res_fac,
                        out=np.zeros(self.n), where=res_fac > 1)
        return {"serv": serv, "fac": fac}

    def access(self, st: dict) -> dict[str, np.ndarray]:
        use = st["use"]
        open_area = np.where(use == U["opn"], self.lot, 0.0)
        park = self._within(open_area, self.k_walk) >= self.park_min
        raw = self._raw_ratios(st)
        # Adequacy indices (0-1): per-resident supply against the city's baseline median. Saturating.
        serv = np.clip(raw["serv"] / self.t_serv, 0, 1)
        fac = np.clip(raw["fac"] / self.t_fac, 0, 1)
        groups = [("res",), ("mix", "com"), ("ind", "tra"), ("pub",), ("opn",)]
        land = np.stack([
            self._within(np.where(np.isin(use, [U[k] for k in grp]), self.lot, 0.0), self.k_walk)
            for grp in groups
        ])
        tot = land.sum(axis=0)
        share = np.divide(land, tot, out=np.zeros_like(land), where=tot > 0)
        ent = -(share * np.log(np.where(share > 0, share, 1.0))).sum(axis=0) / np.log(len(groups))
        green_cover = np.divide(land[-1], tot, out=np.zeros_like(tot), where=tot > 0)
        return {"park_access": park, "services_access": serv, "facility_access": fac,
                "mix": ent, "green_cover": green_cover, "serv_raw": raw["serv"], "fac_raw": raw["fac"]}

    # ------------------------------------------------------------- aggregation
    def scope_mask(self, use: np.ndarray, scope: str = "affected") -> np.ndarray:
        if scope == "city":
            return np.ones(self.n, bool)
        if scope.startswith("cd:"):
            return self.cd == int(scope.split(":")[1])
        changed = (use != self.base_use).astype(float)
        if changed.sum() == 0:
            return np.ones(self.n, bool)
        return self._within(changed, self.k_fac) > 0.5

    def aggregate(self, st: dict, acc: dict, mask: np.ndarray) -> dict[str, float]:
        out = {k: float(st[k][mask].sum()) for k in ADDITIVE}
        w = st["residents"][mask]
        wsum = w.sum()
        for k in ("park_access", "services_access", "facility_access", "mix", "green_cover"):
            v = acc[k][mask].astype(float)
            out[k] = float((v * w).sum() / wsum) if wsum > 0 else float("nan")
        return out

    def evaluate(self, use: np.ndarray, scope: str = "affected", pillar_weights: dict | None = None) -> dict:
        use = np.asarray(use, dtype="int16")
        st = self.parcel_state(use)
        acc = self.access(st)
        base = self.baseline_state
        bacc = self._base_acc if hasattr(self, "_base_acc") else self._cache_base_acc()
        mask = self.scope_mask(use, scope)
        s_agg, b_agg = self.aggregate(st, acc, mask), self.aggregate(base, bacc, mask)
        city_s = self.aggregate(st, acc, np.ones(self.n, bool))
        city_b = self._city_base if hasattr(self, "_city_base") else self._cache_city_base()
        rows, pillar_scores = [], {p: [] for p in PILLARS}
        for ind in INDICATORS:
            b, s = b_agg[ind.key], s_agg[ind.key]
            d = s - b
            pct = 100 * d / abs(b) if b and np.isfinite(b) and abs(b) > 1e-9 else 0.0
            # Totals score as % change; bounded 0-1 shares score as percentage points.
            raw_score = 100 * d if ind.kind == "share" else pct
            score = float(np.clip(ind.direction * raw_score, -100, 100))
            pillar_scores[ind.pillar].append(score)
            row = asdict(ind) | {
                "baseline": b, "scenario": s, "delta": d, "pct": pct, "score": score,
                "city_baseline": city_b[ind.key], "city_scenario": city_s[ind.key],
                "city_delta": city_s[ind.key] - city_b[ind.key],
            }
            rows.append(row)
        pillars = {p: float(np.mean(v)) if v else 0.0 for p, v in pillar_scores.items()}
        pw = pillar_weights or {p: 1.0 for p in PILLARS}
        overall = float(sum(pillars[p] * pw.get(p, 0) for p in PILLARS) / max(sum(pw.values()), 1e-9))
        return {
            "scope": scope, "scope_parcels": int(mask.sum()),
            "n_changed": int((use != self.base_use).sum()),
            "indicators": rows, "pillars": pillars, "overall": overall,
            "by_use": self.by_use(st, base),
            "warnings": self.warnings(use),
        }

    def _cache_base_acc(self):
        self._base_acc = self.access(self.baseline_state)
        return self._base_acc

    def _cache_city_base(self):
        self._city_base = self.aggregate(self.baseline_state, self._base_acc if hasattr(self, "_base_acc") else self._cache_base_acc(), np.ones(self.n, bool))
        return self._city_base

    def by_use(self, st: dict, base: dict) -> list[dict]:
        out = []
        for u in LAND_USES:
            i = U[u.key]
            ms, mb = st["use"] == i, base["use"] == i
            row = {"use": u.key, "label": u.label, "color": u.color,
                   "parcels": int(ms.sum() - mb.sum()),
                   "acres": float((self.lot[ms].sum() - self.lot[mb].sum()) / SQFT_PER_ACRE)}
            for k in ("homes", "jobs", "value", "ghg", "runoff", "green_space"):
                row[k] = float(st[k][ms].sum() - base[k][mb].sum())
            out.append(row)
        return out

    def warnings(self, use: np.ndarray) -> list[dict]:
        changed = np.nonzero(use != self.base_use)[0]
        if not len(changed):
            return []
        bit = (self.allowed[changed] >> np.clip(use[changed], 0, None)) & 1
        zoning = changed[(bit == 0) & (use[changed] >= 0)]
        prot = changed[self.protected[changed]]
        lost_homes = changed[(self.obs_units[changed] > 0) & ~np.isin(use[changed], [U["res"], U["mix"]])]
        w = []
        if len(zoning):
            w.append({"type": "zoning", "count": int(len(zoning)), "parcels": zoning[:200].tolist(),
                      "message": f"{len(zoning)} parcel(s) changed to a use their zoning district does not normally allow (rezoning needed)."})
        if len(prot):
            w.append({"type": "protected", "count": int(len(prot)), "parcels": prot[:200].tolist(),
                      "message": f"{len(prot)} parcel(s) are landmarks or in historic districts."})
        if len(lost_homes):
            n_units = int(self.obs_units[lost_homes].sum())
            w.append({"type": "displacement", "count": int(len(lost_homes)), "parcels": lost_homes[:200].tolist(),
                      "message": f"{n_units} existing homes on {len(lost_homes)} parcel(s) would be removed or converted."})
        return w


def load_engine(processed: Path = PROCESSED) -> ImpactEngine:
    parcels = pd.read_parquet(processed / "parcels.parquet")
    meta = json.loads((processed / "twin_meta.json").read_text())
    return ImpactEngine(parcels, meta)
