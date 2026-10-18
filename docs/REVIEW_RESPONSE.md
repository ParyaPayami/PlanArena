# Response to the independent review of PlanArena 1.0-rc.1

Each reviewer comment maps to the change made, the test that guards it, and the file that holds the evidence. This file contains no results; the numbers are in [VALIDATION.md](VALIDATION.md) and the README's generated blocks, both written by `planarena/report.py` from `results/`.

| Comment | What changed | Test | Evidence |
|---|---|---|---|
| **R1** Validation tests existing conditions and planning arithmetic, not change | Validation split into three classes: existing conditions, planning calculations, prediction of change. Class C predicts observed 2015→2025 changes from the 2015 state plus the observed change, against no-change and transition-type baselines. Unvalidated effects are listed | `test_docs_are_current` | `results/validation/change_prediction.json`, `integration_replay.json`; VALIDATION.md §A–C, §H |
| **R2** Mixed baseline in the deltas | Three delta forms implemented and documented (replacement, difference, hybrid). The default was chosen on prediction of observed change; its sensitivity to baseline residuals is reported | `test_difference_form_is_invariant_to_baseline_residuals`, `test_hybrid_density_change_keeps_the_parcels_own_mix` | METHODS.md §1; `results/validation/delta_forms.json` |
| **R3** "Best fit" and "optimal" overclaim; LightGBM beats the GNN | Renamed to "pattern consistency" and "recommended plan / best plan found" in UI, API and docs. Ablation: GNN (transductive, inductive), LightGBM, LightGBM + GNN embedding. The redevelopment layer uses LightGBM | `test_docs_are_current` | `results/validation/ablation_gnn.json`; README "Pattern-consistency models" |
| **R4** Redevelopment model needs auditing | Annual MapPLUTO snapshots 2015–2025; rolling-origin evaluation at 1, 3 and 5 years; isotonic calibration fitted on an earlier pair; ECE and reliability bins; tile block bootstrap; three seeds. Labels audited against DOB certificates of occupancy; results repeated with certificate-verified labels. The drop between spatial and temporal tests is shown per period. The model is also tested across cities (Manhattan and Milwaukee, outcomes known at decision time) | `test_precedent_table_only_uses_earlier_periods` | `results/validation/rolling_origin.json`, `crosscity_redevelopment.json`; VALIDATION.md §D |
| **R5** Leakage routes | Feature table with as-of dates (METHODS.md §3). The GNN cross-validation is labelled transductive, and an inductive variant is reported. The precedent table is date-aware | `test_transition_features_read_only_the_decision_year_snapshot`, `test_precedent_table_only_uses_earlier_periods` | METHODS.md §3; `results/validation/ablation_gnn.json` |
| **R6** Votes are simulated | Renamed "Simulated stakeholder scenario" everywhere; omitted interests listed. Sensitivity: Dirichlet weight draws, random candidates not built from the utilities, indifference threshold, seat allocations | `test_voting_rules_match_textbook_results`, `test_full_vote_is_consistent` | `results/validation/vote_sensitivity.json`; VALIDATION.md §F |
| **R7** Optimizer claims exceed the benchmark; price of anarchy undefined | Benchmark of six methods per district with budgets, seeds and run times; exhaustive search on small areas. Wording is "best plan found". "Price of anarchy" replaced by a heuristic "cost of fragmented control", formally defined and not used as evidence. The realism layers (precedent filter, likelihood) are ablated against what was built by 2025 | `test_exact_polish_never_worse_and_fixes_large_parcel_case`, `test_optimizer_respects_protections` | `results/validation/optimizer_gap.json`, `realism_ablation.json`; METHODS.md §5–6 |
| **R8** Aggregate agreement hides local error; overlapping buildings | Errors broken down by use, size class and district; held-out-building split for emissions; single-EUI and flat jobs-rate baselines; the in-sample status of each test is stated. Jobs rates chosen by a forward test (fit 2015, test 2023) | `test_docs_are_current` | `results/validation/existing_breakdowns.json`, `jobs_rates.json`, `emissions_ll84_2023.json` |
| **R9** Reported numbers do not reconcile | Every number in README.md and VALIDATION.md is generated from result files. The "same use" baseline ranks without test outcomes. The parcels without land use are counted and documented | `test_docs_are_current` (fails on any drift) | `planarena/report.py` |
| **R10** Tests and usability support narrower claims | Tests described as implementation correctness; usability work described as a developer heuristic review | — | README "Honesty rules built in"; [USABILITY_REVIEW.md](USABILITY_REVIEW.md) |
| **References** could not be audited | `check_refs` resolves every `.bib` entry by DOI (Crossref), arXiv ID or ISBN (Open Library) and fails on any mismatch in title, first author or year. A citation log records claim → source → page; the author reads every source | `test_fabricated_entry_with_real_doi_fails_and_real_entry_passes` | `planarena/tools/check_refs.py`; [citation_log.csv](citation_log.csv) |
| **Evidence bundle** missing | `make reproduce` runs download → twin → history → calibration → models → validation → report. Each input's URL, query and SHA-256 is recorded | `test_docs_are_current` | `Makefile`; `results/data_manifest.json`; `data/raw/*/SOURCE.json` |

## Reproduction (clean clone, 2026-10-17)

`make reproduce` was run on a fresh clone with its own Python environment; downloaded inputs were shared, everything derived from them was rebuilt. Findings and fixes:
- Every model artifact (twin, graph, GNN weights, pattern and redevelopment layers) was rebuilt bit for bit.
- The deployed conversion-precedent table in the working copy predated its date-aware version; it was regenerated, and the optimizer, vote and sensitivity results were recomputed with it. `test_deployed_precedent_table_is_current` now guards this.
- The rezoning, FEIS and homes replays in the working copy predated the recalibration; they were recomputed.
- `orjson` (needed by the API) was missing from `requirements.txt`; it is pinned now.
- The fetch step rewrote an existing GeoPackage extract (same contents, new bytes); it now leaves a verified extract alone.

After the fixes, every result file the clone produced is identical to the committed one, apart from run times. To check a reproduction: `python -I -m planarena.tools.compare_results <clone folder>`.

## Still open

- **Live inputs.** NYC Open Data tables (LL84, DOB) are live, so a new download can differ from the recorded hashes; the manifest shows which.
- **Effects without validation.** Accessibility, runoff, and emissions of buildings below the LL84 size threshold.
- **Jobs at block level.** Changes have no useful skill; this is reported, not fixed.
- **Practitioner evaluation.** Out of scope; it would need human-participant review.
