# PlanArena

**PlanArena** is a land-use decision-support tool built on a city's digital twin, with a game-like interface. Change the use or density of one parcel or many, and it shows the social, economic and environmental gains and losses straight away, with sensitivity ranges. It suggests the best use for each parcel, shows the Pareto trade-off between goals, and lets five AI stakeholder agents negotiate a plan using game theory.

* **Desktop Studio** (`/`): the planner's workspace.
  * Map with select, box, lasso, block and address/BBL search.
  * Use and density (FAR) edits, a live scoreboard with ranges, and capacity.
  * Optimizer and Pareto explorer, stakeholder negotiation.
  * Saved studies with status, checklist, hearing date and history.
  * Desk tools: soft sites, notice radius, staff report.
  * Plan import with review, exports with provenance.
* **Phone game** (`/play`): an installable PWA with neighbourhood levels, missions, tap/drag painting, stars and an AI rival.

Demo city: Manhattan, 42,075 parcels from NYC DCP MapPLUTO 25v3.1. The source file's SHA-256 is recorded in `twin_meta.json` and in every export.

## Run it

```bash
cd ~/Desktop/PlanArena   # first time: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m planarena.api          # then open http://localhost:8787  (phone game: /play)
```

To rebuild everything from raw data:

```bash
.venv/bin/python -m planarena.twin.build     # digital twin: parcels, graph, raster, web layers
.venv/bin/python -m planarena.calibrate      # coefficients from LL84/LL97/CBECS/QCEW + LL84 validation
.venv/bin/python -m planarena.models.train   # baselines + GNN spatial CV + final model (~7 min, CPU)
cd web && npm install && npx vite build      # web app -> web/dist (served by the API)
.venv/bin/python -m pytest -q                # 28 tests
```

`planarena.calibrate` downloads the two LL84 extracts from NYC Open Data into `data/reference/` if they are missing, and records their SHA-256.

## What it does and where

| Capability | Where |
|---|---|
| Digital twin | `planarena/twin`: parcels, 3D massing, parcel graph (adjacency, kNN, same zoning), 50 m access raster, zoning rules-as-code |
| Impact of an intervention | `planarena/indicators`: 11 indicators across three pillars. The observed baseline is kept, and only changed parcels are modelled. A full-city evaluation takes about 18 ms, or about 50 ms with sensitivity ranges |
| Density edits | Each parcel can take a proposed FAR as well as a use. Capacity, soft sites and added zoning capacity are reported |
| Gains and losses by land use | The scoreboard's per-use table |
| GNN | `planarena/models`: relational GraphSAGE with a land-use fit head (masked-node training) and a tax-base value head |
| Several AI models | GNN, LightGBM, an iterated-best-response optimizer, a consensus optimizer, NSGA-III and game-theoretic agents |
| Optimal land use per parcel | `planarena/optimize/suggest.py`, the Optimize tab and the best-fit overlay |
| Pareto trade-offs | `planarena/optimize/pareto.py`: NSGA-III over a study area. Every plan is re-scored by the exact engine. Presets: Balanced, Social / Economy / Environment first |
| Negotiating agents | `planarena/agents/negotiation.py`: five stakeholders using Zeuthen–Harsanyi monotonic concession, with a reservation utility and a mediator fallback |
| Game theory | Nash bargaining, Kalai–Smorodinsky, utilitarian, egalitarian, the Pareto front and price of anarchy |
| Plan upload and evaluation | `POST /api/import` reads CSV, GeoJSON, zipped shapefile or GeoPackage. It reviews unmatched rows, duplicates, unknown uses, FAR issues and unchanged rows before you apply the plan |
| Studies and audit | `planarena/api/store.py`: SQLite studies (draft → under review → hearing scheduled → adopted/withdrawn) with a checklist, hearing date, history, and a hash-chained tamper-evident audit log |
| Outputs | Staff report (HTML), CSV/GeoJSON export, provenance JSON (source hash, coefficients, models, engine version) |
| Requirements traceability | `planarena/requirements.py` produces [docs/REQUIREMENTS_TRACEABILITY.md](docs/REQUIREMENTS_TRACEABILITY.md), mapping a de-identified municipal requirements catalogue to features |

## Coefficients: every value has a source and a range

