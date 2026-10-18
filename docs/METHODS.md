# PlanArena methods

This file defines the calculations. It deliberately contains no results: every number is generated into [VALIDATION.md](VALIDATION.md) from `results/**/*.json`.

## 1. Delta equations (how a change is scored)

**Notation:**
- A parcel *i* has an observed baseline record: floor area F⁰ᵢ, floor-area components cᵢₖ⁰ (residential, office, retail, other commercial, factory, storage, public facility, transport/utility), homes h⁰ᵢ, assessed value v⁰ᵢ, use u⁰ᵢ.
- A plan sets a new use u¹ᵢ and, optionally, a floor area ratio. The new floor area is F¹ᵢ = lot × FAR if a FAR is set. Otherwise it is the existing building when the new use is a built use, or zoning FAR × build-out utilization on an empty lot.
- s(u, F) is the model's split of floor area F into components under use u (from city-wide shares derived from MapPLUTO).
- q is the floor area per home: the parcel's own observed value when plausible (250–5,000 sq ft), otherwise the city median.

Unchanged parcels keep their observed values exactly. For changed parcels, three forms are implemented (`ImpactEngine.delta_form`):

| Form | Components | Homes |
|---|---|---|
| Replacement | cᵢₖ¹ = sₖ(u¹ᵢ, F¹ᵢ) | h¹ᵢ = s_res(u¹ᵢ, F¹ᵢ) / q |
| Difference | cᵢₖ¹ = max(0, cᵢₖ⁰ + sₖ(u¹ᵢ, F¹ᵢ) − sₖ(u⁰ᵢ, F⁰ᵢ)) | h¹ᵢ = max(0, h⁰ᵢ + [s_res(u¹ᵢ, F¹ᵢ) − s_res(u⁰ᵢ, F⁰ᵢ)] / q) |
| **Hybrid (default)** | If u¹ = u⁰ and the record is consistent: cᵢₖ¹ = cᵢₖ⁰ · F¹ᵢ/F⁰ᵢ. Otherwise, replacement | Same rule |

**Consistent record:** F⁰ ≥ 1,000 sq ft and, if the lot has homes, 250 ≤ F⁰/h⁰ ≤ 5,000 sq ft per home.

**The other quantities, in every form:**
- **Jobs** = Σₖ cₖ / (floor area per worker)ₖ.
  - The relative rates are fitted to LEHD LODES 2023 jobs by census block, with non-negative least squares on the floor-area components. The total is scaled once to the BLS QCEW employment count.
  - These rates replaced the EIA CBECS rates after a forward test: rates fitted on 2015 lots and LODES 2015, tested on 2025 lots against LODES 2023.
- **Emissions** = F × EUI(u) × EF(u).
  - EUI(u) is the site energy of the fuels Local Law 97 counts, divided by MapPLUTO floor area, summed over the LL84 buildings of PlanArena land use u (a ratio estimator).
  - EF(u) is that use's emission factor from its fuel mix.
  - Grouping by PlanArena use, rather than by LL84 property type, was chosen on held-out buildings.
  - Both the baseline and the plan use this model, so the delta is a pure model difference.
- **Runoff** = lot × [roof share × C_roof + (1 − roof share) × C_ground(u)]. Also a pure model difference.
- **Assessed value** uses the difference form in all cases: v¹ᵢ = max(0, v⁰ᵢ + [V(u¹ᵢ, F¹ᵢ) − V(u⁰ᵢ, F⁰ᵢ)]). V is the rate-table or GNN value model.
- **Access indicators** (parks, services, facilities, mix, green cover) are recomputed from the resulting state.

**Why the forms differ (reviewer comment R2):**
- With observed y and model ŷ, a replacement delta is ŷ₁ − y = (ŷ₁ − ŷ₀) + (ŷ₀ − y), so it carries the baseline residual.
- The difference form removes that residual but cannot represent a complete conversion. Subtracting the model's old-use composition from a parcel whose observed composition differs leaves "ghost" components, which are floored at zero.
- The hybrid keeps the parcel's observed composition when only density changes. When the use changes, it removes the observed old use and adds the modelled new use.

