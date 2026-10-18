# Ingestion report: Los Angeles, CA

Source: SCAG 2020 Annual Land Use (existing use, General Plan and zoning as compiled in 2019) and LA County Assessor roll 2025 (https://scag.ca.gov/data-tools-land-use).

## Coverage

| Layer | Parcels | Share |
|---|---:|---:|
| Parcels in the twin | 672,444 | |
| Existing land use (baseline) | 672,021 | 99.9% |
| Adopted plan designation | 672,251 | 100.0% |
| Zoning district use class | 671,879 | 99.9% |
| Floor area recorded | 633,454 | 94.2% |

## Homes and jobs

| Measure | Twin | Federal count | Ratio |
|---|---:|---:|---:|
| Homes | 1,476,275 | 1,496,435 (Census 2020 housing units) | 0.99 |
| Jobs (fitted to LODES, so not a check) | 1,917,454 | 1,917,454 (LODES workplace jobs) | 1.00 |

Fitted floor area per worker (sq ft): office 308, retail 1,062, other commercial 226, factory 1,067, storage 1,864, public facility 504, transport utility 284.

## Land-use classes

Plan and zoning layers often distinguish fewer classes than the existing-use layer (a plan may say 'public facilities' where the parcel is a school), so agreement is shown for the class and for its analysis group.

| Class | Existing | Plan | Zoning | Plan agrees: class | Plan agrees: group |
|---|---:|---:|---:|---:|---:|
| Single-family homes | 471,272 | 433,287 | 436,270 | 86.1% | 98.8% |
| Small multi-family (2-4 homes) | 77,275 | 119,668 | 117,228 | 63.6% | 95.1% |
| Multi-family (5+ homes) | 40,882 | 44,428 | 48,173 | 56.7% | 89.6% |
| Mixed use (homes with shops or offices) | 4,564 | 221 | 673 | 0.2% | 0.2% |
| Retail, food and services | 21,503 | 38,278 | 39,299 | 68.5% | 80.8% |
| Offices | 5,939 | 4,909 | 1 | 9.4% | 72.2% |
| Hotels and lodging | 791 | 0 | 0 | 0.0% | 68.4% |
| Industry and manufacturing | 12,727 | 21,672 | 21,890 | 82.8% | 82.8% |
| Warehousing and logistics | 3,272 | 0 | 0 | 0.0% | 83.9% |
| Schools and universities | 3,844 | 0 | 32 | 0.0% | 46.2% |
| Hospitals and health care | 253 | 0 | 0 | 0.0% | 3.2% |
| Civic, religious and government | 3,586 | 4,209 | 3,380 | 7.3% | 7.3% |
| Parks and open space | 4,915 | 4,578 | 3,403 | 45.4% | 45.4% |
| Transportation and utilities | 2,771 | 1,001 | 681 | 5.9% | 5.9% |
| Parking | 5,604 | 0 | 849 | 0.0% | 0.0% |
| Vacant land | 12,823 | 0 | 0 | 0.0% | 0.0% |
| Unknown | 423 | 193 | 565 | | |

Existing use already matches the plan's class on 75.4% of parcels, and its analysis group on 91.6%.
The existing use is allowed by the zoning screen on 98.4% of parcels (legal non-conforming uses and specific plans account for the rest).

## Data quality

| Check | Value |
|---|---:|
| missing land use | 423 |
| missing plan | 193 |
| missing zoning class | 565 |
| scag records | 672,444 |
| stacked records merged | 0 |
| assessor ains | 806,127 |
| ains not in a parcel | 2,693 |
| parcels without assessor record | 2,146 |
| floor area implausible dropped | 2 |
| floor area estimated from footprint | 10,946 |
| homes assessor | 1,476,275 |
| homes census 2020 | 1,496,435 |
| jobs lodes | 1,917,454 |

## What each column is

| Column | Status |
|---|---|
| lot boundaries | observed (SCAG parcels, from the county assessor) |
| land use | observed (SCAG 2020 existing land use, translated to 16 classes) |
| adopted plan | observed (City General Plan land use, as compiled by SCAG in 2019) |
| zoning | observed zone; simplified rules (zone family sets allowed uses; context FAR for capacity) |
| floor area | observed (assessor building square feet, summed over the parcel's AINs); estimated from the building footprint where the roll has none (mostly exempt public property) |
| plan and zoning classes | SCAG's translation, except residential designations and zones, classed by the city's own density categories |
| floors and height | derived (floor area / building footprint) |
| homes | observed (assessor units) |
| jobs | observed by block (LODES), modelled by floor area |
| assessed value | observed (Proposition 13 roll value: below market for long-held property) |
| year built | observed |
| landmarks and historic districts | missing |
| mixed-use split | assumed 70% residential |
