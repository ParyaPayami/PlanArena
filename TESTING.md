# Testing PlanArena 1.0 (release candidate 1)

## Start it

1. Open the `PlanArena` folder on your Desktop.
2. Double-click **Start PlanArena.command**. A Terminal window opens, and your browser opens the Studio at http://localhost:8787.
   - If macOS says the file is from an unidentified developer, right-click it and choose **Open**.
3. To stop PlanArena, close the Terminal window.

**Phone:** double-click **Start PlanArena (phone).command** instead. The Terminal window shows an address such as `http://192.168.1.23:8787/play`. Open it on your phone over the same Wi-Fi. Use a trusted network: while it runs, anyone on that Wi-Fi can open it.

## Things to try (about 30 minutes)

| # | Try this | What should happen |
|---|---|---|
| 1 | Search "350 Fifth Ave" or "14 W 4th St" and click a result | The map flies to the lot. Its card shows zoning, building, homes, assessed value, redevelopment chance and "if this parcel became…" |
| 2 | Press **B** (box) and drag over a few blocks, then press **1** (Residential) | The selected lots turn yellow. The Impact tab shows social, economic and environmental scores with ranges, plus gains and losses by land use |
| 3 | In the left panel, choose **Set floor area ratio**, pick 8 and apply | Homes and capacity change. Warnings appear if the FAR exceeds zoning |
| 4 | **Desk → Rezoning test** | Development sites are highlighted, with projected homes and floor area (the method city environmental reviews use) |
| 5 | **Optimize → Find the optimal plan** for a district | Shows "N AI changes on top of your M". Preview, then apply or undo (⌘Z) |
| 6 | **Optimize → Show where redevelopment is likely** | Bright lots are the most likely to be rebuilt in five years; the colour is the likely new use |
| 7 | **Vote → Hold the vote** | Ballots, nine voting rules, a residents' referendum, a parcel ballot and the decision with a plain explanation. Change the seats and vote again |
| 8 | **Studies → Save current plan as a study** | Set the status and hearing date, add your own checklist step, open the staff report |
| 9 | **Import/Export → Download a sample plan**, then drop it back in | The review lists matched, unmatched and duplicate rows before you apply |
| 10 | The **ⓘ** button (top right) | Every coefficient with its source and range, the model checks and the audit-log check |
| 11 | **Play** (top right), or the phone link | Pick a neighbourhood, paint lots, press **Finish & vote**: the council chooses your plan, the AI's, or no change |

## What to note

- Anything that breaks, looks wrong, or a number you don't believe. Say which parcel or district.
- Anything a planner would find confusing, or a task planners do that is missing.
- How long things take.

Write notes anywhere and send them to me; screenshots help.

## Other cities

12. Click the city name at the top left (next to the Tier badge). Open **Milwaukee, WI** (Tier B: the city's own parcel records) or **Wauwatosa, WI** (Tier A: estimated from national data). Paint a few parcels and check that the scoreboard reacts.
13. In the same dialog, search for any US town (a small one builds in a few minutes) and click **Build twin**. Note how long it took, and whether the land-use map looks right to you for a place you know.

In a Tier A city, lots are estimated from buildings within census blocks, land use and floor area are inferred, and there is no zoning or assessed value. How far off that is, measured in Manhattan and Milwaukee, is in docs/VALIDATION.md, section G.

## Known limits (by design, or still open)

- Zoning is a simplified rules-as-code screen, not a legal determination. Bonus floor area from Mandatory Inclusionary Housing is not modelled.
- Stakeholder priorities are assumptions you can change (seats in the Vote tab).
- Assessed value includes tax-exempt property; it is not tax revenue.
- Over Wi-Fi on a phone, the game cannot be installed as an app (that needs https); it still runs in the browser.
- Usability evidence so far is an expert review ([docs/USABILITY_REVIEW.md](docs/USABILITY_REVIEW.md)). Open items: zoning limits next to the FAR control, a guided first task, and truncated land-use names.

The evidence behind the numbers is in [docs/VALIDATION.md](docs/VALIDATION.md).
