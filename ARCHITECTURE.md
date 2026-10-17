# PlanArena: architecture (v0.3)

PlanArena is a land-use decision-support system on a city's digital twin, with a game-like interface. A planner, or a player on a phone, changes parcels' use or density. The tool then shows the social, economic and environmental gains and losses straight away, and suggests the best use for each parcel. Stakeholder agents and today's residents vote on candidate plans under nine social-choice rules.

```
 Open data: MapPLUTO 25v3.1 · LL84 2024 · LL97 factors · CBECS 2018 · QCEW 2024 · NYC DEP runoff C
        │  planarena/twin/build.py            planarena/calibrate.py (+ LL84 validation)
        ▼                                     ▼
 DIGITAL TWIN (planarena/twin)          calibrated.yaml (generated) over coefficients.yaml
   parcels · 3D massing · parcel graph (adjacency, kNN, same zoning) ·
   50 m access raster · zoning rules-as-code · source SHA-256
        │
        ├── IMPACT ENGINE (planarena/indicators)       ~18 ms city-wide, ~50 ms with ranges
        │     observed baseline; only changed parcels are modelled (use and/or FAR)
        │     11 indicators, 3 pillars · capacity and soft sites · low/high variants → ranges
        │
        ├── ML MODELS (planarena/models)
        │     relational GraphSAGE (PyG): land-use fit head + value head
        │     LightGBM baselines · spatial-block CV (600 m tiles, 5 folds)
        │     transition.py: 5-year redevelopment likelihood + likely new use (LightGBM / GNN),
        │       temporal holdout 2015→2020 / 2020→2025; conversion precedents (realism)
        │
        ├── VALIDATION (planarena/validate.py) against LL84 2023, LODES 2023, MapPLUTO 15v1/20v8,
        │     and the East Harlem, SoHo/NoHo and Inwood rezoning EISs -> docs/VALIDATION.md
        │
        ├── OPTIMIZER (planarena/optimize)
        │     suggest.py: iterated best response (potential game), protections, consensus mode,
        │       exact polish of the top moves, no conversions without precedent
        │     indicators/rwcds.py: CEQR-style development-site screen (rezoning test)
        │     pareto.py: NSGA-III over a study area, exact re-scoring, named presets
        │
        └── STAKEHOLDER VOTE + GAME THEORY (planarena/agents)
              5 stakeholders with utilities over indicators; council seats
              voting.py: ballots from utilities · 9 rules (Schulze decides; Kemeny exact ILP) ·
                Condorcet / Smith · robustness (Monte Carlo) · strategic-voting check ·
                residents' referendum by tax block · parcel-by-parcel ballot · double majority
              gametheory.py: Nash, Kalai–Smorodinsky, utilitarian, egalitarian · Pareto · price of anarchy
              negotiation.py: candidate generation; Zeuthen–Harsanyi bargaining (research mode)
        │
   FastAPI (planarena/api)
     app.py     strict pydantic models · evaluate / suggest / pareto / vote / radius / search
     store.py   SQLite studies: status workflow, checklist, hearing date, history;
                hash-chained tamper-evident audit log
     planio.py  import (CSV, GeoJSON, zipped SHP, GPKG) with review · exports · provenance · staff report
        │
   web/ (React 18 + MapLibre + deck.gl 9.1, zustand; PWA service worker)
     /       Studio: Impact · Optimize · Vote · Studies · Desk · Import/Export · Methods
     /play   Game: neighbourhood levels, missions, stars, council vote against the AI planner
```

## Rules
- **Observed values are the baseline.** Only the parcels a user changes are modelled, so an undo returns exactly to the baseline.
- **Every coefficient has a source, a status and a range.** Generated values come from `python -m planarena.calibrate`, never from hand edits. An indicator is flagged ≈ while any coefficient it depends on is provisional.
- **Ranges are a sensitivity envelope, not prediction intervals.**
- **Results come from code.** Every number in the README and the thesis is generated from result files (`results/*.json`).
- **Zoning is advisory in the Studio and binding in the optimizer.** Planners may propose rezonings, so a conflict shows a warning rather than blocking the edit.
- **Decisions are auditable.** No language model is used; ballots come from utilities. Each study change and service start is written to the hash-chained audit log, and `/api/health` verifies the chain.
- **No human-participant data.** The municipal requirements catalogue is used as a document, de-identified (`planarena/requirements.py`).
