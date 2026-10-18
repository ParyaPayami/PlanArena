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

**Plan:** Milwaukee's comprehensive plan is a set of area plans published as PDFs on the city's website, which refuses scripted downloads. No GIS layer of them is published. The plan layer is therefore missing.

Milwaukee regulates bulk with height, setback and density rules rather than one FAR. Its zoning screen is therefore simplified: the district family sets the allowed uses, and the context FAR (the 90th percentile of built FAR in the census block group, or the lot's own if higher) stands in for capacity.

**Philadelphia** uses the Office of Property Assessment records and the Water Department parcels (`adapters/philadelphia.py`). Each assessment point is placed in the parcel that contains it, and the records on one parcel are summed.
- **Land use:** the City Planning Commission's land-use layer: the smallest land-use polygon containing the parcel's representative point (street right-of-way polygons overlap blocks). Where only the two-digit code is given, the OPA category splits single- from multi-family homes and the building description picks out schools, hospitals, hotels and warehouses.
- **Homes:** OPA has no unit count. Single-family records count as one home each; the rest of each census block's housing units go to its multi-family and mixed parcels by floor area (estimated, flagged).
- **Adopted plan (digitised).** Philadelphia2035 publishes its land-use recommendations only as the "Proposed Land Use" maps in the 18 district plans (PDF; one document covers both Far Northeast districts). The maps are vector drawings of the Commission's land-use categories, lot by lot, and `planarena/sources/pdfplan.py` turns them into a parcel layer (`adapters/philadelphia_plan.py`):
  1. **Legend.** Each swatch's fill colour is read with the label to its right.
  2. **Colour matching.** Map fill colours are matched one to one to legend colours by perceptual distance (CIELAB ΔE, Hungarian assignment; the legend can be CMYK while the map is RGB). Pairs further apart than ΔE 45 are not matched.
  3. **Visibility.** Maps often draw a wider area and clip it to the district. Only shapes that show on the page as poppler renders it are kept: the pixel colour at a point inside the shape must match that fill's rendered colour.
  4. **Registration.** A similarity transform (scale, rotation, translation) is fitted:
     - first, the rendered map's footprint is matched to the district parcels' footprint and to the district outline as images (rotations every 3° in ±90°, then every 0.5°; translation by FFT; Dice overlap);
     - then it is refined by iterative closest point from each parcel centroid to the nearest shape centroid;
     - the fit closer to the lots is kept.
  5. **Classification.** Each parcel takes the category of the smallest shape containing its representative point.
  6. **Checks.** Each district's map is used only if:
     - the median parcel-to-shape distance is 10 ft or less;
     - the plan agrees with the existing land use (16 classes) clearly more often than the same map shifted 300 ft.

     Most land keeps its use in a plan, so a misregistered map fails this test. The registration error, coverage and both agreement rates are listed per district in the ingestion report.

  The layer is flagged "digitised from the plan PDF". Districts whose map fails a check have no plan class.

**Los Angeles** uses SCAG's 2020 Annual Land Use parcels and the LA County Assessor roll (`adapters/losangeles.py`).
- **Three layers from one source:** existing land use (ALU20), the General Plan designation and the zone, both as compiled by SCAG in 2019. Where a specific plan governs, its own code is used. SCAG translates designations and zones into its code list, which has only generic housing codes, so residential designations and zones are classed by the city's own density categories (Low Medium I/II with R2 and RD zones are 2–4 homes; Medium and above, with R3–R5, are 5+).
- **Buildings:** each assessor identification number is joined to its parcel by number, else by its point (condominium units), and building area, units, year built and roll values are summed. Exempt property (schools, government) often has no building area on the roll; where a built class has a mapped footprint but no recorded floor area, floor area is the footprint times the class's median floor-area-to-footprint ratio (estimated, flagged). Floors are floor area over footprint (derived).
- **Homes:** assessor units on residential use codes, plus units on other codes where the parcel is residential or mixed.
- **Zoning screen:** the zone family (Los Angeles Municipal Code) sets the allowed uses; residential uses are allowed in the C and CM zones. The compiled zone field has no height district, which sets FAR, so capacity uses the context FAR. Specific plans are not screened.
- **Districts:** the 36 Community Plan Areas of the City Planning layer (including the airport and the port).
- **Assessed value** is the Proposition 13 roll value, which is below market for long-held property.

**Chicago** uses CMAP's Land Use Inventory 2023 over Cook County's 2025 parcels (`adapters/chicago.py`).
- **Lots:** base parcels, plus condominium parcels that lie on no base parcel; every assessor PIN is joined by its PIN10, else by its point.
- **Land use:** the smallest inventory polygon containing each parcel (the street network, code 6000, is left out). Assessor records refine it: the homes on a parcel split single-family, 2–4 and 5+; the commercial valuation's property type picks out offices, medical, hotels, warehouses, parking and mixed use.
- **Buildings and homes:** building square feet and apartments of class 2 buildings, condominium units (parking spaces and common areas excluded), and units and gross area of classes 3 and 5 from the 2024 commercial valuation (the city's last reassessment). Exempt property has no record: floor area from Overture footprints × floors, and homes on residential exempt parcels (mostly public housing) from the rest of each block's 2020 housing units (both estimated, flagged).
- **Market value:** the board of review's assessed value over the level of assessment (10% residential, 25% commercial and industrial).
- **Zoning:** district families of the Chicago Zoning Ordinance (B1, B3, C1 and C2 allow homes above the ground floor only); planned developments are not screened. **Plan:** Chicago has no citywide adopted land-use map. **Districts:** the 77 community areas.

**Houston** uses the city's "Land Use (Grouped)" layer of appraisal-district parcels (`adapters/houston.py`). The appraisal district's land-use code is the use; the Texas property class splits duplexes to fourplexes (B2–B4) and apartments (B1); vacant exempt land takes the city's own group (park, public, transport or vacant). Stacked condominium records become one parcel. Houses, plexes and condominiums are counted as homes; apartments take the rest of each block's 2020 housing units by floor area (estimated). Floors come from Overture. **Houston has no zoning and no adopted land-use map**, so every use is allowed and the plan layer is missing. Districts: the 11 council districts; the FEMA flood-hazard flag is kept per parcel.

**Dallas** uses the city's own three layers (`adapters/dallas.py`): the Existing Land Use layer (2026), the forwardDallas! 2.0 placetypes (adopted 2024) as the plan, and the base zoning districts, with the Dallas Central Appraisal District's 2026 certified files for building area, stories, year built, units and values (only those columns are read). Building classes split the business and public categories (office, medical, hotel, warehouse, school, church, parking); unit counts split housing. The appraisal district's unit counts include hotel rooms, storage units and parking spaces, so only apartment building classes count as homes. Planned developments (PD) and conservation districts are not screened. Districts: the 14 council districts.

**San Antonio** uses the Bexar Appraisal District parcels as the San Antonio River Authority republishes them (`adapters/sanantonio.py`), with the city's Future Land Use (every adopted area plan) and base zoning. The Texas property class is the use. **Its limits are stated in the app:** the appraisal district does not publish its property-use code table, so commercial property is one class (shown as retail and services); totally exempt buildings (found by asking the server for the ids of exempt parcels only; the exemptions field, which carries personal information, is never downloaded) are shown as civic. The plan covers the 61% of parcels inside an adopted area plan. Districts: the 10 council districts (2022).

**Phoenix** uses Maricopa County Assessor parcels as the city publishes them (`adapters/phoenix.py`): the assessor's property use group is the use; groups that describe ownership or tax status (public, exempt, miscellaneous) take MAG's Existing Land Use 2026. The plan is the city's General Plan land use, read with the city's own code table (residential by the designation's highest density; preserves are open space). The published parcels have no building area, units, values or year built: floor area and floors come from Overture, apartment homes from the Census (estimated), and the tax-base indicator is marked missing. Districts: the 15 urban villages.

**San Diego** uses SANDAG's Land Use 2025 (104 codes) over the county assessor's parcels in the city (`adapters/sandiego.py`), with the city's General Plan land use (community plan designations; residential by the designation's highest density) and base zoning. Assessor unit counts split housing and give the homes; living area gives residential floor area; other floor area and floors come from Overture (estimated). Districts: the community planning areas.

**Ingestion report.** `planarena/cities/ingestion.py` writes `docs/ingestion/<city>.md` for review before a city is used: the parcel count, each layer's coverage, the 16-class distributions of existing use, plan and zoning, how often the existing use matches the plan (class and analysis group), the share of existing uses the zoning screen allows, homes against Census 2020 housing units, and the fitted floor area per worker.

**Data checks in every adapter:**
- recorded lot area is replaced by the polygon's area when the two differ by more than 3×;
- floor area above FAR 50 is treated as unrecorded;
- LL84 records with a site EUI above 1,000 kBtu/sq ft are dropped as reporting errors (`calibrate.plausible_ll84`), in the calibration and in every validation.

**Coefficients in every city other than Manhattan:**
- residential site EUI: RECS 2020 by state;
- non-residential site EUI: CBECS 2018 by census division and use (national where a cell has fewer than 30 buildings);
- emission factors: eGRID2023 state electricity rates and the EPA Emission Factors Hub (AR5 GWPs), weighted by each use's fuel mix;
- persons per household: Census 2020 population per housing unit (an understatement, because vacant units are included);
- jobs: floor area per worker by type, fitted by non-negative least squares to the city's LODES blocks; a fitted rate more than 4× away from the CBECS value (the fit cannot separate that type, e.g. little floor area of it or its jobs counted at other addresses) is replaced by the CBECS value and listed in the city's ingestion report.

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

## 11. Does combining the layers help? Component ablation across cities

`planarena/models/integration.py` tests the claim behind PlanArena on observed history: that knowing what exists, what zoning permits, what the adopted plan intends and the neighbourhood context together predicts where change happens, what it becomes and how much housing it adds better than any of them alone.

**Panels.** One row per lot at t0, every attribute measured at t0 or before:
- **Los Angeles:** LA County Assessor rolls of January 2021, 2023 and 2025; existing use from SCAG 2020; General Plan and zoning as compiled by SCAG in 2019, so both precede every window.
- **Dallas:** DCAD certified files 2022, 2024 and 2026; existing use at t0 from DCAD's own state codes (the city's survey is 2025); forwardDallas! (adopted 2024) and zoning are current layers.
- **New York:** MapPLUTO 21v1, 23v1 and 25v3.1; zoning from each release; no citywide plan.
- **Milwaukee:** MPROP 2021, 2023 and 2025 (zoning from each year); development is a new building (MPROP floor area is not consistent over time).
- **Phoenix and San Diego:** the regional agency's land-use vintages (MAG 2022, 2024, 2026; SANDAG 2023, 2024, 2025). Development is a change to a built use of another analysis group (or more homes); unit counts at t0 are not available, so these two have no homes scenario.
- **Left out:** lots already under construction at t0 (SCAG 1700, MAG "Developing", SANDAG 95xx), whose completion would be trivial to predict.

**Outcome.** A building completed after t0, or floor area up by more than 25% and 2,000 sq ft (as in the Manhattan transition model); homes added = the increase in recorded homes.

**Feature blocks:**
- **E, existing:** analysis group of the existing use, lot area, floor area, built FAR, building age, homes, land-value share of the assessed value.
- **C, context:** the share of lots within 400 m built (or changed use) in the five years before t0, and the neighbours' land-use mix.
- **Z, zoning:** the zoning class, whether the existing use departs from it, and the step in homes intensity from the existing use to the zoning class.
- **P, plan:** the same for the adopted plan.

All are portable classes and ratios, with no city-specific codes.

**Protocol:**
1. **Out-of-time holdout (headline).** LightGBM fitted on the first window and scored on the next (Los Angeles, New York and Milwaukee: 2021→2023, then 2023→2025; Dallas and Phoenix: 2022→2024, then 2024→2026; San Diego: 2023→2024, then 2024→2025).
2. **Spatial cross-fitting** on the full window (five folds of 2 km tiles), as a second view.
3. **Scores.** Each block set gets AUC, average precision and precision in the top 1% and 5% of lots. The gain from adding a block has a 95% bootstrap interval over 2 km tiles.
4. **Destination.** Among developed lots, the class they became is predicted by the existing use (no change), the zoning class, the plan class and the models.
5. **Scenario assessment.** Homes added by district are compared with:
   - zoning build-out (every lot at the homes density its zoning class reaches in the city today, the 90th percentile);
   - plan build-out;
   - those increments weighted by the out-of-time likelihood;
   - the five-year trend.
6. **Leakage control where plan and zoning are current layers.** Lots whose zoning case or plan polygon dates from t0 or later (Phoenix: zoning case year and plan insert date; San Diego: zoning implementation date) are left out in a conservative variant, reported beside the main one. Los Angeles's layers predate every window and need no such control.
