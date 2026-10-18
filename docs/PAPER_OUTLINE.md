# Systems paper: outline and evidence map

A planning document for the PlanArena systems paper (Phase 3). It contains no results and no references:
- **Numbers:** quote them from [VALIDATION.md](VALIDATION.md), which `planarena/report.py` generates from `results/`.
- **References:** every one is found by its identifier, checked with `python -I -m planarena.tools.check_refs`, logged in [citation_log.csv](citation_log.csv) with the page that supports the claim, and read by the author.
- **AI assistance:** disclosed in the manuscript.

## Working title and question

**Question:** For each parcel and scenario, PlanArena distinguishes what exists (official land use), what is permitted (zoning), what is planned (the adopted future land use), what is likely (redevelopment model) and what is recommended (optimizer). Does this integration give plan assessments closer to what actually gets built than capacity-based scenario buildout (the approach of density-based scenario tools)?

**Benchmarks:** ArcGIS Urban (scenario planning on zoning and land-use plans) and UrbanSim (predictive simulation). Cite them from official documentation only. PlanArena exports to, and analyses scenarios from, ArcGIS Urban; it does not compete with it as a design tool.

**Target venue:** a planning-analytics journal (for example *Environment and Planning B*). Not the journal that rejected the earlier PIMALUOS submission.

## Contributions (each must stay true to its evidence)

| # | Claim | Evidence (VALIDATION.md section → result file) | Limits to state |
|---|---|---|---|
| 1 | An open, parcel-level impact engine whose change predictions beat transition-type baselines for homes and building emissions | C → `change_prediction.json` | Jobs at block level show no skill; density-only changes and access effects are not validated |
| 2 | Likelihood-weighted projections of three Manhattan rezonings are close to the homes built by 2025; capacity-based projections are not | G → `integration_replay.json` | Three cases; few redeveloped sites; the comparison is near-term (to 2025), while reviews project full build-out |
| 3 | The redevelopment model is tested over time (rolling origin, 2015–2025) and its labels are audited against certificates of occupancy | D → `rolling_origin.json` | Labels are noisy (audit precision is a lower bound); probabilities shift with the market |
| 4 | The model transfers from Manhattan to Milwaukee, and pooling helps; the reverse transfer is weak | D → `crosscity_redevelopment.json` | Two cities; new-building label only; Milwaukee pairs miss split and merged parcels |
| 5 | The three-layer workflow (existing, plan, zoning) runs in ten large US cities from official parcel-level land use | Per-city ingestion reports (to come) | Plan and zoning layers are missing in some cities; classifications are crosswalked by hand |
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

- [ ] Clean-clone `make reproduce` matches the committed results (or the differences are explained).
- [ ] Every reference passes `check_refs`, has a citation-log row with a page, and was read by the author.
- [ ] Advisor review (Dr. Schermer).
- [ ] AI-assistance statement.
- [ ] Data and code availability statement (repository, data manifest, licences: Overture CDLA/ODbL, city open-data terms).
