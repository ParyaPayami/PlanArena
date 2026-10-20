# Response to the second review (major revision)

The paper is [paper/paper.pdf](../paper/paper.pdf) and the new technical supplement [paper/supplement.pdf](../paper/supplement.pdf) (S1–S8 below). Every number in both is filled from `results/validation/` by `planarena/paper.py`; a test fails if either is stale. Numbers quoted here are from the same files, as of the commit that adds this response.

Two defects were found while responding, and both are corrected in every result:
- **A label error.** MapPLUTO's December 2020 release already lists about fifty buildings completed in 2020. The old new-building rule counted them as developed in every pair starting in 2020 (78% of the 2020–2021 positives, 9% of the 2020–2025 positives). A building already on the starting record is no longer counted as new. The rule was applied to every panel. The 2020–2025 AUC moved from 0.847 to 0.855, so the error was noise rather than leakage that inflated skill.
- **Missing terms in the optimizer's first-order model.** The exhaustive test of NSGA-III (point 7) showed that the first-order model ignored land-use mix, green cover and the change in who is counted when a parcel's residents change. With these terms, the exhaustive optimizer check improved too (first order finds the optimum in 14 of 15 areas, against 11 of 15 before).

## 1. Claims and evidence types

- **Title.** It is now *PlanArena: an integrated land-use optimizer with empirical evaluation*.
- **Wording.** "Validated" and "validation of every component" are gone. The abstract states the main limits: homes overstated about 1.5-fold, no skill for job change, probabilities that shift with the cycle, the trend ranking districts better, and votes that are illustrative.
- **Evidence types.** Section 4 now distinguishes four kinds of evidence: empirical predictive tests, accounting checks, algorithmic verification and illustrative simulation. Table 3 gives the evidence type of each component, and Supplement S1 lists claim by claim.

## 2. Methods specification

Supplement S3–S7 specifies:
- the floor-area rule and the three delta forms with the consistency rule;
- jobs, emissions, runoff and value;
- access, mix and green cover (Euclidean disks);
- scoring and normalisation (per cent change for totals, percentage points for shares, clipped at ±100), pillar means, overall weighted mean and default weights;
- the sensitivity variants;
- LightGBM settings and features;
- calibration metrics;
- how probabilities become expected homes, with the extension of the horizon by constant hazard and the Monte Carlo ranges;
- the optimizer: objective, conversion penalty, budget, constraints, first-order gains, rounds, polishing and the likelihood layer as a candidate restriction;
- NSGA-III settings;
- the five agents' weights (Table S10), one seat each, candidate generation, the nine rules with tie-breaking, the residents' referendum, robustness draws and sensitivity tests.

Settings are read from the code when the supplement is built.

**Release.** The repository is tagged `v1.1-review`. *To do (author):* make the repository public and archive the tag (for example on Zenodo) to obtain a DOI, then add both to "Data and code availability".

## 3. Leakage

Supplement S2 covers three points:
- **Feature timestamps.** Table S2 dates every feature family against the decision year for every panel.
- **Following lots over time.** Mergers and splits are followed by representative point: merged lots' floor area is summed, and growth is measured on the piece containing the starting point. Table S3 counts both per pair.
- **Separate observations.** The impact test selects the form and scale on two spatial folds and evaluates on three. Likelihood models are fitted only on pairs whose outcome was known at the decision year.

Dallas's "upper bounds" wording is replaced. Its zoning and plan are undated current layers adopted partly after the window's start, so "its zoning and plan results may contain post-decision information".

## 4. Impact tests

The test is now held out (Section 5.2, Table 6; Supplement S4).
- **Design.** Coefficients come from 2015 data (benchmarking and LEHD 2015). The delta form, unit-size rule and a scale factor are chosen on 1,314 lots in two of five spatial folds, and metrics are computed on the other 2,036. The test is described as conditional: given what was built, not whether it would be.
- **Stronger baselines.** Gradient-boosted regression and the transition mean are fitted on the selection lots with the same information (old and new use, floor area, lot area, old homes and value).
- **Results.**

| Method | Homes r | Value r | Emissions r | Homes total ratio |
|---|---:|---:|---:|---:|
| Engine (deployed form) | 0.79 | 0.74 | 0.60 | 1.47 |
| Gradient-boosted regression | 0.68 | 0.57 | 0.36 | 1.24 |

  The regression's total is closer. The direction of the value change is right for only 60% of lots (88% for homes); the paper says value predictions are unreliable for single lots.
- **Errors reported.** Mean absolute error, bias, totals, results by size of new building and by transition type (Tables S5–S6), and observed-vs-predicted plots (Figure S1). Conversions to mixed use account for 70% of the excess; commercial-to-mixed conversions alone overstate by 28 homes per lot. A selection-fold scale factor brings the total to 1.35.
- **Employment.** Tested by census block on blocks with no selection lot: r = 0.05, no skill. The limitation now reads "tested and showed no skill".

## 5. Housing projections

