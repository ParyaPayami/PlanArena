# PlanArena

**PlanArena** turns a city's digital twin into a game for testing land-use plans. Change the use of one parcel or many, and the tool shows the social, economic and environmental gains and losses straight away. It can also suggest the best use for each parcel, or let five AI stakeholder agents negotiate a plan using game theory.

* **Desktop Studio** (`/`): a planner's workspace with the map, selection tools, a live scoreboard, the AI optimizer, the stakeholder negotiation and plan upload.
* **Phone game** (`/play`): neighbourhood levels with missions, tap/drag painting, stars, and an AI rival to beat.

Demo city: Manhattan, 42,075 parcels from NYC DCP MapPLUTO 25v3.1.

## Run it

```bash
cd ~/Desktop/PlanArena
.venv/bin/python -m planarena.api          # then open http://localhost:8787  (phone game: /play)
```

To rebuild everything from raw data:

```bash
.venv/bin/python -m planarena.twin.build     # digital twin: parcels, graph, raster, web layers (~6 s)
.venv/bin/python -m planarena.models.train   # baselines + GNN spatial CV + final model (~7 min, CPU)
cd web && npm install && npx vite build      # web app -> web/dist (served by the API)
.venv/bin/python -m pytest -q                # 19 tests
```

## How the requirements are met

| Requirement | Where |
|---|---|
| Digital twin of the city | `planarena/twin`: parcels, 3D massing, parcel graph (adjacency, kNN, same-zoning), 50 m access raster, zoning rules-as-code, and a 3D view in the app |
| Impact of an intervention: social, economic, environmental | `planarena/indicators`: 11 indicators. The baseline is the observed data, and only changed parcels are modelled. A full-city evaluation takes about 16 ms |
| Gains and losses by land use | The scoreboard's "Gains & losses by land use" table |
| GNN | `planarena/models`: relational GraphSAGE with two heads, land-use fit (masked-node training) and tax-base value |
| Several AI models | GNN, LightGBM baselines, an iterated-best-response optimizer, a consensus optimizer and game-theoretic agents |
| AI agents negotiating | `planarena/agents/negotiation.py`: five stakeholders, a Zeuthen–Harsanyi monotonic concession protocol, a reservation utility, and a mediator fallback |
| Game theory | Nash bargaining, Kalai–Smorodinsky, utilitarian, egalitarian, the Pareto front, and the price of anarchy of fragmented control |
| Optimal suggested land use for each parcel | `planarena/optimize/suggest.py` plus the AI optimizer tab and the "best-fit land use" overlay |
| Upload a plan to evaluate | The Upload tab and `POST /api/upload`, for CSV or GeoJSON with `bbl` or `i` plus `land_use` |
| Game-like phone version | `web/src/game`, an installable PWA |

## Model results (spatial-block cross-validation; whole 600 m tiles held out)

| Task | GNN | LightGBM | Simple baseline |
|---|---|---|---|
| Land-use fit, accuracy | 0.671 ± 0.016 | **0.689 ± 0.013** | 0.593 (zoning majority) |
| Land-use fit, log loss | 0.918 | **0.912** | 1.192 |
| Value, R² | 0.621 ± 0.075 | **0.702 ± 0.048** | 0.540 (median by use and district) |

The GNN beats the simple baselines, but tuned LightGBM with neighbour features is still stronger. This is reported as is in `results/gnn_cv.json` and in the app's model card. Improving the GNN is open work (see below).

In tests on CD 103, 105 and 110, the agents' negotiation reached the **Nash bargaining solution** without the mediator, and every agent gained. With fragmented control of parcels, the price of anarchy is about 1.5.

## Honesty rules built in
* Any coefficient without a verified source is tagged `provisional` in `planarena/indicators/coefficients.yaml`. Indicators that depend on one carry a ≈ mark in the UI.
* Zoning rules are a simplified rules-as-code version of the NYC Zoning Resolution. The Studio treats them as advisory; the optimizer treats them as hard constraints.
* The optimizer protects landmarks and historic districts, parks, public facilities, infrastructure and existing homes. It never demolishes buildings unless that is explicitly allowed.
* LLMs are not used for any decision. Agents decide through an auditable game-theory engine.

## Known limitations and next steps
1. **LLM-voiced agents.** No API key or local model is configured, so agents speak in templated sentences. With `ANTHROPIC_API_KEY` or a local Ollama model, the agents can argue in natural language, while the engine still makes the decisions.
2. **Coefficients.** Verify the provisional values against primary sources: EIA CBECS (jobs per sq ft), NYC LL84 (energy), NYC LL97 (emission factors), CEQR Technical Manual, and ACS household size.
3. **GNN.** Try HGT, longer training, explicit neighbour-composition inputs, and a GNN + LightGBM ensemble.
4. **Imagery** (not used yet). For a vision branch, add NAIP or Sentinel-2. Google Street View may not be used for training.
5. **More cities.** The twin builder is city-agnostic once parcels, zoning and land-use codes are mapped. UrbanTransformBench data can then add a "likelihood the change happens" layer.
6. **Validation.** Replay observed land-use changes and permits; heuristic usability review.