| Coefficient | Source | Status |
|---|---|---|
| Building energy (site EUI by use) | NYC LL84 benchmarking 2024, Manhattan; floor-area-weighted mean, Q25–Q75 range | derived |
| Emission factor | NYC LL97 §28-320.3.1.1 (2024–2029) weighted by LL84 Manhattan fuel shares | derived |
| Floorspace per worker | EIA CBECS 2018 Table B2, scaled so the baseline equals BLS QCEW New York County employment (Dec 2024: 2,480,984) | calibrated |
| Persons per household | Census QuickFacts, New York County, 2020–2024: 2.00 | corroborated (page is bot-protected; confirm) |
| Runoff C | NYC DEP surface coefficients (roof 1.00, pavement 0.85, other 0.75, grass 0.20), from the DCP 15 Penn Plaza FEIS worksheet, weighted by each parcel's roof share from MapPLUTO | derived; ground cover of open space and vacant lots is an assumption |
| Unit size, values, service targets | Derived from MapPLUTO itself (medians; Q25/Q75 multipliers for ranges) | derived |
| Build-out utilization | 0.8 (0.6–1.0) | assumption |

The Studio's Methods dialog (ⓘ) shows the full register, the provenance and the audit-chain check.

## Validation

**Emissions against metered buildings.** `results/validation_emissions_ll84.json` compares modelled emissions with LL84 metered energy × LL97 factors for 9,188 Manhattan buildings matched by BBL:

| Measure | Value |
|---|---|
| log–log correlation | 0.808 |
| Median absolute error | 34% per building |
| Aggregate modelled / metered | 1.07 (8.18 vs 7.63 Mt) |

This check is in-sample: the EUIs are fitted to the same LL84 year. Use-type averages reproduce totals well and individual buildings only roughly. With medians instead of weighted means, the median error is 26% but totals are 16% low. Totals matter more for plan comparison.

**Models, spatial-block cross-validation** (whole 600 m tiles held out):

| Task | GNN | LightGBM | Simple baseline |
|---|---|---|---|
| Land-use fit, accuracy | 0.671 ± 0.016 | **0.689 ± 0.013** | 0.593 (zoning majority) |
| Land-use fit, log loss | 0.918 | **0.912** | 1.192 |
| Value, R² | 0.621 ± 0.075 | **0.702 ± 0.048** | 0.540 (median by use and district) |

The GNN beats the simple baselines, but tuned LightGBM is still stronger. This is reported as is.

**Negotiation.** In CD 103, 105 and 110, the agents reached the Nash bargaining solution without the mediator, and every agent gained. With fragmented control of parcels, the price of anarchy is about 1.5.

## Honesty rules built in
* Each coefficient carries a status: verified, derived, calibrated, corroborated, assumption or provisional. An indicator is flagged ≈ while any coefficient it depends on is still provisional; none is at the moment.
* Ranges are a sensitivity envelope from low and high coefficient variants. They are not calibrated prediction intervals.
* Zoning is a simplified rules-as-code version of the NYC Zoning Resolution. The Studio treats it as advisory; the optimizer treats it as a hard constraint.
* The optimizer protects landmarks and historic districts, parks, public facilities, infrastructure and existing homes. It never demolishes unless that is explicitly allowed.
* No language model makes any decision. Agents decide through an auditable game-theory engine.
* No human-participant data is used.

## Known limitations and next steps
1. **LLM-voiced agents.** No API key or local model is configured, so the agents' explanations are templated. With `ANTHROPIC_API_KEY` or a local model, they could argue in natural language while the engine still decides.
2. **LL84 covers only buildings of 25,000 sq ft or more.** Small buildings take the same use-type EUIs.
3. **Roof share** is estimated as floor area / floors. NYC building footprints would measure it directly.
4. **Out-of-sample validation.** Next steps:
   * a jobs check against LEHD LODES, which needs a file download;
   * EUIs fitted on one LL84 year and tested on the next;
   * replay of observed land-use change from past PLUTO releases.
5. **GNN.** Try HGT, explicit neighbour-composition inputs, and a GNN + LightGBM ensemble.
6. **Imagery** is not used. NAIP and Sentinel-2 are open and could feed a vision branch; Google Street View may not be used for training.
7. **More cities.** The twin builder is city-agnostic once parcels, zoning and land-use codes are mapped.
