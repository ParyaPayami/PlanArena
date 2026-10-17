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
cd PlanArena   # first time: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m planarena.api          # then open http://localhost:8787  (phone game: /play)
```

To rebuild everything from raw data:

```bash
.venv/bin/python -I -m planarena.twin.fetch  # official MapPLUTO release -> Manhattan extract + SOURCE.json
.venv/bin/python -m planarena.twin.build     # digital twin: parcels, graph, raster, web layers
.venv/bin/python -m planarena.calibrate      # coefficients from LL84/LL97/CBECS/QCEW
.venv/bin/python -m planarena.models.train   # baselines + GNN spatial CV + final model
.venv/bin/python -I -m planarena.models.transition all  # redevelopment-transition model + conversion precedents
.venv/bin/python -m planarena.agents.voting   # simulated stakeholder scenario in every district
.venv/bin/python -I -m planarena.validate all  # validation against open data -> results/validation
.venv/bin/python -I -m planarena.report      # writes docs/VALIDATION.md and the generated blocks in this README
cd web && npm install && npx vite build      # web app -> web/dist (served by the API)
.venv/bin/python -m pytest -q                # tests (implementation correctness; includes a docs-are-current check)
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
| Pattern consistency | `planarena/models`: a GraphSAGE model and LightGBM that reconstruct current use from context. They describe existing patterns, not what is desirable |
| Simulated stakeholder scenario | `planarena/agents/voting.py`: ballots computed from assumed utilities, nine voting rules, compared with bargaining solutions. Not elicited preferences |
| Realism | Conversions of existing buildings never observed at that size are flagged, and the optimizer skips them |
| Plan upload, studies, outputs | `POST /api/import` with review; SQLite studies with a hash-chained audit log; staff report, CSV/GeoJSON, provenance JSON |
| Requirements traceability | [docs/REQUIREMENTS_TRACEABILITY.md](docs/REQUIREMENTS_TRACEABILITY.md), from a de-identified municipal requirements catalogue |

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
| A | Building emissions vs LL84 2023 (fitted on 2024; mostly the same buildings) | total 1.07×; log–log r 0.795; median building error 37% |
| A | Jobs vs LODES 2023 | tract r 0.816, block r 0.704; median tract error 40% |
| A | Homes from observed floor area (295 developed lots) | 1.089× recorded homes; median error 28% |
| B | East Harlem FEIS sites, same floor area and use | 0.969× the FEIS homes (site r 0.973) |
| B | SoHo/NoHo FEIS sites, same floor area and use | 1.039× (site r 0.976) |
| C | Change in homes after real use changes (3,234) | r 0.872 (baseline 0.435); total 1.29× |
| C | Change in emissions after real use changes (193 buildings) | r 0.826 (baseline 0.090); total 1.16× |
| C | Change in jobs by census block | r 0.089: no useful skill |
| D | Redevelopment within 5 years, temporal holdout 2020→2025 | LightGBM AUC 0.847, precision in top 1% 26% (base rate 1.4%); best baseline Land-value share of assessed value AUC 0.754 |
| E | Optimizer vs exhaustive search (16 single-block areas, up to 2 changes) | optimum found in 100% with exact re-scoring; small cases only |
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
| The council winner is also the Nash bargaining solution | 1 of 12 |
| One insincere ballot could change the Schulze result | 6 of 12 |
| Median robustness of the winner (coefficients and seats varied, 200 draws) | 67.8% |
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
5. **Usability items** F9, F12 and F14 are open.
6. **One city.** Every US city is planned (two tiers of open data); see the project plan.