**How the default was chosen** (`python -I -m planarena.validate delta_forms changes`):
1. **Influence of baseline residuals on recommendations.** Synthetic log-normal error is added to the observed components and homes, and the optimizer's recommendations are compared with and without it (Jaccard overlap, 12 districts).
2. **Prediction of observed change.** For lots that changed between MapPLUTO 15v1 (2015) and 25v3.1 (2025), each form predicts the change in homes, assessed value and emissions, given the 2015 state plus the observed new use and floor area. Baselines are no change and the cross-fitted mean change of the same transition type and size class.
   - Density-only changes count only with evidence of construction (a building completed since 2015).
   - 2015 records with inconsistent floor area are excluded.

The form with the smaller bias and error on observed change is the default. Its sensitivity to baseline residuals is reported alongside, not hidden.

## 2. Validation classes

1. **Existing conditions:** does the model reproduce what is there? (LL84 emissions, LODES jobs, homes)
2. **Consistency with planning calculations:** given a city environmental review's sites, floor area and use, does PlanArena reproduce its numbers? (FEIS replays)
3. **Prediction of change:** given a real change, does PlanArena predict its effect? (Section 1, test 2)

**Effects without validation** are listed in `results/validation/change_prediction.json` (`"unvalidated"`) and in VALIDATION.md.

## 3. Redevelopment-transition model

**Unit and labels.**
- **Unit:** a lot in the start snapshot (year t₀).
- **Matching:** each lot is matched to the lot of the end snapshot (t₁) that contains its representative point. This follows splits and mergers.
- **"Redeveloped"** if the matched t₁ lot has a building completed in the period (year built ≥ t₀), or its floor area grew by more than 25% and 2,000 sq ft over the t₀ lots inside it.
- **Destination** is the matched lot's land use.
- **Label audit** (`planarena/models/rolling.py`): labels are compared with DOB certificates of occupancy for new buildings and alteration type 1 jobs, matched by BBL within the same window.

**Features.** Every feature is computed from the t₀ snapshot only; nothing from t₁ or later enters.

| Feature group | Source (t₀ MapPLUTO unless noted) | As of |
|---|---|---|
| Lot and building size, floors, year built, built FAR, permitted FARs, overlays, historic district and landmark flags, zoning family | parcel record | t₀ |
| Own land use (one-hot) | parcel record | t₀ |
| Underbuilt share of zoning capacity, maximum FAR, land-value share, assessed value per sq ft, soft-site flag, homes | parcel record, zoning rules | t₀ |
| Land-use mix of adjacent and nearby lots | parcel graph built from t₀ geometry | t₀ |
| Share of adjacent and nearby lots with a building completed in the five years before t₀ | t₀ year-built field | t₀ |

**Protocols.**
- **Temporal holdout.** Train on pairs (t₀ → t₀ + h) whose outcome is known by the decision year t (t₀ + h ≤ t). Test on (t → t + h).
- **Rolling origin.** Horizons of 1, 3 and 5 years over the annual snapshots, 2015–2025.
- **Calibration.** Isotonic regression fitted on the most recent training pair, predicted by a model trained on the pairs before it. Reported as ECE and reliability bins, before and after.
- **Uncertainty.** 600 m tile block bootstrap for AUC and average precision; three seeds.
- **Spatial-within-period cross-validation** of the test pair is reported only to show the optimism of non-temporal tests.

**Label definitions.**
- **The default label** includes floor-area growth recorded in MapPLUTO, some of which is record correction rather than construction.
- **The verified label** keeps new buildings (by year built). It keeps floor-area growth only when a DOB new-building or alteration-type-1 certificate of occupancy was issued for the lot, or its predecessor, in the window.
- Results are reported for both labels.

**Precedent.** The conversion-precedent table is date-aware: `precedent(as_of=t)` uses only snapshot pairs that ended by t.

**Across cities** (`planarena/models/crosscity.py`). Milwaukee snapshots 2015–2026 come from the annual Master Property files on today's parcel polygons (`planarena/cities/mke_history.py`; 2016 is left out because 27,186 parcels lack floor area in that file). The label is a new building within three years, in both cities, because Milwaukee's floor area is not recorded consistently over time. Features are portable: within-city percentile ranks of size, age, value and density, the land-value share, FAR relative to the 90th percentile of nearby lots, and neighbour mix and recent construction. Zoning and permitted FAR are left out, because the cities regulate density differently. Each test city's latest pair is scored by models trained on the same city, on the other city only, and on both, with training pairs ending by the test pair's start year.

