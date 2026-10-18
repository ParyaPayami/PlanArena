# Ingestion report: New York, NY

Source: NYC DCP MapPLUTO 25v3.1 (all boroughs) (https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/mappluto/nyc_mappluto_25v3_1_arc_shp.zip).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 856,634 | |
| Existing land use (baseline) | 854,072 | 99.7% |
| Adopted plan designation | 0 | no layer |
| Zoning district use class | 0 | no layer |
| Floor area recorded | 815,878 | 95.2% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Jobs (fitted to LODES, so not a check) | 4,460,294 | 4,460,294 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 343, retail 1,700, other commercial 1,378, factory 555, storage 704, public facility 1,767, transport utility 2,529.
Replaced by the CBECS value because the fit was more than 4x away: retail (fitted 348), other_commercial (fitted 76,060).

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 313,413 | 0 | 0 |  |  |
| Small multi-family (2-4 homes) | 343,697 | 0 | 0 |  |  |
| Multi-family (5+ homes) | 53,800 | 0 | 0 |  |  |
| Mixed use (homes with shops or offices) | 56,161 | 0 | 0 |  |  |
| Retail, food and services | 13,670 | 0 | 0 |  |  |
| Offices | 6,483 | 0 | 0 |  |  |
| Hotels and lodging | 994 | 0 | 0 |  |  |
| Industry and manufacturing | 3,300 | 0 | 0 |  |  |
| Warehousing and logistics | 6,071 | 0 | 0 |  |  |
| Schools and universities | 2,965 | 0 | 0 |  |  |
| Hospitals and health care | 1,168 | 0 | 0 |  |  |
| Civic, religious and government | 7,897 | 0 | 0 |  |  |
| Parks and open space | 4,741 | 0 | 0 |  |  |
| Transportation and utilities | 6,031 | 0 | 0 |  |  |
| Parking | 9,224 | 0 | 0 |  |  |
| Vacant land | 24,457 | 0 | 0 |  |  |
| Unknown | 2,562 | 856,634 | 856,634 | | |
The city has no zoning layer: every use is allowed.

## Data quality

| Check | Value |
|---|---:|
| missing land use | 2,562 |
| lots without 2020 block | 610 |
| zero building area | 40,756 |
| jobs lodes | 4,460,294 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (tax lots) |
| floor area | observed (MapPLUTO) |
| land use | observed (MapPLUTO) |
| homes | observed (MapPLUTO) |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (DOF) |
| zoning | simplified rules-as-code of the NYC Zoning Resolution |
| year built | observed |
| landmarks and historic districts | observed |
| conversion precedent | Manhattan only; not applied here |