Section 5.5 is rewritten.
- **Ranking districts.** A five-year trend ranks districts better than build-out and likelihood × build-out in all four cities. The new probability × empirical-yield projection ranks them as well as the trend or better in three of four, but underestimates totals (0.12–0.45×). The paper now reports both.
- **Horizons and counts.** The text states that build-out is an end state while observed counts are gross homes added in a two- or four-year window. The build-out is described as a proxy (the density lots of a class reach today), not legal capacity (Supplement S5).
- **From probability to homes.** Defined in S5, with a new empirical-yield variant: probability × the homes developing lots of the same class and size added in the training window.
- **Rezonings.** Per-rezoning ratios are reported. Probability × capacity is 0.84× observed in East Harlem and 0.87× in Inwood, but 44× in SoHo/NoHo (3 homes built). The close total (607 against 561) is stated to come from cancelling errors, and the sum of absolute errors is reported for every projection.
- **The yield variant did not help** (summed error 471 against 212 homes), and the paper says so.

## 6. Calibration

New `planarena/models/calibration_report.py` (Supplement S5, Tables S7–S8, Figure S2). By city and by horizon and origin it reports:
- reliability in ten bins;
- observed over predicted events;
- calibration intercept and slope;
- Brier skill against the training-period rate.

Each is reported raw, after temporal isotonic recalibration (Manhattan), and after logistic recalibration on out-of-fold training probabilities.

Logistic recalibration fixes the spread (slopes near one) but not the totals. Observed over predicted still ranges 0.06–1.31 across Manhattan origins (the low end is 2020–2021, with 14 developments) and 0.41–1.24 across cities, because the development rate changes between windows.

The paper now says the model "ranks lots better than it predicts how many redevelop". "Not where it happens" is softened to "added little to ranking where development happened in these windows, once existing conditions and context were known".

## 7. Optimizer

- **Denominators.** "In 20 small areas … 15 had a plan better than no change. First-order search found the optimum in 14 of 15, and with exact re-scoring in all 15."
- **Table 9** is captioned "share of the best plan any tested method found (not a proven optimum)".
- **NSGA-III, quantitatively** (new `planarena/optimize/pareto_test.py`). Every combination of options was enumerated on 20 random tax blocks. On 10 small blocks scored exactly, the explorer recovered the exact front. On 10 medium blocks (24,576–327,680 plans) its front covered a median 100% (minimum 98.6%) of the exhaustive front's hypervolume, against 96.4% for random search with the same evaluations. The explorer now archives every plan it evaluates, and drops plans that another plan beats on every pillar after exact re-scoring.
- **Equal counts and a common objective** (Table 10). Each setting recommends, district by district, the smallest count any setting recommended there. All plans are scored with the overall score minus the conversion penalty, and the base rate among each setting's eligible parcels is reported. The share of recommended parcels redeveloped by 2025 was 11% with no realism layer, 15% with the precedent filter and 21% with the likelihood layer. The objective fell 3% with the filter and 48% with the likelihood layer.
- **Redevelopment is not implementation.** None of the recommended parcels at equal counts became the recommended use.
- **The likelihood layer** is described as a candidate restriction, not a weight.
- **The precedent trade-off** is discussed in Section 5.6.

## 8. Voting framing

- **Retitled.** Section 5.7 is now "Decision rules (illustrative)": no observed counterpart, assumed utilities, one seat per agent. The text says the agents "stand for interests, not for people, and one agent per interest does not capture the variety within it".
- **Categories and seats.** Supplement S7 justifies the five categories as the parties that commonly testify or decide at land-use hearings, and shows the seat sensitivity.
- **Heterogeneity within residents.** Each block's resident weights are drawn independently; the residents' winner is unchanged in a median 100% of draws.
- **Candidate generation.**

| Candidate set | Median distinct winners (of nine rules) |
|---|---:|
| Generated ballot | 4 |
| Agents' ideal plans only | 3 |
| Random feasible plans only | 2 |

  Condorcet winners exist in 7, 11 and 11 of 12 districts respectively (Table S11).

## 9. Other points

- **Appendix A.** Each parcel's category was also read from the rendered page's colours. It agrees with the vector reading on 99.8% of 451,691 parcels (99.4–100.0% by district). A random sample of 150 parcels with page positions and map crops is in `results/validation/philadelphia_check/` for a check by eye. *To do (author):* fill the `author_label` column of `sample.csv`; the paper does not claim this check until it is done.
- **Zoning represented.** Section 1 (Scope) and Supplement S8: use permissions and maximum FAR only (no height, bulk, parking or bonuses).
- **Ranges vs intervals.** Section 3 and S3: sensitivity ranges have no probability and are not prediction intervals. The rezoning ranges are conditional on the probabilities and omit model error.
- **Access.** "straight-line radii of 400 m and 800 m, not along walking routes" (Section 3; S3, S8).
- **Distributional effects.** New limitation: who gains and loses within a scope, displacement and future residents are not measured.
- **Job change.** Corrected as above.
- **AI declaration.** Expanded. *To do (author):* confirm the bracketed declaration.
- **Screenshots.** Rendered at a 1200 px viewport and three times resolution, and cropped along the Studio's columns, so interface text prints at about 6.5–7.5 pt.

## Not done

- A manual check of the digitised plan by eye (sheet provided; the author's task).
- A public repository and DOI (the author's task).
- Usability with planners, causal effects of zoning, distributional analysis.
- Impact validation outside Manhattan.
