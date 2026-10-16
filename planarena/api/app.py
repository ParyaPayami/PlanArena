"""PlanArena API (FastAPI).

Run:  python -m planarena.api           (serves the built web app from web/dist, if present)
Dev:  uvicorn planarena.api.app:app --reload --port 8787
"""
from __future__ import annotations

import csv
import io
import json
import time
from functools import lru_cache
from typing import Literal

import numpy as np
import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, ORJSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from planarena.agents.negotiation import generate_candidates, negotiate, price_of_anarchy
from planarena.agents.stakeholders import DEFAULT_STAKEHOLDERS
from planarena.config import LAND_USES, PLUTO_TO_USE, PROCESSED, ROOT, USE_INDEX, USE_KEYS, WEB_DATA
from planarena.indicators.engine import INDICATORS, ImpactEngine, load_engine
from planarena.optimize.suggest import SuggestConfig, Suggester

app = FastAPI(title="PlanArena API", version="0.1.0", default_response_class=ORJSONResponse)
app.add_middleware(GZipMiddleware, minimum_size=2000)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
STAKE = {s.key: s for s in DEFAULT_STAKEHOLDERS}


# ----------------------------------------------------------------------------- state
@lru_cache(maxsize=1)
def runtime() -> dict:
    t0 = time.time()
    engine = load_engine()
    suit, model_info = None, {"gnn": False}
    if (PROCESSED / "suitability.npy").exists():
        suit = np.load(PROCESSED / "suitability.npy")
        model_info["gnn"] = True
        _attach_value_model(engine)
    cv = ROOT / "results" / "gnn_cv.json"
    if cv.exists():
        model_info["cv_summary"] = json.loads(cv.read_text()).get("cv_summary")
    sug = Suggester(engine, suit)
    sug.per_use_values()
    return {"engine": engine, "suggester": sug, "suitability": suit, "model_info": model_info,
            "startup_seconds": round(time.time() - t0, 2)}


