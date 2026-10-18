# Ingestion report: Houston, TX

Source: City of Houston Land Use (Grouped), from Harris Central Appraisal District records (https://mycity2.houstontx.gov/gisweb02/rest/services/HoustonMap/Landuse/MapServer/0).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 630,525 | |
| Existing land use (baseline) | 613,800 | 97.3% |
| Adopted plan designation | 0 | no layer |
| Zoning district use class | 0 | no layer |
| Floor area recorded | 522,999 | 82.9% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 943,712 | 998,258 (Census 2020 housing units) | 0.95 |
| Jobs (fitted to LODES, so not a check) | 1,784,641 | 1,784,641 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 765, retail 929, other commercial 1,058, factory 1,429, storage 1,478, public facility 740, transport utility 1,166.
Replaced by the CBECS value because the fit was more than 4x away: factory (fitted 92,181).

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 465,365 | 0 | 0 |  |  |
| Small multi-family (2-4 homes) | 8,788 | 0 | 0 |  |  |
| Multi-family (5+ homes) | 5,801 | 0 | 0 |  |  |
| Mixed use (homes with shops or offices) | 314 | 0 | 0 |  |  |
| Retail, food and services | 15,532 | 0 | 0 |  |  |
| Offices | 2,783 | 0 | 0 |  |  |
| Hotels and lodging | 734 | 0 | 0 |  |  |
| Industry and manufacturing | 6,057 | 0 | 0 |  |  |
| Warehousing and logistics | 10,233 | 0 | 0 |  |  |
| Schools and universities | 1,131 | 0 | 0 |  |  |
| Hospitals and health care | 1,131 | 0 | 0 |  |  |
| Civic, religious and government | 10,815 | 0 | 0 |  |  |
| Parks and open space | 11,919 | 0 | 0 |  |  |
| Transportation and utilities | 3,803 | 0 | 0 |  |  |
| Parking | 1,239 | 0 | 0 |  |  |
| Vacant land | 68,155 | 0 | 0 |  |  |
| Unknown | 16,725 | 630,525 | 630,525 | | |
The city has no zoning layer: every use is allowed.

## Data quality

| Check | Value |
|---|---:|
| missing land use | 16,725 |
| missing plan | 630,525 |
| plan layer | none (no adopted land-use map) |
| zoning layer | none (Houston has no zoning) |
| records | 694,328 |
| stacked records merged | 63,803 |
| floor area implausible dropped | 1 |
| homes observed | 542,848 |
| homes estimated | 400,864 |
| homes census 2020 | 998,258 |
| parcels in flood hazard area | 90,608 |
| jobs lodes | 1,784,641 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (City of Houston parcels from HCAD) |
| land use | observed (HCAD land-use code and property class, City of Houston groups) |
| adopted plan | missing (Houston has no adopted land-use map) |
| zoning | none: Houston has no zoning; deed restrictions are not modelled |
| floor area | observed (HCAD building area) |
| floors and height | estimated (Overture building floors or heights; stories are not recorded) |
| homes | observed for houses, duplexes to fourplexes and condominiums; apartments estimated from Census 2020 block housing units |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (HCAD market value) |
| year built | observed |
| flood hazard | observed (FEMA special flood hazard area flag) |
| landmarks and historic districts | observed (city landmark flag) |
| mixed-use split | assumed 70% residential |
