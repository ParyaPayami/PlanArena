# PlanArena

**PlanArena** is a land-use decision-support tool built on a city's digital twin, with a game-like interface. Change the use or density of one parcel or many, and it shows the social, economic and environmental gains and losses straight away, with sensitivity ranges. It suggests the best use for each parcel, shows the Pareto trade-off between goals, and puts candidate plans to a comprehensive stakeholder vote: a council of five stakeholder agents, a residents' referendum by tax block, and a parcel-by-parcel ballot.

* **Desktop Studio** (`/`): the planner's workspace.
  * Map with select, box, lasso, block and address/BBL search.
  * Use and density (FAR) edits, a live scoreboard with ranges, and capacity.
  * Optimizer and Pareto explorer, stakeholder vote.
  * Saved studies with status, checklist, hearing date and history.
  * Desk tools: soft sites, notice radius, staff report.
  * Plan import with review, exports with provenance.
* **Phone game** (`/play`): an installable PWA with neighbourhood levels, missions, tap/drag painting and stars. At the end, the stakeholder council votes between your plan, the AI planner's plan and no change.

Demo city: Manhattan, 42,075 parcels from NYC DCP MapPLUTO 25v3.1, downloaded from DCP by `planarena.twin.fetch`. The archive's and the extract's SHA-256 are recorded in `twin_meta.json` and in every export.

## Run it

```bash
cd PlanArena   # first time: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m planarena.api          # then open http://localhost:8787  (phone game: /play)
```

To rebuild everything from raw data:

