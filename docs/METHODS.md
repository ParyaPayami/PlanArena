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

*Sections to come as the Phase 1 work lands: redevelopment-model protocol and feature dates; simulated preference scenarios; optimizer benchmark; price-of-anarchy definitions.*
