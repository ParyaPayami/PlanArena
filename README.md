# PlanArena

**PlanArena** is an open planning-support tool built on a parcel-level digital twin. A planner changes the use or density of one parcel or many, and PlanArena estimates the social, economic and environmental effects straight away, with sensitivity ranges.

It also does four further things:
- shows where redevelopment is likely to happen;
- tests a rezoning with the development-site method city environmental reviews use;
- recommends plans (the best plan found by its search, not a proven optimum);
- puts candidate plans to a simulated stakeholder scenario: assumed priorities voting under nine voting rules.

* **Desktop Studio** (`/`): the planner's workspace.
  * Map with select, box, lasso, block and address/BBL search.
  * Use and density (FAR) edits, a live scoreboard with ranges, and capacity.
  * Recommended plans and a Pareto explorer.
  * Simulated stakeholder scenario.
  * Saved studies with status, checklist, hearing date and history.
  * Desk tools: soft sites, notice radius, rezoning test, staff report.
  * Plan import with review, exports with provenance.
* **Phone game** (`/play`): neighbourhood levels with missions, tap/drag painting and stars. At the end, a simulated council votes between your plan, the recommended plan and no change.

<!-- BEGIN GENERATED: header -->
Demo city: Manhattan, 42,075 parcels from NYC DCP MapPLUTO 25v3.1, downloaded from DCP by `planarena.twin.fetch`. The archive's and the extract's SHA-256 are recorded in `twin_meta.json` and in every export. 11 indicators across three pillars.
<!-- END GENERATED: header -->

## Quick start

Double-click **Start PlanArena.command** in this folder. Your browser opens the Studio at http://localhost:8787; the phone game is at /play. **Start PlanArena (phone).command** also serves the game to a phone on the same Wi-Fi. See [TESTING.md](TESTING.md) for what to try.

## Run it

```bash
cd PlanArena   # first time: python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -I -m planarena.api          # then open http://localhost:8787  (phone game: /play)
```

