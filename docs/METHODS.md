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
- **Jobs** = Σₖ cₖ / (floor area per worker)ₖ. The rates come from CBECS and are scaled once so that the observed baseline matches the employment total.
- **Emissions** = F × EUI(u) × emission factor. Both the baseline and the plan use this model, so the delta is a pure model difference.
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

**Precedent.** The conversion-precedent table is date-aware: `precedent(as_of=t)` uses only snapshot pairs that ended by t.

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
