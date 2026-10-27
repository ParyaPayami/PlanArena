# Related planning-support tools: methods PlanArena can use

Reviewed 2026-10-17 from each tool's own code or documentation (links below; nothing here is from secondary
summaries). The question: does any of them do land-use optimization or decision support that PlanArena should adopt?

## Short answer

None of the three publishes a land-use optimizer. UrbanSim Inc.'s site says its platform can "optimize over thousands
of alternatives", but no method is documented, and the open UrbanSim libraries contain none. What they do have are
four decision-support methods PlanArena lacks:
- allocating a growth target to parcels;
- a developer's pro forma (is a change financially feasible?);
- build-out capacity under zoning and plan;
- environmental constraint screens.

They also offer three impact modules worth matching with open national sources: water, transportation (VMT) and
fiscal. PlanArena's own strengths are absent from all three tools:
- optimization: a potential-game best response, NSGA-III Pareto fronts and a consensus mode;
- redevelopment likelihood learned from history, and precedent screening;
- stakeholder voting.

## What each tool does

| | UrbanFootprint 1.5 (open source) | CommunityViz Pro | UrbanSim |
|---|---|---|---|
| Licence | GPL-3.0; last commit 2018 | commercial ArcGIS Pro add-in (Texas A&M AgriLife) | open libraries BSD-3 (`urbansim`, `developer`, `orca`); `pandana` AGPL-3.0; UrbanSim Inc. cloud is commercial |
| Scenario editing | paint place types / building types onto parcels or grid | Paint, Land Use Designer | zoning levers, development projects |
| Impact modules | building energy, water, fiscal (residential), transportation (VMT), public health, agriculture | 100+ built-in indicators; user formulas | accessibility, real-estate market, households and jobs |
| Decision-support methods | environmental constraints (developable share removed) | Suitability (weighted criteria), Build-Out (capacity under rules), Allocator (growth to parcels by rules and capacity), Alerts | square-foot pro forma per parcel and building form; developer model picks feasible buildings to meet demand |
| Optimization | none | none | none documented |

## Methods to adopt

### 1. Growth-target allocation (CommunityViz Allocator; UrbanSim developer model)
The planner asks "where should 10,000 homes and 5,000 jobs go?", rather than "improve the score".
- **In PlanArena:** a target mode for the optimizer. Choose parcel changes that meet the homes and jobs targets at the best overall score. Respect zoning and, optionally, the adopted plan, plus capacity, precedent and feasibility.
- **Why it fits:** the potential-game optimizer can take the targets as constraints (Lagrangian penalty or greedy fill by score per added home).
- **Gap it closes:** no tool combines target allocation with multi-aspect impacts and redevelopment likelihood.

### 2. Financial feasibility: the pro forma (UrbanSim `developer`, BSD-3)
- **Method:** a change to use *u* at FAR *f* on a parcel is feasible when the value of the new building exceeds total development cost plus acquisition:
  - value: price per sq ft × floor area;
  - development cost: construction per sq ft × floor area, plus parking, financing interest and fees, and a required profit margin;
  - acquisition: the current property value.
- **In PlanArena:**
  - a feasibility flag and margin for every edit;
  - a "financially feasible" filter in the optimizer;
  - a fourth signal for "likely", next to the redevelopment model.
- **Open inputs per city:**
  - prices per sq ft by use, from assessed market values (the engine's value model);
  - construction cost per sq ft, from each city's building-permit filings (declared job cost or valuation over permitted floor area);
  - acquisition, from the assessor's market value.
- **Caveat:** Los Angeles's roll value (Proposition 13) is not market value, so LA needs sale-based values.

### 3. Plan and zoning build-out (CommunityViz Build-Out)
PlanArena already computes capacity under zoning FAR. PlanArena 3 adds the adopted plan as a layer.
- **To do:** a `respect_plan` option in the optimizer.
- **To do:** a build-out view of each scenario: homes and jobs at full zoning capacity vs at the plan's classes.
- **Report:** the share of changes consistent with the plan and with zoning (already in the plan for step 4).

### 4. Environmental constraint screens (UrbanFootprint constraints module)
Flag, and optionally exclude, adding homes or jobs on constrained land.
- **Sources already in hand:** SCAG's parcel flags (flood, fire hazard, wildland-urban interface, sea-level rise, wetland, habitat) for Los Angeles.
- **To add:** the FEMA National Flood Hazard Layer for the other cities.

### 5. Impact modules to match (step 3 knowledge base; each only with a fetched public primary source)
- **New-construction efficiency:** new buildings use less energy than the existing stock.
  - UrbanFootprint applies a reduction factor.
  - PlanArena can use RECS and CBECS energy intensity by year of construction, so redeveloped parcels get the vintage-specific EUI.
- **Water:** UrbanFootprint uses indoor water per resident by housing type, per employee by sector, and outdoor water by irrigated area × reference evapotranspiration. National open sources are still to be found and quoted.
- **Transportation (VMT):** UrbanFootprint uses the MXD "D-variables" method (density, diversity, design, destinations, distance to transit). An open national alternative:
  - baseline VMT per household by block group from a federal source;
  - D-variable elasticities from a peer-reviewed meta-analysis, cited only after the reference is checked.
- **Fiscal:** UrbanFootprint's per-unit costs and revenues are California-specific. The open, transferable method is per-capita multipliers from the Census of Governments city finances, plus property tax from the assessed value already modelled.

### Not adopted
- UrbanFootprint code and built-form library: GPL-3.0, California-specific, and unmaintained since 2018. Methods only, no code.
- `pandana`: AGPL-3.0. Network accessibility, if added, would use a permissively licensed shortest-path implementation.
- Microsimulation of households and firms (UrbanSim location choice): out of scope; PlanArena's likelihood layer is learned from observed redevelopment instead.

## Sources read
- UrbanFootprint 1.5 repository (licence, analysis modules, policy fixtures): https://github.com/CalthorpeAnalytics/urbanfootprint
- UrbanFootprint 1.5 user guide, analysis modules: https://urbanfootprint-v1.readthedocs.io/en/latest/analysis_modules/index.html
- CommunityViz Pro tools: https://communityviz.com/product-information/tools/
- CommunityViz Pro analysis framework: https://communityviz.com/product-information/cvizproanalysis/
- UrbanSim scenario modeling: https://www.urbansim.com/scenario-modeling
- UrbanSim rapid site feasibility: https://www.urbansim.com/rapid-site-feasibility
- UrbanSim developer model documentation: https://github.com/UDST/developer/blob/master/docs/developer.rst
- Licences: GitHub repository metadata for UDST/urbansim, UDST/developer, UDST/pandana and CalthorpeAnalytics/urbanfootprint
