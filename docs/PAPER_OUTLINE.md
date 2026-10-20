# Systems paper: outline and evidence map

A planning document for the PlanArena systems paper (Phase 3). It contains no results; references are in [refs.bib](refs.bib):
- **Numbers:** quote them from [VALIDATION.md](VALIDATION.md), which `planarena/report.py` generates from `results/`.
- **References:** every one is found by its identifier, checked with `python -I -m planarena.tools.check_refs`, logged in [citation_log.csv](citation_log.csv) with the page that supports the claim, and read by the author.
- **AI assistance:** disclosed in the manuscript.

## Working title and question

**Question:** For each parcel and scenario, PlanArena distinguishes what exists (official land use), what is permitted (zoning), what is planned (the adopted future land use), what is likely (redevelopment model) and what is recommended (optimizer). Does combining these layers improve predictions of where change happens and what it becomes, and give scenario assessments closer to what actually gets built than capacity-based build-out (the approach of density-based scenario tools)? The test is historical and across cities, with each layer removed in turn (component ablation, VALIDATION section H, METHODS section 11).

**Draft:** *PlanArena: an integrated land-use optimizer with empirical evaluation*. It opens with why measuring impact is hard in land-use and location decisions (many dimensions, spatial interaction, uncertainty, competing interests). It then describes how such decisions are made at public hearings, where residents testify but do not vote, and what computation can measure. The rest is a systems paper in which each component has a stated test and type of evidence: empirical (held out or out of time), accounting check, algorithmic verification, or illustrative simulation (the votes). A technical supplement ([paper/supplement.pdf](../paper/supplement.pdf)) specifies every model and test; the response to the second review is [REVIEW_RESPONSE_2.md](REVIEW_RESPONSE_2.md). [paper/paper.pdf](../paper/paper.pdf), built from [paper/paper.tex.in](../paper/paper.tex.in) by `python -I -m planarena.paper`. Every number is filled from `results/`, and a test fails if the draft is stale or cites a source outside `refs.bib`.

**Literature:** [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md) (74 verified sources in eight themes, and the gap).

**Benchmarks:** ArcGIS Urban (scenario planning on zoning and land-use plans) and UrbanSim (predictive simulation). Cite them from official documentation only. PlanArena exports its layers and scenarios to ArcGIS Urban as import files (`planarena/integrations/urban_export.py`). Reading Urban scenarios back needs the Urban API and the author's sign-in, and is not built. PlanArena does not compete with Urban as a design tool. UrbanFootprint and CommunityViz are reviewed with UrbanSim in [RELATED_TOOLS.md](RELATED_TOOLS.md): none publishes a land-use optimizer; the methods PlanArena adopts from them (growth-target allocation, pro forma feasibility, build-out, constraint screens) are listed there.

**Target venue:** a planning-analytics journal (for example *Environment and Planning B*). Not the journal that rejected the earlier PIMALUOS submission.

## Contributions (each must stay true to its evidence)

| # | Claim | Evidence (VALIDATION.md section → result file) | Limits to state |
|---|---|---|---|
| 0 | **Main claim (as section H shows it).** Out of time, in seven cities:<br>• Recent development and neighbour mix (context) add the most predictive value for where development happens, significantly in five cities.<br>• Zoning and the adopted plan add smaller gains on top of context: significant in some cities, large only in Phoenix, and absent in Los Angeles.<br>• Zoning and plan classes name what developed lots became far better than "no change", and the full model does better still.<br>• Likelihood-weighted totals of homes added fall between 0.8× and 2.6× of what was built (four cities), against 76–193× for zoning or plan build-out.<br>• The five-year trend ranks districts better than any projection.<br>• A model fitted on other cities predicts less well than the city's own model, except in Milwaukee. | H → `integration_cities.json` (per city: `results/validation/integration/`); [figures/integration_layers.png](figures/integration_layers.png) | Plan layers exist in four of the seven test cities, and plan and zoning are current layers in three (conservative variant reported; some gains do not survive it). Windows are short (1–2 years). Chicago's outcome is a permit, not a completed building. In Phoenix and San Diego the first land-use vintage starts the training window, so the recent-change feature exists only in the test window. Gains are in AUC; average precision and precision among the top 1% and 5% of lots are in the result files. |
| 1 | An open, parcel-level impact engine whose change predictions beat transition-type baselines for homes and building emissions | C → `change_prediction.json` | Jobs at block level show no skill; density-only changes and access effects are not validated |
| 2 | Likelihood-weighted projections of three Manhattan rezonings are close to the homes built by 2025; capacity-based projections are not | G → `integration_replay.json` | Three cases; few redeveloped sites; the comparison is near-term (to 2025), while reviews project full build-out |
| 3 | The redevelopment model is tested over time (rolling origin, 2015–2025) and its labels are audited against certificates of occupancy | D → `rolling_origin.json` | Labels are noisy (audit precision is a lower bound); probabilities shift with the market |
| 4 | The model transfers from Manhattan to Milwaukee, and pooling helps; the reverse transfer is weak | D → `crosscity_redevelopment.json` | Two cities; new-building label only; Milwaukee pairs miss split and merged parcels |
| 5 | The three-layer workflow (existing, plan, zoning) runs in ten large US cities from official parcel-level land use | Per-city ingestion reports, `docs/ingestion/` | Plan and zoning layers are missing in some cities; classifications are crosswalked by hand |
| 6 | Realism layers change what the optimizer recommends | G → `realism_ablation.json` | Plausibility is not desirability; plan scores are heuristic "best found" |

