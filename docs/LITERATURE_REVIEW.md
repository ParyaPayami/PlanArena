# Literature review

**Sources and checks**
- 74 sources.
- Each is in [refs.bib](refs.bib) with its DOI or ISBN and passes `check_refs` against the record that identifier resolves to ([reference_check.md](reference_check.md)).
- Summaries are written from each source's abstract. † marks a source whose abstract was not available; its summary comes from the title and record and must be checked on reading.
- A source is cited in the paper only after the author has read it and logged the supporting passage in [citation_log.csv](citation_log.csv).

## 1. Planning problems and participation

| Study | What it does | Use in PlanArena |
|---|---|---|
| Arnstein 1969 | Typology of eight levels of citizen participation, from manipulation to citizen control. | The simulated votes are not participation; PlanArena claims no level on this ladder. |
| Rittel & Webber 1973† | Planning problems are "wicked": no definitive formulation and no single correct solution. | Why decision rules are compared instead of returning one optimum. |
| Steinitz 2012 (book) | Geodesign as six linked models: representation, process, evaluation, change, impact, decision. | Order of the Studio: existing → change → impact → decision. |

## 2. Planning support systems and urban digital twins

| Study | What it does | Use in PlanArena |
|---|---|---|
| Klosterman 1999 | What if?, a scenario planning support system (PSS): land suitability, demand projection, allocation to suitable sites. | Plan-based allocation, without a validated likelihood layer. |
| Vonk, Geertman & Schot 2005 | Survey of planners: PSS are rarely used, and the bottlenecks are on the users' side. | PlanArena makes no adoption or usability claim. |
| te Brömmelstroet 2013 | Framework for PSS performance and a review of how studies report it. | Performance is reported as validated outputs. |
| Pelzer 2017† | Conceptual framework of PSS usefulness, with an empirical illustration. | Usefulness is not tested here. |
| Geertman & Stillwell 2020 | Update of PSS developments and challenges from an international expert panel. | Positions PlanArena as a PSS. |
| Batty 2018 | Defines digital twins for cities and their limits. | The twin here is parcels, rules and models, not sensors. |
| Batty 2024† | Digital twins within the history of urban modelling: simulation, prediction, design. | Same. |
| White et al. 2021 | Online 3D twin of Dublin's Docklands where the public views proposals and gives feedback. | Interaction precedent. |
| Lehtola et al. 2022 | Reviews twin technology starting from city needs. | Scope of the twin. |
| Ferré-Bigorra et al. 2022 | Clarifies the urban digital twin concept and its components. | Terminology. |
| Lei et al. 2023 | Systematic review and Delphi survey of technical and non-technical challenges of urban twins. | Data integration across ten city schemas. |
| Azadi et al. 2025 | Review of 84 articles: technical progress, but most planning ambitions unrealised. | Report demonstrated contributions only. |
| Luo et al. 2025 | Review of 84 studies (2014–2024) of twins for built-environment perception and participation. | Participation is outside PlanArena's evidence. |
| Wu & Guan 2025 | Review of intra- and inter-city twins; calls for shared databases and cross-domain links. | Ten cities on one schema. |
| Kruse et al. 2026 | Pilots, workshops and interviews in Danish and Swedish municipalities: promised versus practised use of 3D models and twins. | Limits in practice. |

## 3. Models of urban land change

