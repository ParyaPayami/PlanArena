---
license: other
pretty_name: PlanArena city twins
---

# PlanArena city twins (demo data)

The run-time data of the [PlanArena](https://github.com/ParyaPayami/PlanArena) demo: one parcel twin per city
(existing land use, adopted plan, zoning, floor area, homes, assessed value, map layers), built by the repository's
scripts from each city's or county's published open data. `MANIFEST.json` lists every file with its SHA-256.

- Sources are listed per city in `data/cities/registry.json` and each `twin_meta.json`; the repository's
  `results/data_manifest.json` records each download's URL and SHA-256.
- Owner, mailing, taxpayer, deed and exemption fields were never requested and are not included.
- The data are derived from public records; their use is subject to each source's terms. The code is MIT-licensed;
  this dataset is not.
