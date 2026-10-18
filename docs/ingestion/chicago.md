# Ingestion report: Chicago, IL

Source: CMAP Land Use Inventory 2023, Cook County parcels 2025 and Cook County Assessor records (https://www.cmap.illinois.gov/data/land-use/inventory).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 606,894 | |
| Existing land use (baseline) | 606,294 | 99.9% |
| Adopted plan designation | 0 | no layer |
| Zoning district use class | 583,721 | 96.2% |
| Floor area recorded | 498,102 | 82.1% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 1,323,154 | 1,262,610 (Census 2020 housing units) | 1.05 |
| Jobs (fitted to LODES, so not a check) | 1,386,129 | 1,386,129 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 609, retail 1,700, other commercial 804, factory 2,401, storage 5,943, public facility 958, transport utility 1,429.
Replaced by the CBECS value because the fit was more than 4x away: office (fitted 105,631), retail (fitted 12,259), transport_utility (fitted 34,802).

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 313,976 | 0 | 388,783 |  |  |
| Small multi-family (2-4 homes) | 119,271 | 0 | 75,395 |  |  |
| Multi-family (5+ homes) | 34,812 | 0 | 23,012 |  |  |
| Mixed use (homes with shops or offices) | 16,566 | 0 | 7,166 |  |  |
| Retail, food and services | 26,513 | 0 | 60,335 |  |  |
| Offices | 3,687 | 0 | 908 |  |  |
| Hotels and lodging | 451 | 0 | 0 |  |  |
| Industry and manufacturing | 8,564 | 0 | 24,089 |  |  |
| Warehousing and logistics | 2,699 | 0 | 0 |  |  |
| Schools and universities | 6,058 | 0 | 0 |  |  |
| Hospitals and health care | 2,417 | 0 | 0 |  |  |
| Civic, religious and government | 9,265 | 0 | 0 |  |  |
| Parks and open space | 5,954 | 0 | 3,666 |  |  |
| Transportation and utilities | 14,405 | 0 | 367 |  |  |
| Parking | 680 | 0 | 0 |  |  |
| Vacant land | 40,976 | 0 | 0 |  |  |
| Unknown | 600 | 606,894 | 23,173 | | |
The existing use is allowed by the zoning screen on 96.0% of parcels (legal non-conforming uses and planned developments account for the rest).

## Data quality

| Check | Value |
|---|---:|
| missing land use | 600 |
| missing plan | 606,894 |
| plan layer | none citywide |
| missing zoning class | 23,173 |
| parcels | 606,894 |
| assessor pins | 881,586 |
| pins not in a parcel | 25,224 |
| floor area from overture | 26,502 |
| floor area implausible dropped | 323 |
| homes assessor | 1,250,738 |
| homes estimated | 72,416 |
| homes census 2020 | 1,262,610 |
| jobs lodes | 1,386,129 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (Cook County base parcels 2025) |
| land use | observed (CMAP Land Use Inventory 2023; assessor units and property types refine it) |
| adopted plan | missing (Chicago has no citywide adopted land-use plan) |
| zoning | observed district; simplified rules (district family sets allowed uses; context FAR) |
| floor area | observed (assessor building square feet); estimated from Overture footprints and floors where the assessor has no building record (mostly exempt property) |
| floors and height | observed stories where the commercial record has them, else Overture |
| homes | observed (assessor apartments, condominium units and units); estimated from Census 2020 block housing units on residential parcels with no record (mostly public housing) |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | derived (board of review assessed value / level of assessment: 10% residential, 25% commercial and industrial) |
| year built | observed |
| landmarks and historic districts | missing |
| mixed-use split | assumed 70% residential |