| Study | What it does | Use in PlanArena |
|---|---|---|
| Clarke, Hoppen & Gaydos 1997 | Cellular automaton of urban growth, calibrated on the San Francisco Bay Area's history. | Grid model; PlanArena works on parcels. |
| Landis & Zhang 1998 | California Urban Futures 2: site-level statistical model of land-use change, calibrated on history. | Early parcel-level, history-calibrated precedent. |
| Waddell 2002 | UrbanSim: households, firms and developers interacting through land markets. | Benchmark for predictive simulation. |
| Waddell et al. 2003 | Design and implementation of the UrbanSim microsimulation. | Same. |
| Parker et al. 2003 | Review of multi-agent models of land-use and land-cover change. | PlanArena's agents only vote; they do not simulate land markets. |
| Verburg et al. 2004 | Review of land-use change models and six research priorities (scale, drivers, neighbourhood, time, integration). | Neighbourhood and recent-change features (context block). |
| Brown et al. 2013† | Ways to improve the impact, integration and evaluation of land change models. | Evaluation design. |
| Tepe & Guldmann 2020 | Spatio-temporal autologistic model of parcel land-use change (Delaware County, Ohio). | Parcel-level change model. |
| Tepe 2023† | Machine learning for parcel-level land-use change. | Same. |
| Domingo, Palka & Hersperger 2021 | Adds the floor area each zoning plan allows per parcel to land-use scenarios in four Spanish urban areas. | Zoning in simulation, without an out-of-time test of its value. |
| Weerasinghe et al. 2025 | Review of 22 land-use models and their use in local planning. | Model choice. |
| Drici & Carpio-Pinedo 2025 | Review of 66 AI studies of fine-grained land-use mix. | Mixed use as a class. |
| Abolhasani, Ramirez Eudave & Hersperger 2026 | Standardises local planning regulations for 3D land-use simulation (Zurich, Copenhagen). | Closest recent work: regulations in simulation, two cities, no predictive test. |

## 4. Redevelopment, and what zoning changes

| Study | What it does | Use in PlanArena |
|---|---|---|
| Rosenthal & Helsley 1994† | Land is redeveloped when its value in a new use exceeds the value of the existing property; used to estimate land values. | Land-value features (land share of value). |
| Munneke 1996† | Redevelopment decisions for commercial and industrial property. | Same. |
| Mayer & Somerville 2000† | Land-use regulation and new construction. | Regulation limits supply. |
| Weber et al. 2006 | Logit of demolition permits in three Chicago community areas: smaller, older, frame buildings are demolished more. | Building age and size features. |
| Dye & McMillen 2007† | Teardowns and land values in the Chicago area. | Same. |
| Charles 2013 | Multilevel logit of single-family redevelopment in 128 inner-ring Chicago suburbs, 2000–2010. | Same. |
| Gabbe 2018 | Upzoning in Los Angeles happens where development opportunity meets weak resistance. | Rezoning is not random, hence the conservative variant. |
| Freemark 2020 | Chicago upzonings (difference-in-differences): higher prices, no more permitted homes within five years. | Zoning alone predicts little in the short run. |
| Dong 2024 | Portland 2000–2017 (matched parcels): upzoned parcels develop more often and more densely. | Zoning carries some signal. |
| Greenaway-McGrevy & Phillips 2023 | Auckland's 2016 upzoning raised construction (quasi-experimental). | Same. |
| Carruthers & Wei 2024 | Machine learning and econometrics of redevelopment in Boston, Chicago and Seattle are complements. | Prediction versus explanation. |

## 5. Plan implementation

| Study | What it does | Use in PlanArena |
|---|---|---|
| Talen 1996 | Typology of plan evaluation; implementation is rarely measured. | Why conformance is measured. |
| Laurian et al. 2004 | Conformance-based evaluation from plans and permits (six New Zealand councils). | Plan-consistency flag on each change. |
| Brody & Highfield 2005 | Wetland permits against comprehensive-plan land-use designs in Florida, over ten years. | Same. |
| Berke et al. 2006 | Conformance versus performance, and agency practices (New Zealand). | Same. |
| Loh 2011 | GIS comparison of planned and actual land use, and how to read non-conformance. | Plan versus existing use in the ingestion reports. |
| Feitelson et al. 2017† | Combines conformance and performance in evaluating a land-use plan. | A plan that matches outcomes need not have caused them. |
| Hersperger et al. 2018 | Agenda for planning in land-change science: plan intentions, implementation, external conditions. | The plan layer is an intention, tested as a predictor. |

## 6. Optimisation and collective decisions