**Not claimed:**
- public support or political feasibility (the votes are simulated scenarios, section F);
- usability gains (developer heuristic review only);
- global optimality (section E);
- causal effects of rezoning.

## Sections

1. **Introduction.** The gap between capacity-based environmental review and realized development; planning support systems that integrate prediction with impact assessment.
   *Sources needed:* reviews of planning support systems; studies of projected vs realized development after rezonings; CEQR technical manual (primary source).
2. **Data and system.**
   - Twin schema; official land use, plan and zoning per parcel in ten cities. See [METHODS.md](METHODS.md) §1 and §9.
   - Delta equations (§1).
   - Redevelopment model (§3).
   - Integration (§10).

   *Sources needed:* the official land-use, plan and zoning sources of each city (MapPLUTO, SCAG, CMAP, NCTCOG, city portals); LEHD LODES; Census TIGER; EIA RECS/CBECS; EPA eGRID and the EPA GHG Emission Factors Hub. Cite each by its official documentation page or DOI.
3. **Validation design.** Three classes (A, B, C), temporal protocols, leakage controls (R5), label audit. *Sources needed:* temporal cross-validation for spatial prediction; calibration and expected calibration error.
4. **Results.**
   - 4.1 Existing conditions and planning calculations (A, B).
   - 4.2 Prediction of change (C).
   - 4.3 Redevelopment over time and across cities (D).
   - 4.4 Integration value (H).
   - 4.5 Ten cities: existing, planned and permitted.
5. **Discussion.**
   - When likelihood weighting helps, and when it cannot (rare events, market shifts).
   - What the plan and zoning layers add to impact assessment.
   - Normative recommendations versus market plausibility (realism ablation).
6. **Limitations and threats to validity.** Use the "Limits to state" column above, plus:
   - assessor data quality (Milwaukee lot areas, inconsistent floor area across years);
   - the 2016 Milwaukee file;
   - simplified zoning.
7. **Reproducibility.** `make reproduce`; data manifest with SHA-256; code and result files released.

## Figures and tables (all generated from result files)

`python -I -m planarena.figures` writes PNG and SVG files to [figures/](figures/); they read only `results/validation/*.json`.

| Figure / table | Source |
|---|---|
| System diagram | to draw by hand from METHODS.md |
| Table: validation classes and key results | README "key results" block |
| Figure: projected vs built homes for three rezonings (capacity, pro-rated, likelihood-weighted with ranges) | `integration_replay.json` → [figures/integration_replay.png](figures/integration_replay.png) |
| Figure: rolling-origin AUC and average precision by horizon and decision year | `rolling_origin.json` → [figures/rolling_origin.png](figures/rolling_origin.png) |
| Table or figure: cross-city transfer | `crosscity_redevelopment.json` → [figures/crosscity.png](figures/crosscity.png) |
| Map: one parcel with its existing use, plan designation and zoning in the Studio | screenshot |

## Before submission

**Evidence**
- [ ] Clean-clone `make reproduce` matches the committed results (or the differences are explained). It now builds all ten cities, digitises Philadelphia's plan and runs section H; expect most of a day.
- [ ] Spot-check the digitised Philadelphia plan against the PDF maps: three districts, about 50 parcels each, recorded in a table.
- [ ] Review each city's crosswalk (source code → 16 classes) as a planner, since the classes are crosswalked by hand. List the changes.
- [ ] Decide whether the paper's impact claims stay Manhattan-only. Energy, emissions and jobs are validated only against New York City data; the other nine cities use national coefficients.

**Writing**
- [x] Draft written (`paper/`); numbers generated from the result files.
- [ ] Author's revision of the draft, and the AI-assistance statement confirmed.
- [ ] Citation style for the chosen journal. The draft uses numbered citations (`unsrtnat`); *Environment and Planning B* needs author–date. To switch, change `[numbers,sort&compress]` to `[authoryear,round]` and `unsrtnat` to `plainnat` in `paper/paper.tex.in`.
- [ ] System diagram (by hand).
- [x] Bibliography: 74 sources in [refs.bib](refs.bib), all passing `check_refs` ([reference_check.md](reference_check.md)); themes and gap in [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md).
- [ ] Read each source, then fill `read_by`, `date_read` and the page in [citation_log.csv](citation_log.csv). Start with the 11 marked † (no abstract was available).
- [ ] Advisor review (Dr. Schermer).
- [ ] AI-assistance statement.

**Release**
- [ ] Choose a licence for the code (none is set) and add a CITATION.cff.
- [ ] Data and code availability statement covering the repository, the data manifest and the licences:
  - Overture: CDLA/ODbL;
  - each city's and agency's open-data terms (SCAG, CMAP, NCTCOG/DCAD, Bexar AD, Maricopa County, SANDAG, Cook County, OPA, MPROP, MapPLUTO);
  - the Philadelphia2035 district plans.

  Check whether each source allows its derived parcel layers to be redistributed. Where it does not, release the code and the manifest only.
- [ ] Public repository and an archived release with a DOI (for example Zenodo).