## 4. Simulated stakeholder scenario

**Voters.**
- **Stakeholders** have assumed indicator weights (`planarena/agents/stakeholders.py`). Utility = Σₖ wₖ · scoreₖ, the same signed indicator scores as the scoreboard, so the status quo is worth 0.
- **Simulated residents** are today's population by tax block. They are scored on their own block's access changes plus district homes.

**Ballots and rules.**
- Ballots are full rankings by utility, with ties allowed.
- Rules: plurality, Borda, instant runoff, Copeland, Schulze (decides), Kemeny–Young (exact ILP), approval (utility > 0), score (0–10 per voter) and majority judgment.

**Sensitivity** (`voting.sensitivity`):
- utility weights drawn from a Dirichlet centred on the assumed weights;
- random feasible plans added to the ballot (a candidate generator not built from the utilities);
- the residents' indifference threshold swept;
- seat allocations varied.

**What it is not.** These are simulated preference scenarios. They say nothing about public support or political feasibility.

## 5. Optimizer benchmark

**Objective.** J = overall plan score − conversion penalty × number of changes, with the GNN term off.

**Methods compared** in every district at a fixed budget:
- first-order iterated best response;
- the same with exact re-scoring of the top moves (the default);
- greedy with exact evaluation over a shortlist of first-order moves;
- simulated annealing over the shortlist (several seeds);
- best of random feasible plans;
- the exact optimum of the linear first-order surrogate (top moves of distinct parcels).

**Small cases.** Exhaustive search on single-block areas with up to two changes.

**What none of this shows.** A global optimum at district or city scale. Results are "best plan found".

## 6. Cost of fragmented control (heuristic, not a formal price of anarchy)

**Definitions.**
- **Players:** the five stakeholders.
- **Control:** eligible parcels in the study area are split at random (seeded) into five equal-probability sets; each player controls one.
- **Actions:** feasible land-use assignments to the player's own parcels, under the same protections as the optimizer, with a change budget of 5% of its parcels.
- **Payoffs:** the player's utility over the study area (section 4).
- **Dynamics:** three rounds of sequential first-order best responses. The resulting profile is not verified to be a Nash equilibrium.
- **Welfare:** the sum of utilities.
- **Benchmark:** the optimizer's plan with averaged weights over all eligible parcels. It is itself a heuristic, not the welfare optimum.
- **Reported value:** welfare(benchmark) / welfare(fragmented).

A formal price of anarchy would need the worst equilibrium and the true optimum. This ratio is neither, so it is reported only as a heuristic illustration and is not used as evidence.

## 7. Pattern-consistency models and their ablation

**Task.** Reconstruct each parcel's current land use (and assessed value) from its context. This measures how well a use fits the existing pattern, not whether it is desirable.

**Spatial cross-validation.** Five folds of 600 m tiles. Two settings for the GNN:
- **Transductive** (as first reported): held-out parcels stay in the graph, with their use and value masked during training and testing. Their features and their edges are seen in training.
- **Inductive:** during training, every edge touching a held-out parcel is removed, so held-out parcels play no part in training. At test time the full graph is used, with held-out parcels masked.

**Ablation** (`planarena/models/ablation.py`), on the same folds:
- GNN, transductive and inductive;
- LightGBM on the context features plus the land-use mix of neighbours (held-out parcels hidden);
- LightGBM with the GNN embedding added. Each training parcel's embedding is computed while that parcel is hidden (ten random chunks), so its own use never enters its features.

The GNN is kept only where the ablation shows that it adds accuracy; the redevelopment layer uses LightGBM.

## 8. Reproduction

`make reproduce` downloads every input, rebuilds the twins, recalibrates, retrains, reruns every validation and regenerates the docs. `planarena/tools/fetch_open_data.py` records each input's URL, query and SHA-256 in `data/raw/*/SOURCE.json` and `results/data_manifest.json`. `make compare` lists result files that differ from the committed ones.

## 9. The ten cities

**Principle.** Each city's baseline is the land use its government or regional planning agency publishes for every parcel. The adopted plan (future land use) and zoning are separate layers; nothing is estimated. City adapters (`planarena/cities/adapters/`) map each source into the `parcels.parquet` schema; `planarena/cities/build.py` lists the ten cities.