| Study | What it does | Use in PlanArena |
|---|---|---|
| Nash 1950 | Axiomatic solution to two-party bargaining. | Bargaining rule. |
| Malczewski 2006 | Survey of GIS multicriteria decision analysis, 1990–2004. | Indicator weighting. |
| Schulze 2011 | A Condorcet-consistent, clone-independent, monotonic voting method with a polynomial-time winner. | Deciding voting rule. |
| Deb & Jain 2014 | NSGA-III: reference-point many-objective evolutionary algorithm. | Optimizer. |
| Brandt et al. 2016 (book) | Handbook of computational social choice. | Properties of voting rules. |
| Rahman & Szabó 2021 | Systematic review of 55 urban land-use optimisation studies. | Objectives and methods. |
| Zheng et al. 2023 | Graph deep reinforcement learning designs community land use and roads. | Computational comparator. |
| Feng et al. 2024 | Stakeholder equity versus ecosystem multifunctionality in land-use scenarios (Yongsheng County). | Stakeholder trade-offs. |
| Lin et al. 2025† | Explainable machine learning and spatial optimisation for urban renewal, weighing government, resident and developer interests. | Closest stakeholder-optimisation comparator. |
| Hashemi, Taleai & Abolhasani 2026 | Genetic algorithm with asymmetric Nash bargaining for land reallocation (Iran). | Bargaining inside allocation. |

## 7. Validation and uncertainty

| Study | What it does | Use in PlanArena |
|---|---|---|
| Künsch 1989 | Block bootstrap and jackknife for dependent observations. | Tile bootstrap intervals. |
| Pontius et al. 2008 | Compares 13 applications of 9 land change models at several resolutions. | Change is scored, not persistence. |
| Pontius & Millones 2011 | Replaces kappa with quantity and allocation disagreement. | Same. |
| Roberts et al. 2017 | Blocked cross-validation for spatial, temporal and grouped data. | Spatial tiles and out-of-time tests. |
| Saltelli et al. 2019 | Most published sensitivity analyses vary one factor at a time. | Impact ranges are labelled a sensitivity envelope, not intervals. |
| Ploton et al. 2020 | Random cross-validation overstates the skill of spatial models. | Same as Roberts et al. |
| Meyer & Pebesma 2021 | Area of applicability of spatial prediction models. | Cross-city transfer. |
| Black et al. 2023 | Validate transition potential directly, not only the simulated maps. | The likelihood layer is scored directly. |
| Wei, Zheng & Yang 2016 | Transfer learning between cities with scarce labels. | Leave-one-city-out transfer. |

## 8. Map digitisation and registration

| Study | What it does | Use in PlanArena |
|---|---|---|
| Besl & McKay 1992 | Iterative closest point registration. | Refines a plan map's fit to the parcels. |
| Umeyama 1991 | Closed-form least-squares similarity transform. | Each ICP step. |
| Reddy & Chatterji 1996 | FFT registration for translation, rotation and scale. | Coarse registration. |
| Chiang, Leyk & Knoblock 2014 | Survey of digital map processing. | Context. |
| Luft & Schiewe 2021 | Automatic, content-based georeferencing of historical topographic maps. | Raster maps; plan PDFs are vector, so shapes are read directly. |
| Milleville et al. 2022 | Automatic georeferencing and label extraction for topographic raster maps. | Same. |

## Gap

1. **Prediction and plan evaluation are separate literatures.** Land-change and redevelopment models predict where development occurs (Landis & Zhang 1998; Waddell 2002; Tepe & Guldmann 2020; Carruthers & Wei 2024). Plan evaluation measures conformance after the fact (Laurian et al. 2004; Loh 2011). Recent work adds zoning or planning regulations to simulation (Domingo et al. 2021; Abolhasani et al. 2026), but in one region and without testing what they add to prediction.
2. **Upzoning studies disagree.** They estimate causal effects one city at a time. Freemark (2020) finds no new construction within five years; Dong (2024) and Greenaway-McGrevy & Phillips (2023) find more construction.
3. **Claims exceed evidence.** Reviews of planning support systems and urban twins find that claims exceed demonstrated contributions (Vonk et al. 2005; Azadi et al. 2025; Kruse et al. 2026).
4. **PlanArena's test.** In seven US cities, out of time and by ablation, it asks how much zoning and the adopted plan add to existing use and neighbourhood context. Three outcomes are predicted:
   - where development happens;
   - what it becomes;
   - how many homes it adds.

   Context adds most, and zoning and the plan add small gains (VALIDATION section H). Where a plan exists only as PDF maps, it is digitised and checked against a shifted-map control.
