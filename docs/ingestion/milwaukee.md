# Ingestion report: Milwaukee, WI

Source: City of Milwaukee MPROP (assessment year 2026) and parcel polygons (https://data.milwaukee.gov/dataset/mprop).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 148,042 | |
| Existing land use (baseline) | 147,896 | 99.9% |
| Adopted plan designation | 0 | no layer |
| Zoning district use class | 146,634 | 99.0% |
| Floor area recorded | 138,647 | 93.7% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 272,087 | 257,723 (Census 2020 housing units) | 1.06 |
| Jobs (fitted to LODES, so not a check) | 275,341 | 275,341 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 237, retail 1,118, other commercial 795, factory 1,758, storage 1,610, public facility 565, transport utility 1,141.

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 89,724 | 0 | 58,339 |  |  |
| Small multi-family (2-4 homes) | 37,652 | 0 | 70,485 |  |  |
| Multi-family (5+ homes) | 2,671 | 0 | 5,062 |  |  |
| Mixed use (homes with shops or offices) | 2,602 | 0 | 974 |  |  |
| Retail, food and services | 2,893 | 0 | 7,760 |  |  |
| Offices | 396 | 0 | 525 |  |  |
| Hotels and lodging | 70 | 0 | 0 |  |  |
| Industry and manufacturing | 648 | 0 | 3,001 |  |  |
| Warehousing and logistics | 632 | 0 | 0 |  |  |
| Schools and universities | 509 | 0 | 0 |  |  |
| Hospitals and health care | 308 | 0 | 0 |  |  |
| Civic, religious and government | 1,137 | 0 | 0 |  |  |
| Parks and open space | 1,006 | 0 | 488 |  |  |
| Transportation and utilities | 540 | 0 | 0 |  |  |
| Parking | 863 | 0 | 0 |  |  |
| Vacant land | 6,245 | 0 | 0 |  |  |
| Unknown | 146 | 148,042 | 1,408 | | |
The existing use is allowed by the zoning screen on 98.9% of parcels (legal non-conforming uses and planned developments account for the rest).

## Data quality

| Check | Value |
|---|---:|
| missing land use | 146 |
| tax keys | 159,556 |
| condo parcels | 530 |
| zero building area | 9,395 |
| lots outside census blocks | 34 |
| lot area from polygon | 8,822 |
| floor area implausible dropped | 0 |
| columns missing in source |  |
| jobs lodes | 275,341 |
| homes census 2020 | 257,723 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (city parcels) |
| floor area | observed (MPROP BLDG_AREA) |
| land use | observed (MPROP land-use group) |
| homes | observed (MPROP NR_UNITS on residential and mixed parcels only) |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (MPROP, incl. exempt) |
| zoning | simplified (district family sets allowed uses; context FAR for capacity) |
| year built | observed |
| landmarks and historic districts | observed (locally designated) |
| mixed-use split | assumed 70% residential |
