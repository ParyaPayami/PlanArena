# Ingestion report: San Diego, CA

Source: SANDAG Land Use 2025, San Diego County Assessor parcels (SanGIS), City of San Diego General Plan and zoning (https://geo.sandag.org/server/rest/services/Hosted/Land_Use_2025/FeatureServer/0).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 272,948 | |
| Existing land use (baseline) | 272,946 | 100.0% |
| Adopted plan designation | 272,855 | 100.0% |
| Zoning district use class | 256,401 | 93.9% |
| Floor area recorded | 257,005 | 94.2% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 561,089 | 548,931 (Census 2020 housing units) | 1.02 |
| Jobs (fitted to LODES, so not a check) | 817,392 | 817,392 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 329, retail 894, other commercial 618, factory 653, storage 2,400, public facility 1,724, transport utility 1,351.

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 206,149 | 150,573 | 194,079 | 68.5% | 98.3% |
| Small multi-family (2-4 homes) | 30,041 | 71,083 | 1,390 | 44.9% | 94.5% |
| Multi-family (5+ homes) | 9,548 | 23,279 | 43,663 | 58.4% | 86.3% |
| Mixed use (homes with shops or offices) | 522 | 10,521 | 816 | 80.3% | 80.3% |
| Retail, food and services | 5,830 | 3,552 | 8,510 | 28.0% | 28.0% |
| Offices | 1,436 | 0 | 628 | 0.0% | 26.6% |
| Hotels and lodging | 368 | 0 | 219 | 0.0% | 43.2% |
| Industry and manufacturing | 3,043 | 3,583 | 3,852 | 68.7% | 68.7% |
| Warehousing and logistics | 348 | 0 | 0 | 0.0% | 53.7% |
| Schools and universities | 571 | 0 | 0 | 0.0% | 69.9% |
| Hospitals and health care | 306 | 0 | 0 | 0.0% | 18.0% |
| Civic, religious and government | 1,214 | 1,356 | 0 | 20.2% | 20.2% |
| Parks and open space | 7,736 | 8,019 | 3,233 | 63.9% | 63.9% |
| Transportation and utilities | 1,594 | 889 | 0 | 42.0% | 42.0% |
| Parking | 1,050 | 0 | 11 | 0.0% | 0.0% |
| Vacant land | 3,190 | 0 | 0 | 0.0% | 0.0% |
| Unknown | 2 | 93 | 16,547 | | |

Existing use already matches the plan's class on 62.4% of parcels, and its analysis group on 91.8%.
The existing use is allowed by the zoning screen on 97.8% of parcels (legal non-conforming uses and planned developments account for the rest).

## Data quality

| Check | Value |
|---|---:|
| missing land use | 2 |
| missing plan | 93 |
| missing zoning class | 16,547 |
| records | 393,788 |
| stacked records merged | 120,840 |
| floor area from overture | 15,135 |
| floor area implausible dropped | 7 |
| homes assessor | 561,089 |
| homes census 2020 | 548,931 |
| jobs lodes | 817,392 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (San Diego County Assessor parcels) |
| land use | observed (SANDAG Land Use 2025; assessor unit counts split housing) |
| adopted plan | observed (City of San Diego General Plan and community plan land use) |
| zoning | observed base zone; simplified rules (zone family sets allowed uses; context FAR) |
| floor area | observed living area for homes; estimated from Overture footprints for other buildings (the parcel layer has no commercial floor area) |
| floors and height | estimated (Overture building floors or heights) |
| homes | observed (assessor unit counts on residential and mixed-use parcels) |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (Proposition 13 roll value: below market for long-held property) |
| year built | observed (assessor effective year) |
| landmarks and historic districts | missing |
| mixed-use split | assumed 70% residential |