```bash
.venv/bin/python -I -m planarena.twin.fetch  # official MapPLUTO 25v3.1 (300 MB) -> Manhattan extract + SOURCE.json
.venv/bin/python -m planarena.twin.build     # digital twin: parcels, graph, raster, web layers
.venv/bin/python -m planarena.calibrate      # coefficients from LL84/LL97/CBECS/QCEW + LL84 validation
.venv/bin/python -m planarena.models.train   # baselines + GNN spatial CV + final model (~7 min, CPU)
.venv/bin/python -I -m planarena.models.transition all  # redevelopment-transition model + conversion precedents
.venv/bin/python -m planarena.agents.voting   # stakeholder vote in all 12 districts -> results/vote_summary.json
.venv/bin/python -I -m planarena.validate all  # validation against open data -> results/validation, docs/VALIDATION.md
cd web && npm install && npx vite build      # web app -> web/dist (served by the API)
.venv/bin/python -m pytest -q                # 46 tests
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
| Stakeholder vote | `planarena/agents/voting.py`. No language model: each ballot comes from a voter's utilities. See below |
| Game theory | Nash bargaining, Kalai–Smorodinsky, utilitarian and egalitarian solutions, the Pareto front and price of anarchy, all compared with the vote. A Zeuthen–Harsanyi bargaining protocol is kept in `negotiation.py` as a research mode |
| Plan upload and evaluation | `POST /api/import` reads CSV, GeoJSON, zipped shapefile or GeoPackage. It reviews unmatched rows, duplicates, unknown uses, FAR issues and unchanged rows before you apply the plan |
| Studies and audit | `planarena/api/store.py`: SQLite studies (draft → under review → hearing scheduled → adopted/withdrawn) with a checklist, hearing date, history, and a hash-chained tamper-evident audit log |
| Outputs | Staff report (HTML), CSV/GeoJSON export, provenance JSON (source hash, coefficients, models, engine version) |
| Redevelopment likelihood | `planarena/models/transition.py`: five-year likelihood and likely new use for every lot (Optimize tab overlay, parcel inspector) |
| Rezoning test | `planarena/indicators/rwcds.py`: the development-site screen city environmental reviews use, applied to the FAR values in a plan (Desk tab) |
| Realism | Conversions of existing buildings never seen in Manhattan 2015–2025 at that size are flagged, and the optimizer skips them |
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

Full results are in [docs/VALIDATION.md](docs/VALIDATION.md). They are generated by `python -I -m planarena.validate all` from downloaded open data, and the hashes are in `results/validation/`.

| What is tested | Against | Result |
|---|---|---|
| Building emissions, **out of sample** | LL84 2023 metered energy, 6,238 buildings (fitted on 2024) | log–log r 0.795; total 1.07× metered; median building error 37% |
| Jobs, where they are | LEHD LODES 2023 workplace jobs | Total 2,480,984 vs 2,504,522; tract r 0.816, block r 0.704 |
| Homes from floor area | 295 parcels developed 2015–2025 (MapPLUTO 15v1 → 25v3.1) | 1.089× recorded homes; r 0.894; median error 28% |
| **East Harlem rezoning** (2017) | The city's FEIS, 68 projected development sites | Same sites and FAR: 0.969× the FEIS homes (site r 0.973); from zoning alone: 0.898×. By 2025, 12% of the projected increment was built |
| **Redevelopment-transition model**, temporal holdout (trained 2015→2020, tested 2020→2025) | 569 lots redeveloped of 42,170 (base rate 1.4%) | LightGBM AUC **0.847**, precision in the top 1% **26%** (19× base); GNN 0.809; best baseline 0.749. New use: top-3 92% (GNN), top-1 60% (average of both) |
| GNN suitability as a redevelopment predictor (2015 → 2025) | 773 lots rebuilt with a new use | Loses to simple baselines (AUC 0.707 vs 0.78). It describes fit, not change, which is why the transition model was built |
| **SoHo/NoHo rezoning** (2021) | FEIS Appendix A2, 26 projected sites (parse matches the appendix total) | Same sites and floor area: 1.039× the FEIS homes (site r 0.976). Nothing built on them by 2025 |
| PlanArena's own rezoning screen, three rezonings | City projections for East Harlem, Inwood, SoHo/NoHo | Inwood 0.938×, SoHo/NoHo 1.341×, East Harlem 1.706× (the screen also counts 'potential' sites). Built by 2025: 9%, 14% and about 0% of the projected increments |
| Optimizer | Exhaustive search, 16 small areas | Exact optimum found in 69% with first-order search alone; **100% with the exact polish step**, now on by default |

**What this means**

* **The impact engine is credible for plan comparison.**
  * Emissions totals are within 7% out of sample.
  * Jobs land in the right places (tract r 0.82).
  * Homes from floor area are within 9%.
  * On the East Harlem sites, PlanArena reproduces the city's own environmental impact projection within 3%.
* **Where change happens is now predicted with a model built for it.**
  * The transition model learns from observed redevelopment.
  * On a later period it never saw, its top 1% of lots were redeveloped 26% of the time, against a 1.4% base rate.
  * It runs in the app as "Show where redevelopment is likely (next 5 years)", and in the parcel inspector.
  * Within the training period, accuracy is far higher (average precision about 0.54 against 0.14 later). The redevelopment pattern shifted after 2020; that is a finding, not noise.
* **The GNN suitability model describes fit, not change.** It is kept for the "best fit" overlay. For redevelopment, simple baselines beat it.
* **Projections and build-out differ in timing.**
  * Of the projected increments, only 9% (East Harlem, 2017) and 14% (Inwood, 2018) were built by 2025. SoHo/NoHo (adopted 2021) had nothing yet.
  * A planning tool should show both "what zoning allows" and "what is likely to happen". PlanArena now does both.

**Spatial cross-validation of the GNN** (whole 600 m tiles held out; the task is reconstructing current use):

| Task | GNN | LightGBM | Simple baseline |
|---|---|---|---|
| Land-use fit, accuracy | 0.671 ± 0.016 | **0.689 ± 0.013** | 0.593 (zoning majority) |
| Land-use fit, log loss | 0.918 | **0.912** | 1.192 |
| Value, R² | 0.621 ± 0.075 | **0.702 ± 0.048** | 0.540 (median by use and district) |

**Emissions, in sample** (`results/validation_emissions_ll84.json`, 9,188 buildings): log–log r 0.808; total 1.07× metered.

## The stakeholder vote

* **Ballots.**
  * Each stakeholder ranks every candidate plan by its own utility, and ties are allowed.
  * Candidates are each stakeholder's ideal, pairwise compromises, balanced, consensus, the parcel ballot, your current plan and no change.
  * The council's seats are adjustable.
* **Rules.** Plurality, Borda, instant runoff, Copeland, Schulze, Kemeny–Young (exact, by integer programming), approval, score and majority judgment.
  * The decision uses **Schulze**: it is Condorcet-consistent, monotone and independent of clones. Compromise plans are often near-copies of each other, so clone independence matters.
  * The rules are checked against the textbook Tennessee-capital example in the tests.
* **Analysis.**
  * Pairwise majority matrix, Condorcet winner and loser, Smith set, and agreement across rules.
  * Robustness: Monte Carlo over coefficient ranges (triangular, comonotone) and seat weights (Dirichlet).
  * A strategic-voting check: can one voter change the result by misreporting?
  * A comparison with the bargaining solutions.
* **Residents' referendum.**
  * Today's residents vote by tax block, weighted by population. They judge the change in their own block's access to parks, shops, community facilities, mix and green cover, plus homes in the district.
  * Differences under 0.01 points count as indifference.
  * Future residents do not vote.
* **Parcel-by-parcel ballot.**
  * On every eligible parcel, the council ranks the allowed uses by marginal utility (weighted Borda).
  * A change passes only with an absolute majority of seats.
  * The strongest passed changes, within the change budget, form one more candidate plan.
* **Double majority.** A decision is "contested" unless both the council seats and the affected residents prefer it to no change.

**Results in all 12 districts** (`results/vote_summary.json`, one seat each, plans change at most 5% of parcels):

| Finding | Districts |
|---|---|
| A Condorcet winner exists (otherwise majority preferences cycle) | 7 of 12 |
| All nine rules agree | 0 of 12 |
| The council winner carries a double majority against no change | 12 of 12 |
| Residents' own winner is the council's winner | 1 of 12 |
| The council winner is also the Nash bargaining solution | 1 of 12 |
| One insincere ballot could change the Schulze result | 8 of 12 |
| Median robustness of the winner (coefficients and seats varied) | 70% |

Every council winner beats no change among residents, but residents almost always prefer a different plan. Majority voting and bargaining rarely agree: bargaining protects the worst-off stakeholder, while majority rule does not. With fragmented control of parcels, the price of anarchy is about 1.5.

## Honesty rules built in
* Each coefficient carries a status: verified, derived, calibrated, corroborated, assumption or provisional. An indicator is flagged ≈ while any coefficient it depends on is still provisional; none is at the moment.
* Ranges are a sensitivity envelope from low and high coefficient variants. They are not calibrated prediction intervals.
* Zoning is a simplified rules-as-code version of the NYC Zoning Resolution. The Studio treats it as advisory; the optimizer treats it as a hard constraint.
* The optimizer protects landmarks and historic districts, parks, public facilities, infrastructure and existing homes. It never demolishes unless that is explicitly allowed.
* No language model is used. Ballots, votes and decisions are computed and written to the audit log.
* No human-participant data is used.

## Known limitations and next steps
1. **Stakeholder priorities are modelling assumptions.** The vote is only as representative as the weights in `planarena/agents/stakeholders.py`. They can be edited, and seats can be changed in the app.
2. **LL84 covers only buildings of 25,000 sq ft or more.** Small buildings take the same use-type EUIs.
3. **Roof share** is estimated as floor area / floors. NYC building footprints would measure it directly.
4. **Still open.**
   * Inwood's site-level FEIS tables are not machine-readable here, so its replay is area level only.
   * Mandatory Inclusionary Housing bonus FAR is not modelled.
   * Usability items F9, F12 and F14 in [docs/USABILITY_REVIEW.md](docs/USABILITY_REVIEW.md).
5. **GNN.** The transition GNN trails LightGBM (AUC 0.81 vs 0.85). Try longer training histories (more PLUTO releases), HGT, and embedding the GNN as a feature for LightGBM.
6. **Imagery** is not used. NAIP and Sentinel-2 are open and could feed a vision branch; Google Street View may not be used for training.
7. **More cities.** The twin builder is city-agnostic once parcels, zoning and land-use codes are mapped.