**New York City** (all boroughs) uses the citywide MapPLUTO release with the same schema and zoning rules as the Manhattan demo (`adapters/nyc.py`). Its energy and emission coefficients are chosen on held-out buildings. The two candidates are national (RECS/CBECS, eGRID New York State) and the Manhattan LL84 calibration. Both are scored against LL84 2023 emissions of buildings outside Manhattan, and the one with the smaller median error is kept. Jobs rates are fitted to the city's LODES blocks either way.

**Milwaukee** uses the Master Property File and the city's parcel polygons (`adapters/milwaukee.py`):
- land use from the MPROP land-use group (parking codes 7521, 7523 and 7525 become parking);
- floor area, units (residential and mixed groups only), stories, year built and assessed value (including exempt value);
- condominium units summed to their parcel;
- locally designated historic properties protected;
- aldermanic districts as districts.

Milwaukee regulates bulk with height, setback and density rules rather than one FAR. Its zoning screen is therefore simplified: the district family sets the allowed uses, and the context FAR (the 90th percentile of built FAR in the census block group, or the lot's own if higher) stands in for capacity.

**Philadelphia** uses the Office of Property Assessment records and the Water Department parcels (`adapters/philadelphia.py`). Each assessment point is placed in the parcel that contains it, and the records on one parcel are summed.
- **Land use:** the OPA category, with institutions picked out from the building description.
- **Parks:** land zoned parks and open space (SPPOA, SPPOP) is open space.
- **Homes:** OPA has no unit count. Single-family records count as one home each; the rest of each census block's housing units go to its multi-family and mixed parcels by floor area (estimated, flagged).

**Data checks in every adapter:**
- recorded lot area is replaced by the polygon's area when the two differ by more than 3×;
- floor area above FAR 50 is treated as unrecorded;
- LL84 records with a site EUI above 1,000 kBtu/sq ft are dropped as reporting errors (`calibrate.plausible_ll84`), in the calibration and in every validation.

**Coefficients in every city other than Manhattan:**
- residential site EUI: RECS 2020 by state;
- non-residential site EUI: CBECS 2018 by census division and use (national where a cell has fewer than 30 buildings);
- emission factors: eGRID2023 state electricity rates and the EPA Emission Factors Hub (AR5 GWPs), weighted by each use's fuel mix;
- persons per household: Census 2020 population per housing unit (an understatement, because vacant units are included);
- jobs: floor area per worker by type, fitted by non-negative least squares to the city's LODES blocks.

**Map data for large cities.** Above 100,000 parcels, the web app loads compact parcel points (use, district, position, size) instead of one GeoJSON file. Parcel polygons come as Mapbox vector tiles at zooms 13–15, cut from the twin's own geometry and cached on disk. Selection tools work on the points, so they behave the same in both modes.

## 10. Integration value (retrospective, no human participants)

`planarena/models/replay.py` asks whether combining the impact engine with redevelopment likelihood gives projections closer to what was built than capacity alone. For each Manhattan rezoning:
- **Sites:** the development-site screen (`rwcds.py`) under the adopted maximum FAR, on the adoption-year snapshot.
- **Homes added per site:** the engine, at the build-out utilisation.
- **Capacity projection:** the sum over sites; also pro-rated linearly to 2025 from the review's build year.
- **Likelihood-weighted projection:** the sum of homes added × the site's probability of redevelopment by 2025.
  - The probability comes from the redevelopment model trained only on snapshot pairs whose outcome was known by the adoption year.
  - It is scored with the adopted zoning in the features.
  - It uses the longest available horizon, extended to 2025 with a constant hazard.
  - Its range is the 2.5th–97.5th percentile of 20,000 draws, with each site redeveloping independently.
- **Observed:** homes recorded in 2025 on each site's land, minus those before; and the redevelopment label.

**Realism-layer ablation** (`planarena/models/ablate_recs.py`). On the 2020 snapshot (precedent table as of 2020), the optimizer plans every district (balanced weights, 2% budget) three ways:
- without the precedent filter;
- with it;
- with it and candidates restricted to the likeliest fifth for redevelopment (model trained on 2015→2020).

Recommended parcels are compared with 2025: redeveloped or not, and whether the recommended use appeared.