To rebuild everything from public data (downloads about 17 GB; every input's URL and SHA-256 is recorded in `results/data_manifest.json`):

```bash
make reproduce   # or `make results` to rerun models and validation on data already downloaded
```

The individual steps:

```bash
.venv/bin/python -I -m planarena.twin.fetch  # official MapPLUTO release -> Manhattan extract + SOURCE.json
.venv/bin/python -I -m planarena.tools.fetch_open_data  # LODES, LL84, DOB certificates, FEIS appendices + hashes
.venv/bin/python -I -m planarena.twin.build     # digital twin: parcels, graph, raster, web layers
.venv/bin/python -I -m planarena.calibrate      # coefficients from LL84/LL97/LODES/QCEW
.venv/bin/python -I -m planarena.models.history  # annual MapPLUTO twins 2015-2024
.venv/bin/python -I -m planarena.models.train   # baselines + GNN spatial CV + final model
.venv/bin/python -I -m planarena.models.ablation all  # GNN vs LightGBM ablation, inductive CV
.venv/bin/python -I -m planarena.models.transition all  # redevelopment-transition model + conversion precedents
.venv/bin/python -I -m planarena.models.rolling  # rolling-origin evaluation, calibration, label audit
.venv/bin/python -I -m planarena.agents.voting   # simulated stakeholder scenario in every district
.venv/bin/python -I -m planarena.validate all  # validation against open data -> results/validation
.venv/bin/python -I -m planarena.report      # writes docs/VALIDATION.md and the generated blocks in this README
cd web && npm install && npx vite build      # web app -> web/dist (served by the API)
.venv/bin/python -I -m pytest -q             # tests (implementation correctness; includes a docs-are-current check)
```

## What it does and where

| Capability | Where |
|---|---|
| Digital twin | `planarena/twin`: parcels, 3D massing, parcel graph (adjacency, kNN, same zoning), 50 m access raster, zoning rules-as-code |
| Effects of a change | `planarena/indicators/engine.py`. Unchanged parcels keep their observed values; the delta equations are in [docs/METHODS.md](docs/METHODS.md) |
| Density edits | Each parcel can take a proposed FAR as well as a use. Capacity, soft sites and added zoning capacity are reported |
| Redevelopment likelihood | `planarena/models/transition.py`: five-year likelihood and likely new use for every lot, from a model tested on a later period |
| Rezoning test | `planarena/indicators/rwcds.py`: the development-site screen city environmental reviews use, applied to the FAR values in a plan |
| Recommended plans | `planarena/optimize/suggest.py` (iterated best response with exact re-scoring of the top moves) and `pareto.py` (NSGA-III). The best plan found, not a proven optimum |
| Pattern consistency | `planarena/models`: LightGBM with a GraphSAGE embedding (the best model in the ablation below), cross-fitted so no parcel sees its own use. It describes existing patterns, not what is desirable |
| Simulated stakeholder scenario | `planarena/agents/voting.py`: ballots computed from assumed utilities, nine voting rules, compared with bargaining solutions. Not elicited preferences |
| Realism | Conversions of existing buildings never observed at that size are flagged, and the optimizer skips them |
| Plan upload, studies, outputs | `POST /api/import` with review; SQLite studies with a hash-chained audit log; staff report, CSV/GeoJSON, provenance JSON |
| Requirements traceability | [docs/REQUIREMENTS_TRACEABILITY.md](docs/REQUIREMENTS_TRACEABILITY.md), from a de-identified municipal requirements catalogue |
| Review response | [docs/REVIEW_RESPONSE.md](docs/REVIEW_RESPONSE.md): each reviewer comment mapped to the change, its test and the evidence file |

## Any US city

PlanArena opens with the Manhattan demo. The city name in the Studio's header opens a picker that searches every US place in the Census gazetteer (incorporated places, census-designated places and New England towns) and builds a twin on request.

| Tier | Where | Lots | Land use, floor area, homes | Value and zoning |
|---|---|---|---|---|
| **B** (parcel records) | Manhattan demo and all of New York City (NYC MapPLUTO); Philadelphia (OPA); Milwaukee (MPROP); every Massachusetts city and town (MassGIS L3); every Florida place (DOR parcel maps and tax roll) | assessors' parcels | from the records | value from the records; zoning simplified (Milwaukee district families), not interpreted (Massachusetts) or absent (Florida) |
| **A** (national open data) | any other US place | pseudo-lots: each building's cell within its 2020 census block | estimated from Overture buildings, places and land use (a model trained on the Tier B cities); homes are Census 2020 housing units by block | none (hidden in the UI) |

Every Tier A and Tier B city gets its own coefficients: energy use from EIA RECS 2020 (by state) and CBECS 2018 (by census division); emission factors from EPA eGRID2023 (by state) and the EPA GHG Emission Factors Hub; and jobs rates fitted to that city's LODES blocks. Each twin records, column by column, what is observed, estimated or missing (`twin_meta.json`; Methods dialog).

```bash
.venv/bin/python -I -m planarena.cities.build "Austin, TX"         # any place, by name or Census GEOID (best tier available)
.venv/bin/python -I -m planarena.cities.adapters.milwaukee         # Tier B: Milwaukee
.venv/bin/python -I -m planarena.cities.adapters.massgis Worcester # Tier B: any Massachusetts town
.venv/bin/python -I -m planarena.cities.compare milwaukee          # Tier A scored against Tier B
```

**How good is Tier A?** The Tier A pipeline is run inside the Tier B cities and scored against their parcel records:

<!-- BEGIN GENERATED: tiers -->
Tier A runs for any US place from national open data (Census 2020 blocks, LODES, Overture Maps, EIA and EPA). To measure what that costs, the Tier A pipeline is run inside cities that also have parcel records (Tier B) and scored against them (`planarena/cities/compare.py`).

| City | Test | Tier A | Tier B |
|---|---|---|---|
| Manhattan | Lots | 45,808 pseudo-lots | 42,075 parcels |
| Manhattan | Land use of built lots (accuracy; macro F1) | 63%; 0.274 (majority class 50%) | records |
| Manhattan | Floor area by census block (total; log r; median error) | 1.22×; 0.797; 18% | records |
| Manhattan | Floor area total after the correction learned from the other cities | 0.83× | records |
| Manhattan | Homes by census block, Census 2020 vs city records (total; r) | 0.92×; 0.765 | records |
| Manhattan | Jobs by census block vs LODES (r; in-sample) | 0.517 | 0.647 |
| Manhattan | Building emissions vs LL84 2023, 5,634 buildings (total; median error) | 0.72×; 42% | 0.86×; 33% |
| Cambridge | Lots | 13,045 pseudo-lots | 12,933 parcels |
| Cambridge | Land use of built lots (accuracy; macro F1) | 87%; 0.306 (majority class 82%) | records |
| Cambridge | Floor area by census block (total; log r; median error) | 1.32×; 0.874; 36% | records |
| Cambridge | Floor area total after the correction learned from the other cities | 0.96× | records |
| Cambridge | Homes by census block, Census 2020 vs city records (total; r) | 1.10×; 0.772 | records |
| Cambridge | Jobs by census block vs LODES (r; in-sample) | 0.769 | 0.476 |
| Gainesville | Lots | 37,275 pseudo-lots | 37,345 parcels |
| Gainesville | Land use of built lots (accuracy; macro F1) | 84%; 0.286 (majority class 78%) | records |
| Gainesville | Floor area by census block (total; log r; median error) | 1.38×; 0.719; 62% | records |
| Gainesville | Floor area total after the correction learned from the other cities | 1.05× | records |
| Gainesville | Homes by census block, Census 2020 vs city records (total; r) | 1.04×; 0.601 | records |
| Gainesville | Jobs by census block vs LODES (r; in-sample) | 0.162 | 0.217 |
| Milwaukee | Lots | 165,024 pseudo-lots | 148,042 parcels |
| Milwaukee | Land use of built lots (accuracy; macro F1) | 91%; 0.286 (majority class 88%) | records |
| Milwaukee | Floor area by census block (total; log r; median error) | 1.55×; 0.684; 25% | records |
| Milwaukee | Floor area total after the correction learned from the other cities | 1.17× | records |
| Milwaukee | Homes by census block, Census 2020 vs city records (total; r) | 0.94×; 0.872 | records |
| Milwaukee | Jobs by census block vs LODES (r; in-sample) | 0.628 | 0.567 |
| New York | Lots | 832,352 pseudo-lots | 856,634 parcels |
| New York | Land use of built lots (accuracy; macro F1) | 87%; 0.315 (majority class 84%) | records |
| New York | Floor area by census block (total; log r; median error) | 1.17×; 0.866; 25% | records |
| New York | Floor area total after the correction learned from the other cities | 0.80× | records |
| New York | Homes by census block, Census 2020 vs city records (total; r) | 0.94×; 0.663 | records |
| New York | Jobs by census block vs LODES (r; in-sample) | 0.529 | 0.626 |
| Philadelphia | Lots | 412,620 pseudo-lots | 547,410 parcels |
| Philadelphia | Land use of built lots (accuracy; macro F1) | 90%; 0.274 (majority class 89%) | records |
| Philadelphia | Floor area by census block (total; log r; median error) | 1.69×; 0.824; 62% | records |
| Philadelphia | Floor area total after the correction learned from the other cities | 1.28× | records |
| Philadelphia | Homes by census block, Census 2020 vs city records (total; r) | 1.00×; 0.960 | records |
| Philadelphia | Jobs by census block vs LODES (r; in-sample) | 0.496 | 0.544 |
| Cambridge | Land use from a model trained on Gainesville, Manhattan, Milwaukee, Newyork, Philadelphia (accuracy; macro F1) | 89%; 0.363 (rules 87%; 0.311) | records |
| Gainesville | Land use from a model trained on Cambridge, Manhattan, Milwaukee, Newyork, Philadelphia (accuracy; macro F1) | 85%; 0.321 (rules 84%; 0.288) | records |
| Manhattan | Land use from a model trained on Cambridge, Gainesville, Milwaukee, Philadelphia (accuracy; macro F1) | 60%; 0.272 (rules 63%; 0.274) | records |
| Milwaukee | Land use from a model trained on Cambridge, Gainesville, Manhattan, Newyork, Philadelphia (accuracy; macro F1) | 91%; 0.354 (rules 91%; 0.287) | records |
| Newyork | Land use from a model trained on Cambridge, Gainesville, Milwaukee, Philadelphia (accuracy; macro F1) | 87%; 0.327 (rules 87%; 0.317) | records |
| Philadelphia | Land use from a model trained on Cambridge, Gainesville, Manhattan, Milwaukee, Newyork (accuracy; macro F1) | 88%; 0.303 (rules 90%; 0.275) | records |
| | | | |
| New York City, 11,580 benchmarked buildings outside Manhattan | Emissions with national coefficients (total; median error) | 0.54×; 40% | |
| New York City, 11,580 benchmarked buildings outside Manhattan | Emissions with manhattan ll84 coefficients (total; median error) | 0.81×; 32% (chosen) | |

Tier A has no assessed values or zoning; those indicators are hidden in Tier A cities.
A land-use model trained on the other Tier B cities and tested on each held-out one did not beat the rules in every held-out city, so Tier A uses the rules (5 model variants tried; `results/validation/landuse_model.json`).
<!-- END GENERATED: tiers -->

## Coefficients: every value has a source and a range

<!-- BEGIN GENERATED: coefficients -->
| Coefficient | Source | Status |
|---|---|---|
| Building energy (site EUI by use) | NYC LL84 benchmarking, calendar 2024, Manhattan; floor-area-weighted mean, Q25–Q75 range | derived |
| Emission factor | NYC LL97 §28-320.3.1.1 (2024–2029) weighted by LL84 Manhattan fuel shares | derived |
| Floorspace per worker | EIA CBECS 2018 Table B2, scaled so the baseline equals BLS QCEW New York County employment (2,480,984) | calibrated |
| Persons per household | Census QuickFacts, New York County: 2.00 | corroborated (page is bot-protected; confirm) |
| Runoff C | NYC DEP surface coefficients (roof 1.00) weighted by each parcel's roof share; ground C by use | derived |
| Build-out utilization | 0.8 (0.6–1.0) | assumption |
<!-- END GENERATED: coefficients -->

The Studio's Methods dialog (ⓘ) shows the full register, the provenance and the audit-chain check.

## Validation

All results are in [docs/VALIDATION.md](docs/VALIDATION.md), generated from `results/`. The checks fall into three classes:
- **A. Existing conditions:** does the model reproduce what is there?
- **B. Planning calculations:** given a city review's sites and floor area, does PlanArena reproduce its numbers?
- **C. Prediction of change:** given a real change, does PlanArena predict its effect?

Models are in D and the optimizer in E.

<!-- BEGIN GENERATED: key_results -->
| Class | What is tested | Result |
|---|---|---|
| A | Building emissions vs LL84 2023 (fitted on 2024; mostly the same buildings) | total 1.04×; log–log r 0.807; median building error 31% |
| A | Jobs vs LODES 2023 | tract r 0.843, block r 0.727; median tract error 36% |
| A | Homes from observed floor area (295 developed lots) | 1.039× recorded homes; median error 27% |
| B | East Harlem FEIS sites, same floor area and use | 0.859× the FEIS homes (site r 0.940) |
| B | SoHo/NoHo FEIS sites, same floor area and use | 1.003× (site r 0.956) |
| C | Change in homes after real use changes (3,234) | r 0.872 (baseline 0.435); total 1.29× |
| C | Change in emissions after real use changes (193 buildings) | r 0.857 (baseline 0.090); total 1.00× |
| C | Change in jobs by census block | r 0.068: no useful skill |
| D | Redevelopment within 5 years, temporal holdout 2020→2025 | LightGBM AUC 0.847, precision in top 1% 26% (base rate 1.4%); best baseline Land-value share of assessed value AUC 0.754 |
| A | Building-level emissions error vs a single citywide intensity | median 31% vs 29% (totals 1.04× vs 0.96×) |
| A | Jobs rates tested forward (fit 2015, test 2023), block median error | fitted rates 46%; CBECS 45%; flat rate 48% |
| D | Redevelopment, rolling origin (15 tests, 1-, 3- and 5-year horizons) | AUC 0.847–0.952; above the best simple baseline in every test |
| D | Labels vs DOB certificates of occupancy (2020→2025) | 55% of labelled lots have a certificate (a lower bound); labels are noisy |
| C | Homes built by 2025 on the development sites of three rezonings (561) | likelihood-weighted projection 585; capacity 8,423 (pro-rated 5,207); three cases only |
| D | Redevelopment model moved between cities (new buildings, 3 years) | Milwaukee: trained on Manhattan AUC 0.951 vs own city 0.946; Manhattan: trained on Milwaukee 0.774 vs own city 0.903 (best baseline 0.857) |
| E | Optimizer vs exhaustive search (15 single-block areas, up to 2 changes) | optimum found in 93% with exact re-scoring; small cases only |
<!-- END GENERATED: key_results -->

**What this supports, and what it does not**

* **Supported:**
  * Effects on homes and on building emissions of real use changes are predicted far better than by a simple transition-type average.
  * City environmental-review calculations are reproduced closely when PlanArena is given the same sites, floor area and use.
* **Not supported (yet):**
  * Effects of density-only changes.
  * Job changes at block level.
  * Accessibility and runoff effects of a change; they are not validated.
* **Local error:** aggregate totals agree much better than individual buildings or blocks. Parcel-level estimates carry substantial error, shown in VALIDATION.md.
* **Recommendations depend on the baseline:** synthetic error in the observed baseline changes some of them. See VALIDATION.md, section C.

**Pattern-consistency models** (spatial cross-validation):

<!-- BEGIN GENERATED: gnn_cv -->
Spatial-block cross-validation, 5 folds of 600 m tiles. The task is reconstructing each parcel's current use from its context, which describes pattern consistency, not suitability.

Parcels evaluated: 41,942 of 42,075; the 133 parcels with no recorded land use have no label and are excluded.

| Task | GNN | LightGBM | Simple baseline |
|---|---|---|---|
| Current use, accuracy | 0.671 ± 0.016 | 0.689 ± 0.013 | 0.593 ± 0.020 (zoning majority) |
| Current use, macro F1 | 0.380 ± 0.008 | 0.465 ± 0.013 | 0.246 ± 0.023 |
| Current use, log loss | 0.918 ± 0.031 | 0.912 ± 0.051 | 1.192 ± 0.057 |
| Value, R² | 0.621 ± 0.075 | 0.702 ± 0.048 | 0.540 ± 0.069 (median by use and district) |

LightGBM has higher current-use accuracy than the GNN in 5 of 5 folds.

The GNN cross-validation is transductive: held-out parcels stay in the graph with their use and value masked. See docs/METHODS.md.

**Ablation** (same folds; `results/validation/ablation_gnn.json`):

| Model | Accuracy | Macro F1 | Log loss |
|---|---|---|---|
| GNN, transductive (as above) | 0.671 ± 0.016 | 0.380 ± 0.008 | 0.918 ± 0.031 |
| GNN, inductive (no test-parcel edges in training) | 0.670 ± 0.015 | 0.380 ± 0.008 | 0.922 ± 0.031 |
| LightGBM | 0.689 ± 0.013 | 0.465 ± 0.013 | 0.912 ± 0.051 |
| LightGBM + GNN embedding | 0.704 ± 0.016 | 0.475 ± 0.015 | 0.919 ± 0.063 |

Adding the GNN embedding raises LightGBM accuracy in 5 of 5 folds.
<!-- END GENERATED: gnn_cv -->

## The simulated stakeholder scenario

* **Voters are assumed, not real.**
  * Five stakeholder agents rank every candidate plan by assumed priority weights (`planarena/agents/stakeholders.py`).
  * Today's residents are simulated by tax block, from changes in their block's access and in district homes.
* **Interests not represented:** renters as a separate group, commuters, future residents, small landlords, and people with disabilities.
* **Rules:** plurality, Borda, instant runoff, Copeland, Schulze (decides), Kemeny–Young (exact ILP), approval, score and majority judgment. They are checked against the textbook Tennessee-capital example.
* **Candidates:** stakeholder ideals, pairwise compromises, balanced, consensus, a parcel-by-parcel ballot, the current plan and no change.
  * Most candidates are generated from the same utilities that later score them, which shapes the outcome.
  * Sensitivity to alternative utilities, candidate generators, indifference thresholds and seat allocations is reported in VALIDATION.md, section F.

<!-- BEGIN GENERATED: vote -->
Ballots are computed from assumed stakeholder utilities, not elicited preferences. These results describe the simulated scenario, not public support or political feasibility.

| Finding (12 districts, one seat each) | Districts |
|---|---|
| A Condorcet winner exists (otherwise the simulated majority preferences cycle) | 7 of 12 |
| All nine rules agree | 0 of 12 |
| The council winner beats no change in both simulated electorates | 12 of 12 |
| The simulated residents' winner is the council's winner | 1 of 12 |
| The council winner is also the Nash bargaining solution | 0 of 12 |
| One insincere ballot could change the Schulze result | 6 of 12 |
| Median robustness of the winner (coefficients and seats varied, 200 draws) | 75.8% |
<!-- END GENERATED: vote -->

## Honesty rules built in
* Every reported number is generated from result files (`planarena/report.py`); a test fails if the docs drift from the results.
* Each coefficient carries a status: verified, derived, calibrated, corroborated, assumption or provisional.
* Ranges are a sensitivity envelope from low and high coefficient variants. They are not calibrated prediction intervals.
* Zoning is a simplified rules-as-code version of the NYC Zoning Resolution: advisory in the Studio, a hard constraint in the optimizer.
* No language model is used.
* No human-participant data is used.
* The usability work so far is a developer heuristic review ([docs/USABILITY_REVIEW.md](docs/USABILITY_REVIEW.md)), not a study with planners.
* The tests check implementation correctness, not scientific validity.

## Known limitations
1. **Assumed priorities.** Stakeholder priorities and the simulated electorates are assumptions.
2. **Building coverage.** LL84 covers only buildings of 25,000 sq ft or more; smaller buildings take use-type EUIs.
3. **Roof share** is estimated as floor area / floors.
4. **Inwood** is replayed for the whole area only; Mandatory Inclusionary Housing bonus floor area is not modelled.
5. **Tier A is an estimate.** Pseudo-lots are not legal parcels, and land use and floor area are inferred; see the Tier A against Tier B results above.
6. **Large cities** (over 100,000 parcels) are drawn as points when zoomed out and as vector tiles cut on demand when zoomed in (`planarena/cities/tiles.py`); the first view of each area takes a moment while its tiles are made.
