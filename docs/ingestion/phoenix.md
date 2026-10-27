# Ingestion report: Phoenix, AZ

Source: Maricopa County Assessor parcels (property use codes), MAG Existing Land Use 2026, City of Phoenix General Plan and zoning (https://maps.phoenix.gov/pub/rest/services/Public/COUNTY_PARCELS/MapServer/3).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 510,871 | |
| Existing land use (baseline) | 510,871 | 100.0% |
| Adopted plan designation | 510,815 | 100.0% |
| Zoning district use class | 505,765 | 99.0% |
| Floor area recorded | 418,700 | 82.0% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 624,794 | 630,784 (Census 2020 housing units) | 0.99 |
| Jobs (fitted to LODES, so not a check) | 969,095 | 969,095 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 474, retail 1,571, other commercial 3,544, factory 5,116, storage 2,464, public facility 3,659, transport utility 3,366.

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 425,025 | 369,217 | 353,343 | 79.9% | 96.5% |
| Small multi-family (2-4 homes) | 11,629 | 31,338 | 0 | 2.8% | 86.9% |
| Multi-family (5+ homes) | 12,411 | 61,670 | 117,543 | 38.3% | 89.2% |
| Mixed use (homes with shops or offices) | 16 | 6,416 | 2,485 | 100.0% | 100.0% |
| Retail, food and services | 10,836 | 19,817 | 20,027 | 54.7% | 60.2% |
| Offices | 3,514 | 5,400 | 0 | 6.7% | 53.3% |
| Hotels and lodging | 311 | 0 | 0 | 0.0% | 56.9% |
| Industry and manufacturing | 2,735 | 8,688 | 12,346 | 46.7% | 46.7% |
| Warehousing and logistics | 4,875 | 0 | 0 | 0.0% | 55.3% |
| Schools and universities | 1,061 | 2 | 0 | 0.2% | 35.2% |
| Hospitals and health care | 1,667 | 0 | 0 | 0.0% | 4.1% |
| Civic, religious and government | 2,414 | 1,796 | 0 | 16.3% | 16.3% |
| Parks and open space | 17,750 | 6,023 | 21 | 12.0% | 12.0% |
| Transportation and utilities | 1,998 | 448 | 0 | 12.8% | 12.8% |
| Parking | 442 | 0 | 0 | 0.0% | 0.0% |
| Vacant land | 14,187 | 0 | 0 | 0.0% | 0.0% |
| Unknown | 0 | 56 | 5,106 | | |

Existing use already matches the plan's class on 69.5% of parcels, and its analysis group on 87.5%.
The existing use is allowed by the zoning screen on 97.9% of parcels (legal non-conforming uses and planned developments account for the rest).

## Data quality

| Check | Value |
|---|---:|
| missing land use | 0 |
| missing plan | 56 |
| missing zoning class | 5,106 |
| records | 525,812 |
| stacked records merged | 14,941 |
| floor area implausible dropped | 121 |
| homes observed | 449,065 |
| homes estimated | 175,729 |
| homes census 2020 | 630,784 |
| jobs lodes | 969,095 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (Maricopa County parcels) |
| land use | observed (assessor property use group; MAG 2026 land use for public and exempt parcels) |
| adopted plan | observed (City of Phoenix General Plan land use, with the city's code table) |
| zoning | observed district; simplified rules (general zone sets allowed uses; context FAR) |
| floor area | estimated (Overture building footprints x floors; the published parcels have none) |
| floors and height | estimated (Overture building floors or heights) |
| homes | observed for houses, townhouses and condominiums; apartments estimated from Census 2020 block housing units |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | missing (not in the published parcels) |
| year built | missing |
| landmarks and historic districts | missing |
| mixed-use split | assumed 70% residential |
