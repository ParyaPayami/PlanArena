# Ingestion report: Philadelphia, PA

Source: Philadelphia OPA property assessments and PWD parcels (OpenDataPhilly) (https://opendataphilly.org/datasets/philadelphia-properties-and-assessment-history/).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 547,410 | |
| Existing land use (baseline) | 546,867 | 99.9% |
| Adopted plan designation | 455,612 | 83.2% |
| Zoning district use class | 545,409 | 99.6% |
| Floor area recorded | 505,495 | 92.3% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 716,425 | 726,795 (Census 2020 housing units) | 0.99 |
| Jobs (fitted to LODES, so not a check) | 734,106 | 734,106 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 210, retail 1,700, other commercial 1,378, factory 2,750, storage 2,400, public facility 350, transport utility 1,228.

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 428,481 | 402,954 | 418,332 | 96.6% | 98.2% |
| Small multi-family (2-4 homes) | 38,170 | 17 | 5,354 | 0.0% | 96.1% |
| Multi-family (5+ homes) | 7,169 | 13,357 | 78,172 | 48.2% | 80.0% |
| Mixed use (homes with shops or offices) | 14,611 | 16,124 | 34,820 | 76.8% | 76.8% |
| Retail, food and services | 5,284 | 5,600 | 1,061 | 62.0% | 64.3% |
| Offices | 2,623 | 1,552 | 0 | 30.1% | 54.0% |
| Hotels and lodging | 14 | 0 | 0 | 0.0% | 21.4% |
| Industry and manufacturing | 2,157 | 4,034 | 6,860 | 54.3% | 54.3% |
| Warehousing and logistics | 2,690 | 0 | 0 | 0.0% | 60.6% |
| Schools and universities | 902 | 0 | 0 | 0.0% | 79.2% |
| Hospitals and health care | 167 | 0 | 0 | 0.0% | 57.6% |
| Civic, religious and government | 3,161 | 4,059 | 0 | 71.1% | 71.1% |
| Parks and open space | 1,457 | 1,295 | 810 | 60.2% | 60.2% |
| Transportation and utilities | 4,306 | 6,022 | 0 | 38.9% | 38.9% |
| Parking | 216 | 0 | 0 | 0.0% | 0.0% |
| Vacant land | 35,459 | 598 | 0 | 2.0% | 2.0% |
| Unknown | 543 | 91,798 | 2,001 | | |

Existing use already matches the plan's class on 81.2% of parcels, and its analysis group on 90.3%.
The existing use is allowed by the zoning screen on 97.9% of parcels (legal non-conforming uses and planned developments account for the rest).

## Adopted plan digitised from PDF maps

Each district plan's land-use map, registered to the district's parcels (METHODS section 9). A map is used if its median parcel-to-shape distance is at most 10 ft and the plan agrees with the existing use clearly more often than the same map shifted 300 ft.

| District | Used | PDF pages | Median / 90th pct. error (ft) | Parcels covered | Agrees with existing use | Same, map shifted 300 ft |
|---|---|---|---|---:|---:|---:|
| Central | yes | 90, 91 | 3.37 / 29.3 | 91.8% | 74.6% | 46.5% |
| Central Northeast | yes | 70, 71 | 4.02 / 15.7 | 99.9% | 85.8% | 45.3% |
| Lower Far Northeast + Upper Far Northeast | yes | 78, 79 | 3.73 / 20.8 | 99.4% | 89.4% | 57.4% |
| Lower North | yes | 78, 79 | 1.43 / 26.7 | 93.6% | 60.3% | 42.2% |
| Lower Northeast | yes | 64, 65 | 3.22 / 14.4 | 99.9% | 85.9% | 45.1% |
| Lower Northwest | yes | 78, 79 | 3.85 / 28.5 | 97.5% | 85.4% | 63.6% |
| Lower South | yes | 68, 69 | 3.98 / 171.7 | 93.5% | 86.1% | 65.9% |
| Lower Southwest | yes | 68, 69 | 2.34 / 15.5 | 95.2% | 90.3% | 55.1% |
| North | yes | 82, 83 | 1.43 / 16.9 | 87.8% | 74.9% | 52.6% |
| North Delaware | yes | 70, 71 | 3.56 / 17.1 | 99.5% | 86.0% | 42.8% |
| River Wards | yes | 98, 99 | 1.49 / 37.6 | 91.9% | 81.8% | 43.0% |
| South | no: no Proposed Land Use map registered | | | | | |
| University Southwest | yes | 72, 73 | 1.2 / 10.5 | 99.8% | 75.4% | 50.9% |
| Upper North | yes | 76, 77 | 1.62 / 14.2 | 98.3% | 89.2% | 61.9% |
| Upper Northwest | yes | 92, 93 | 7.25 / 26.2 | 96.6% | 83.8% | 58.4% |
| West | yes | 80, 81 | 1.13 / 10.5 | 97.4% | 81.8% | 64.6% |
| West Park | no: median error 47.0 ft | | | | | |

## Data quality

| Check | Value |
|---|---:|
| missing land use | 543 |
| opa accounts | 583,690 |
| accounts not in a parcel | 2,178 |
| parcels without opa record | 1,217 |
| lot area from polygon | 4,912 |
| floor area implausible dropped | 0 |
| homes census 2020 | 726,795 |
| missing plan | 91,798 |
| jobs lodes | 734,106 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (PWD parcels) |
| floor area | observed (OPA livable area) |
| land use | observed (City Planning Commission land-use layer; OPA splits homes) |
| homes | single-family observed; other homes estimated from Census 2020 block housing units |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (OPA market value) |
| zoning | simplified (district families set allowed uses; context FAR for capacity) |
| adopted plan | digitised from the Philadelphia2035 district plans' Proposed Land Use maps (PDF); registration error and agreement checks per district in plan_digitised.json |
| year built | observed |
| landmarks and historic districts | missing |
| commercial mix | assumed 50% office, 30% retail, 20% other |
