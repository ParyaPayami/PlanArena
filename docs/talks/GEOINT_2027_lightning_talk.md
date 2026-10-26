# GEOINT Symposium 2027 Lightning Talk

Five minutes, Innovation Corner. Submissions close **October 26, 2026, 11:59 pm EDT** (Sessionboard). Every number here comes from `results/validation/` at commit 91c30eb.

## Title (recommended first; each 11 words)

1. **Capacity Said 8,423 Homes; 561 Were Built: Testing Urban Digital Twins**
2. Test Your Digital Twin Against History: Lessons from 5 Million Parcels
3. One Digital Twin from Ten Cities' Zoning, Land-Use and PDF Plans

## Session description (162 words)

In three Manhattan rezonings, standard capacity projections expected 8,423 new homes on development sites. By 2025, 561 had been built. Geospatial models like these shape where cities put homes, jobs and parks, yet they are seldom checked against what actually happened.

This talk presents PlanArena, an open parcel-level digital twin built from official land-use, zoning and comprehensive-plan data for 5 million parcels in ten US cities. That includes plans published only as PDF maps, which it converts to GIS layers automatically (99.8% agreement with an independent reading). It scores any land-use change on 11 social, economic and environmental indicators in under a second, estimates where redevelopment is likely, and recommends plans.

The focus is what happened when each model was tested against recorded change: what held up, what failed, and two errors the tests caught. Analysts, modelers and anyone building geospatial AI or digital twins will leave with five checks to run before trusting a model's output. No planning background is needed.

**Tags:** choose the closest options in the form's list. Likely candidates are AI/machine learning, data analytics, modeling and simulation or digital twins, civil or urban applications, academia or research, and open source.

**Wait list:** Yes.

## Speaker bio (no pronouns; edit to taste)

Parya Payami is a PhD candidate in Architecture at the University of Wisconsin–Milwaukee, working on AI-supported land-use decisions with parcel-level digital twins. Payami builds and tests PlanArena, an open system that combines official land-use, zoning and plan data for ten US cities, estimates the impacts and likelihood of land-use change, and checks each model against recorded outcomes.

## Outline (5:00, ten slides)

| Time | Slide | On screen |
|---|---|---|
| 0:00–0:25 | 1. Hook | **8,423 projected · 561 built**, over a map of the three rezonings |
| 0:25–0:50 | 2. The gap | A PDF plan map beside the same area as parcels |
| 0:50–1:40 | 3. PlanArena in 45 s | Recorded, captioned clip: paint, scoreboard, layers, optimizer, vote |
| 1:40–2:00 | 4. The turn | "Then we tested every model against what happened" |
| 2:00–2:28 | 5. Check 1: test forward in time | AUC 0.85–0.90 in 15 tests, each on later years |
| 2:28–2:56 | 6. Check 2: count, don't only rank | One year: **nearly 14×** more redevelopment predicted than happened |
| 2:56–3:24 | 7. Check 3: look by area | **607 vs 561** in total, but **44×** in SoHo/NoHo |
| 3:24–3:52 | 8. Check 4: audit labels against release dates | **50** finished buildings that looked like new development |
| 3:52–4:20 | 9. Check 5: verify the search on solvable cases | Two indicators the optimizer ignored; now the exact optimum in 15 of 15 |
| 4:20–5:00 | 10. Close | The five checks, a QR code to the repository, your name |

## Script (about 480 spoken words, roughly 4 minutes at a calm pace, leaving room for pauses and the clip; rehearse to 4:40)

**1. Hook (0:00).** Three Manhattan rezonings. The standard projection said 8,423 new homes on the development sites. By 2025, 561 had been built. That's not a failure of one study. It's how these projections work: they count what the rules allow, not what gets built. And they decide where a city grows. Almost nobody checks them afterwards.

**2. The gap (0:25).** In US cities these decisions are made at public hearings. The evidence is scattered: land use in one agency, zoning in another, and some plans exist only as PDF maps, like this one from Philadelphia.

**3. PlanArena (0:50).** So I built PlanArena: one parcel-level digital twin from official data, 5 million parcels in ten US cities. Those PDF maps become GIS layers automatically; an independent reading of the same maps agrees on 99.8% of parcels. Here I paint parking lots as housing, and the scoreboard updates: homes, jobs, tax base, access to parks and shops, emissions, runoff, in under a second. I can switch between what exists, what the plan intends and what zoning allows. The optimizer suggests a better plan, and simulated stakeholders vote on it under nine voting rules.

**4. The turn (1:40).** That's the tool. But the part worth your five minutes is what happened when I tested every model against what actually happened. Five checks.

**5. Forward in time (2:00).** One: test forward in time. Train on the past, test on later years, never on a random split, because neighbouring parcels share information. Done that way, the redevelopment model still ranks the lots that get rebuilt well: AUC 0.85 to 0.90 in 15 tests.

**6. Count, don't only rank (2:28).** Two: a model that ranks well can still count badly. In 2020 to 2021, it predicted nearly 14 times more redevelopment than happened. Recalibration fixed how spread out the probabilities were. It can't foresee a market shift. Check the totals, not just the ranking.

**7. Look by area (2:56).** Three: a good total can hide errors that cancel. Weighted by likelihood, the three rezonings came out at 607 homes against 561 built. Close. But in SoHo/NoHo, the projection was 44 times what was built. Report errors area by area.

**8. Audit the labels (3:24).** Four: audit your labels against when the data were released. One December release already listed buildings finished that year, so 50 existing buildings looked like new development. No accuracy metric would flag that. Checking release dates did.

**9. Verify the search (3:52).** Five: test the search, not just the model. On small blocks I enumerated every possible plan and found the optimizer was ignoring two indicators. After the fix, it finds the exact best plan in all 15 test areas.

**10. Close (4:20).** So: test forward in time; check counts as well as rankings; look by area; audit labels against release dates; verify the search where you can solve it exactly. The code and every test are open; the QR code takes you there. Test against history before you trust it. Thank you.

## Delivery

- **Demo:** use a 40-second silent screen recording with captions, not a live demo. Exhibit-hall Wi-Fi and laptops are unreliable, and five minutes leave no room to recover.
- **Slides:** large type, one number per slide, high contrast. People watch from a distance in a noisy hall.
- **Rehearsal:** aloud, with a timer, slower than feels natural. Cut words until you finish at 4:40.
- **Ask USGIF** (sarah.spurrier@usgif.org) whether slides auto-advance, and be ready for either.

## Before submitting

- **Membership:** presenters must be USGIF members. The student rate is about $35; email membership@usgif.org.
- **Availability:** you must be free to present on any of May 16–19, 2027 in Kissimmee, at your own cost for registration, travel and housing. Decisions are announced in January 2027.
- **Open code:** make the repository public before the Symposium, since the description and the closing slide say the code is open.
