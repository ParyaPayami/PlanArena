# Ingestion report: Dallas, TX

Source: City of Dallas Existing Land Use (2026), forwardDallas! 2.0 placetypes (2024), base zoning, and Dallas Central Appraisal District 2026 certified data (https://services2.arcgis.com/rwnOSbfKSwyTBcwN/arcgis/rest/services/Existing_Land_Use_Layer_2025/FeatureServer/5).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 311,431 | |
| Existing land use (baseline) | 311,431 | 100.0% |
| Adopted plan designation | 309,119 | 99.3% |
| Zoning district use class | 247,046 | 79.3% |
| Floor area recorded | 278,274 | 89.4% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 562,029 | 572,121 (Census 2020 housing units) | 0.98 |
| Jobs (fitted to LODES, so not a check) | 860,335 | 860,335 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 764, retail 1,870, other commercial 3,190, factory 1,668, storage 1,842, public facility 398, transport utility 551.

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 250,137 | 266,405 | 214,869 | 95.2% | 98.1% |
| Small multi-family (2-4 homes) | 6,194 | 0 | 4,692 | 0.0% | 96.0% |
| Multi-family (5+ homes) | 3,942 | 12,692 | 7,591 | 45.2% | 80.3% |
| Mixed use (homes with shops or offices) | 144 | 22,925 | 2,508 | 82.6% | 82.6% |
| Retail, food and services | 8,290 | 3,167 | 7,984 | 5.3% | 5.3% |
| Offices | 1,809 | 0 | 433 | 0.0% | 5.6% |
| Hotels and lodging | 266 | 0 | 0 | 0.0% | 5.7% |
| Industry and manufacturing | 348 | 580 | 8,884 | 2.1% | 14.4% |
| Warehousing and logistics | 4,064 | 1,228 | 0 | 15.4% | 19.5% |
| Schools and universities | 497 | 0 | 0 | 0.0% | 4.1% |
| Hospitals and health care | 428 | 0 | 0 | 0.0% | 12.3% |
| Civic, religious and government | 1,762 | 542 | 0 | 1.7% | 1.7% |
| Parks and open space | 3,158 | 1,375 | 0 | 21.7% | 21.7% |
| Transportation and utilities | 1,105 | 205 | 0 | 4.7% | 4.7% |
| Parking | 69 | 0 | 85 | 0.0% | 0.0% |
| Vacant land | 29,218 | 0 | 0 | 0.0% | 0.0% |
| Unknown | 0 | 2,312 | 64,385 | | |

Existing use already matches the plan's class on 77.9% of parcels, and its analysis group on 82.8%.
The existing use is allowed by the zoning screen on 99.2% of parcels (legal non-conforming uses and planned developments account for the rest).

## Data quality

| Check | Value |
|---|---:|
| missing land use | 0 |
| missing plan | 2,312 |
| missing zoning class | 64,385 |
| records | 311,431 |
| parcels without dcad record | 18,105 |
| floor area from overture | 16,361 |
| floor area implausible dropped | 10 |
| homes dcad | 562,029 |
| homes census 2020 | 572,121 |
| jobs lodes | 860,335 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (City of Dallas parcels) |
| land use | observed (City of Dallas existing land use; DCAD building classes and units refine it) |
| adopted plan | observed (forwardDallas! 2.0 placetypes, adopted 2024) |
| zoning | observed base district; simplified rules (district family sets allowed uses; context FAR) |
| floor area | observed (DCAD living and gross building area); estimated from Overture footprints where there is no DCAD record (parcels outside Dallas County, exempt property) |
| floors and height | observed (DCAD stories), else Overture |
| homes | observed (DCAD) |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (DCAD market value) |
| year built | observed |
| landmarks and historic districts | missing |
| mixed-use split | assumed 70% residential |