def _attach_value_model(engine: ImpactEngine) -> None:
    """Use the GNN value head for counterfactual value deltas of changed parcels."""
    import torch

    from planarena.models.gnn import ParcelGNN

    ckpt = torch.load(PROCESSED / "gnn.pt", map_location="cpu")
    model = ParcelGNN(ckpt["in_dim"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    ctx = torch.tensor(np.load(PROCESSED / "gnn_context.npy"))
    lot = engine.lot

    @torch.no_grad()
    def value_fn(use: np.ndarray, idx: np.ndarray) -> np.ndarray:
        i = torch.as_tensor(idx, dtype=torch.long)
        u = torch.as_tensor(np.clip(use[idx], 0, None), dtype=torch.long)
        log_psf = model.value(ctx[i], u).numpy()
        return np.expm1(log_psf) * lot[idx]

    engine.value_model = value_fn


def _use_array(changes: dict[str, str] | None) -> np.ndarray:
    e: ImpactEngine = runtime()["engine"]
    use = e.base_use.copy()
    for k, v in (changes or {}).items():
        i = int(k)
        if not 0 <= i < e.n:
            raise HTTPException(400, f"parcel index out of range: {k}")
        if v not in USE_INDEX:
            raise HTTPException(400, f"unknown land use: {v}")
        use[i] = USE_INDEX[v]
    return use


def _changes_of(use: np.ndarray) -> dict[str, str]:
    e: ImpactEngine = runtime()["engine"]
    idx = np.nonzero(use != e.base_use)[0]
    return {str(int(i)): USE_KEYS[int(use[i])] for i in idx}


# ----------------------------------------------------------------------------- models
class EvalRequest(BaseModel):
    changes: dict[str, str] = Field(default_factory=dict, description="parcel index -> land-use key")
    scope: str = "affected"
    pillar_weights: dict[str, float] | None = None


class SuggestRequest(BaseModel):
    scope: str = "city"
    mode: str = "balanced"  # balanced | consensus | <stakeholder key>
    pillar_weights: dict[str, float] | None = None
    max_change_share: float = 0.05
    respect_zoning: bool = True
    allow_demolition: bool = False
    parcels: list[int] | None = None  # restrict suggestions to these parcels
    changes: dict[str, str] = Field(default_factory=dict)  # start from the user's plan


class NegotiateRequest(BaseModel):
    scope: str = "cd:103"
    parcels: list[int] | None = None
    changes: dict[str, str] = Field(default_factory=dict)
    max_change_share: float = 0.05


# ----------------------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    r = runtime()
    return {"ok": True, "startup_seconds": r["startup_seconds"], "gnn": r["model_info"]["gnn"]}


@app.get("/api/meta")
def meta():
    r = runtime()
    e: ImpactEngine = r["engine"]
    coef = yaml.safe_load((ROOT / "planarena/indicators/coefficients.yaml").read_text())
    provenance = {k: {"status": v.get("status"), "source": v.get("source")}
                  for k, v in coef.items() if isinstance(v, dict) and "status" in v}
    base = e.evaluate(e.base_use, scope="city")
    return {
        "city": e.meta["city"], "source": e.meta["source"], "n_parcels": e.n,
        "bbox": e.meta["bbox_wgs84"], "levels": e.meta["levels"],
        "land_uses": [{"key": u.key, "label": u.label, "color": u.color, "built": u.built} for u in LAND_USES],
        "indicators": [{"key": i.key, "label": i.label, "unit": i.unit, "pillar": i.pillar,
                        "direction": i.direction, "kind": i.kind, "provisional": i.provisional} for i in INDICATORS],
        "baseline_city": {row["key"]: row["baseline"] for row in base["indicators"]},
        "stakeholders": [s.to_dict() for s in DEFAULT_STAKEHOLDERS],
        "derived": e.derived_summary(), "provenance": provenance,
        "zoning_rules": e.meta["zoning_rules"], "models": r["model_info"],
    }


@app.get("/api/parcel/{i}")
def parcel(i: int):
    r = runtime()
    e: ImpactEngine = r["engine"]
    if not 0 <= i < e.n:
        raise HTTPException(404, "parcel not found")
    row = e.p.iloc[i]
    allowed = [USE_KEYS[k] for k in range(len(USE_KEYS)) if (int(row.allowed) >> k) & 1]
    pu = r["suggester"].per_use_values()
    out = {
        "i": i, "bbl": int(row.bbl), "address": row.address, "cd": int(row.cd), "zone": row.zone,
        "overlay": row.overlay, "special_district": row.special, "use": USE_KEYS[int(row.use)] if row.use >= 0 else None,
        "lot_area_sqft": float(row.lot_area), "bldg_area_sqft": float(row.bldg_area), "floors": float(row.floors),
        "units": float(row.units_res), "assessed_value": float(row.assess_tot), "year_built": int(row.year_built),
        "landmark": bool(row.landmark), "historic_district": bool(row.historic), "allowed_uses": allowed,
        "per_use": {USE_KEYS[u]: {k: float(pu[k][i, u]) for k in ("homes", "jobs", "value", "ghg", "runoff", "green_space")}
                    for u in range(len(USE_KEYS))},
    }
    if r["suitability"] is not None:
        out["suitability"] = {USE_KEYS[u]: float(r["suitability"][i, u]) for u in range(len(USE_KEYS))}
    return out


@app.get("/api/suitability")
def suitability():
    """Compact arrays for the map overlay: top use and its probability for each parcel."""
    s = runtime()["suitability"]
    if s is None:
        raise HTTPException(404, "GNN not trained yet")
    return {"top": s.argmax(1).astype(int).tolist(), "p": np.round(s.max(1), 3).tolist()}


@app.post("/api/evaluate")
def evaluate(req: EvalRequest):
    e: ImpactEngine = runtime()["engine"]
    t0 = time.time()
    res = e.evaluate(_use_array(req.changes), scope=req.scope, pillar_weights=req.pillar_weights)
    res["ms"] = round(1000 * (time.time() - t0), 1)
    return res


def _suggest_config(req: SuggestRequest) -> SuggestConfig:
    cfg = SuggestConfig(scope=req.scope, max_change_share=req.max_change_share,
                        respect_zoning=req.respect_zoning, allow_demolition=req.allow_demolition,
                        candidate_parcels=np.array(req.parcels) if req.parcels else None)
    if req.pillar_weights:
        cfg.pillar_weights = req.pillar_weights
    if req.mode == "consensus":
        cfg.unanimity_weights = [s.normalized() for s in DEFAULT_STAKEHOLDERS]
    elif req.mode in STAKE:
        cfg.indicator_weights = STAKE[req.mode].normalized()
    return cfg


@app.post("/api/suggest")
def suggest(req: SuggestRequest):
    r = runtime()
    t0 = time.time()
    out = r["suggester"].suggest(_suggest_config(req), use=_use_array(req.changes))
    return {"changes": _changes_of(out["use"]), "evaluation": out["evaluation"], "history": out["history"],
            "budget": out["budget"], "eligible": out["eligible"], "ms": round(1000 * (time.time() - t0), 1)}


@app.post("/api/negotiate")
def negotiate_route(req: NegotiateRequest):
    r = runtime()
    t0 = time.time()
    cur = _use_array(req.changes) if req.changes else None
    plans = generate_candidates(r["suggester"], DEFAULT_STAKEHOLDERS, scope=req.scope,
                                max_change_share=req.max_change_share, current_use=cur,
                                candidate_parcels=np.array(req.parcels) if req.parcels else None)
    res = negotiate(plans, DEFAULT_STAKEHOLDERS)
    res["plan_changes"] = {p.id: _changes_of(p.use) for p in plans}
    res["plan_evaluations"] = {p.id: p.evaluation for p in plans}
    res["ms"] = round(1000 * (time.time() - t0), 1)
    return res


@app.post("/api/price-of-anarchy")
def poa(req: NegotiateRequest):
    return price_of_anarchy(runtime()["suggester"], DEFAULT_STAKEHOLDERS, req.scope, req.max_change_share)


def _parse_use(value) -> str | None:
    v = str(value).strip()
    if v in USE_INDEX:
        return v
    v2 = v.zfill(2)
    if v2 in PLUTO_TO_USE:
        return USE_KEYS[PLUTO_TO_USE[v2]]
    for u in LAND_USES:
        if v.lower() in (u.label.lower(), u.key):
            return u.key
    return None


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), scope: Literal["affected", "city"] = "affected"):
    """Evaluate an uploaded plan: GeoJSON features or CSV rows with a parcel id (bbl or i) and a land use."""
    e: ImpactEngine = runtime()["engine"]
    raw = await file.read()
    name = (file.filename or "").lower()
    rows = []
    try:
        if name.endswith((".geojson", ".json")):
            gj = json.loads(raw)
            rows = [f.get("properties", {}) for f in gj.get("features", [])]
        elif name.endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        else:
            raise HTTPException(400, "Upload a .geojson, .json or .csv file")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, f"Could not read file: {exc}") from exc
    bbl_to_i = {int(b): i for i, b in enumerate(e.p.bbl.to_numpy())}
    use = e.base_use.copy()
    matched, unmatched, bad_use = 0, [], []
    for r in rows:
        low = {str(k).lower(): v for k, v in r.items()}
        luv = next((low[k] for k in ("land_use", "landuse", "use", "proposed_use", "lu") if k in low), None)
        key = _parse_use(luv) if luv is not None else None
        idx = None
        if "i" in low and str(low["i"]).strip().isdigit():
            idx = int(low["i"])
        elif "bbl" in low:
            try:
                idx = bbl_to_i.get(int(float(low["bbl"])))
            except (TypeError, ValueError):
                idx = None
        if idx is None or not 0 <= idx < e.n:
            unmatched.append(low.get("bbl") or low.get("i"))
            continue
        if key is None:
            bad_use.append(luv)
            continue
        use[idx] = USE_INDEX[key]
        matched += 1
    res = e.evaluate(use, scope=scope)
    res["upload"] = {"rows": len(rows), "matched": matched, "unmatched": len(unmatched),
                     "unmatched_examples": unmatched[:10], "unknown_uses": sorted({str(b) for b in bad_use})[:10]}
    res["changes"] = _changes_of(use)
    return res


@app.get("/api/sample-plan.csv")
def sample_plan():
    """A small example upload: the first 40 parking lots in Lower Manhattan, turned residential."""
    e: ImpactEngine = runtime()["engine"]
    idx = np.nonzero((e.base_use == USE_INDEX["prk"]) & (e.cd == 103))[0][:40]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["bbl", "land_use"])
    for i in idx:
        w.writerow([int(e.p.bbl.iloc[i]), "res"])
    return _csv_response(buf.getvalue())


def _csv_response(text: str):
    return Response(text, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=planarena-sample-plan.csv"})


# ----------------------------------------------------------------------------- static web app
DIST = ROOT / "web" / "dist"
if WEB_DATA.exists():
    app.mount("/data", StaticFiles(directory=WEB_DATA), name="data")
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
