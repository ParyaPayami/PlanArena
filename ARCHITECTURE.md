# PlanArena: architecture

PlanArena is a digital twin of a city that works like a game. A planner, or a player on a phone, recolours parcels to change their land use. The tool then shows the social, economic and environmental gains and losses straight away. It can also suggest the best use for each parcel. AI stakeholder agents can negotiate a plan using game theory.

```
 Open data (MapPLUTO; zoning; later: permits, LL84, ACS, imagery)
        │  planarena/twin/build.py
        ▼
 DIGITAL TWIN (planarena/twin)
   parcels table · 3D massing · parcel graph (adjacency, kNN, block) ·
   50 m accessibility raster · zoning rules-as-code · scenario store
        │
        ├── IMPACT ENGINE (planarena/indicators)        <100 ms per edit
        │     calibrated baseline (observed) + modelled deltas for changed parcels
        │     coefficients.yaml: every value has source + status
        │
        ├── ML MODELS (planarena/models)
        │     Hetero-GNN (PyG): land-use suitability head + value head
        │     baselines: LightGBM, MLP; spatial-block cross-validation
        │
        ├── OPTIMIZER (planarena/optimize)
        │     per-parcel suggestion = iterated best response (potential game)
        │     NSGA-III Pareto set for a selected area (pymoo)
        │
        └── AGENTS + GAME THEORY (planarena/agents)
              stakeholder agents with utility over indicators
              Zeuthen–Harsanyi alternating-offer negotiation → Nash bargaining solution
              Kalai–Smorodinsky / utilitarian comparisons, price of anarchy
              optional LLM voice for agent arguments; decisions stay in the
              auditable game engine
        │
   FastAPI (planarena/api) ──► web/ (React + MapLibre + deck.gl)
                                 /       Studio: desktop, upload plan, compare, report
                                 /play   Game: mobile, missions, stars, AI rival
```

## Rules
- **Observed values are the baseline.** Only the parcels a user changes are modelled.
- **Uncertainty is labelled.** Any coefficient without a verified source is marked `provisional`, and the UI shows that.
- **Results come from code.** No numbers are typed into reports or the thesis by hand; they are generated from result files.
- **Zoning is advisory in the Studio.** Planners may propose rezonings, so a conflict shows a warning rather than blocking the edit. Zoning is a hard constraint in the optimizer by default.
