---
title: PlanArena
emoji: 🏙️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Land-use optimizer on official data for ten US cities
---

# PlanArena

An open land-use optimizer on a parcel-level digital twin: paint a change on the map and see its social, economic and
environmental effects with sensitivity ranges, where redevelopment is likely, a recommended plan, and how simulated
stakeholders would vote. Official existing land use, adopted plans and zoning for ten US cities (about 5 million
parcels). Pick a city at the top left.

- Code, methods and every test: https://github.com/ParyaPayami/PlanArena
- Impacts are tested in Manhattan; in the other cities they rest on national coefficients and are untested.
- This is a shared demo: anything you save may be seen by others and is wiped when the Space restarts. The first
  load of a large city takes a minute.
