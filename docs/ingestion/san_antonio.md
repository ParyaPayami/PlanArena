# Ingestion report: San Antonio, TX

Source: Bexar Appraisal District parcels (December 2025), City of San Antonio Future Land Use and zoning (https://gis.sara-tx.org/ags1/rest/services/FW_Bexar/BCAD_Parcels_PROD/FeatureServer/0).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 438,009 | |
| Existing land use (baseline) | 437,889 | 100.0% |
| Adopted plan designation | 265,734 | 60.7% |
| Zoning district use class | 360,879 | 82.4% |
| Floor area recorded | 399,628 | 91.2% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 589,068 | 592,481 (Census 2020 housing units) | 0.99 |
| Jobs (fitted to LODES, so not a check) | 766,138 | 766,138 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 609, retail 2,707, other commercial 1,378, factory 748, storage 2,400, public facility 968, transport utility 439.

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 373,861 | 182,793 | 304,598 | 77.2% | 96.2% |
| Small multi-family (2-4 homes) | 7,935 | 33,952 | 19,014 | 25.6% | 84.1% |
| Multi-family (5+ homes) | 834 | 16,829 | 10,842 | 37.9% | 74.2% |
| Mixed use (homes with shops or offices) | 0 | 17,025 | 839 |  |  |
| Retail, food and services | 20,542 | 6,200 | 18,162 | 28.3% | 33.5% |
| Offices | 0 | 1,459 | 592 |  |  |
| Hotels and lodging | 0 | 0 | 0 |  |  |
| Industry and manufacturing | 504 | 3,224 | 5,339 | 52.2% | 52.2% |
| Warehousing and logistics | 0 | 0 | 0 |  |  |
| Schools and universities | 0 | 0 | 0 |  |  |
| Hospitals and health care | 0 | 0 | 0 |  |  |
| Civic, religious and government | 1,797 | 1,556 | 0 | 18.1% | 18.1% |
| Parks and open space | 547 | 2,696 | 285 | 22.3% | 22.3% |
| Transportation and utilities | 202 | 0 | 1,208 | 0.0% | 0.0% |
| Parking | 0 | 0 | 0 |  |  |
| Vacant land | 31,667 | 0 | 0 | 0.0% | 0.0% |
| Unknown | 120 | 172,275 | 77,130 | | |

Existing use already matches the plan's class on 67.8% of parcels, and its analysis group on 85.6%.
The existing use is allowed by the zoning screen on 98.8% of parcels (legal non-conforming uses and planned developments account for the rest).

## Data quality

| Check | Value |
|---|---:|
| missing land use | 120 |
| missing plan | 172,275 |
| missing zoning class | 77,130 |
| records | 438,009 |
| commercial not split | 20,542 |
| exempt parcels | 10,951 |
| exempt buildings as civic | 1,762 |
| floor area from overture | 2,284 |
| floor area implausible dropped | 106 |
| homes observed | 586,266 |
| homes estimated | 2,802 |
| homes census 2020 | 592,481 |
| jobs lodes | 766,138 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (BCAD parcels) |
| land use | observed (BCAD property class); commercial is one class in the source (shown as retail and services: office, hotel and medical are not split); exempt buildings shown as civic (schools and hospitals not yet split) |
| adopted plan | observed (City of San Antonio Future Land Use, all adopted area plans) |
| zoning | observed base district; simplified rules (district family sets allowed uses; context FAR) |
| floor area | observed (BCAD square feet); estimated from Overture footprints where none is recorded |
| floors and height | estimated (Overture building floors or heights) |
| homes | observed for houses, duplexes and apartments with a unit count; other apartments estimated from Census 2020 block housing units |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (BCAD market value) |
| year built | observed |
| landmarks and historic districts | missing |
