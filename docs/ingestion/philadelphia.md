# Ingestion report: Philadelphia, PA

Source: Philadelphia OPA property assessments and PWD parcels (OpenDataPhilly) (https://opendataphilly.org/datasets/philadelphia-properties-and-assessment-history/).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 547,410 | |
| Existing land use (baseline) | 546,867 | 99.9% |
| Adopted plan designation | 0 | no layer |
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
| Single-family homes | 428,481 | 0 | 418,332 |  |  |
| Small multi-family (2-4 homes) | 38,170 | 0 | 5,354 |  |  |
| Multi-family (5+ homes) | 7,169 | 0 | 78,172 |  |  |
| Mixed use (homes with shops or offices) | 14,611 | 0 | 34,820 |  |  |
| Retail, food and services | 5,284 | 0 | 1,061 |  |  |
| Offices | 2,623 | 0 | 0 |  |  |
| Hotels and lodging | 14 | 0 | 0 |  |  |
| Industry and manufacturing | 2,157 | 0 | 6,860 |  |  |
| Warehousing and logistics | 2,690 | 0 | 0 |  |  |
| Schools and universities | 902 | 0 | 0 |  |  |
| Hospitals and health care | 167 | 0 | 0 |  |  |
| Civic, religious and government | 3,161 | 0 | 0 |  |  |
| Parks and open space | 1,457 | 0 | 810 |  |  |
| Transportation and utilities | 4,306 | 0 | 0 |  |  |
| Parking | 216 | 0 | 0 |  |  |
| Vacant land | 35,459 | 0 | 0 |  |  |
| Unknown | 543 | 547,410 | 2,001 | | |
The existing use is allowed by the zoning screen on 97.9% of parcels (legal non-conforming uses and planned developments account for the rest).

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
| year built | observed |
| landmarks and historic districts | missing |
| commercial mix | assumed 50% office, 30% retail, 20% other |
