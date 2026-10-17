# Usability review (expert review, no participants)

**Date:** 2026-10-17. **Version:** PlanArena 0.3 (after the redevelopment layer was added).

**Method:** a heuristic evaluation against Nielsen's 10 usability heuristics, combined with a cognitive walkthrough of ten planner tasks. The tasks come from the product brief and from the long-range planning requirements (area G, see [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md)).
- The review was done by the developer in the browser at 1440×900 (Studio) and 375×812 (phone game).
- **Severity scale (Nielsen):** 0 = not a problem, 1 = cosmetic, 2 = minor, 3 = major, 4 = catastrophic.

**Limits:**
- An expert review finds likely problems. It does not measure how real planners perform.
- No human participants were involved, so no IRB review applies.
- Findings marked *fixed* were re-tested in the browser after the change.

## Tasks walked through

| # | Task | Requirement | Result |
|---|---|---|---|
| T1 | Find a parcel by street address | G1, G29 | **Failed** before the fix (see F1). Passes now |
| T2 | Select many parcels, change their use, read the gains and losses | Brief | **Wrong area selected** before the fix (see F2). Passes now |
| T3 | Set a density (FAR) on a selection | G14 | Passes. No zoning reference is shown (F9) |
| T4 | Ask for the optimal plan in a district and apply it | Brief | Passes. The change count was misleading (F3) |
| T5 | Hold a stakeholder vote and understand the decision | Brief | Passes. The voting terms are jargon (F6) |
| T6 | Import a plan file and review it before applying | G2 | Passes |
| T7 | Save a study, set its status and hearing date, add a checklist step, open the staff report | G4–G13, G21, G23 | Passes. A checklist step could not be added before the fix (F4) |
| T8 | List the parcels within a notice radius | G29 | Passes |
| T9 | See where redevelopment is likely, and why | Brief | Passes. Overlay and preview modes could stack (F7) |
| T10 | Phone: play a level and finish with a council vote | Brief | Passes (after the camera fix of 2026-10-16) |

## Findings

| ID | Heuristic | Finding | Severity | Status |
|---|---|---|---:|---|
| F1 | 2 Match with the real world | Address search needed MapPLUTO's spelling ("350 5 AVENUE"). "350 5th Avenue", "Fifth Ave" and "W 4th St" failed or returned the wrong lots | 3 | **Fixed**: ordinals, spelled-out numbers and common abbreviations are normalised. API test added |
| F2 | 1 Visibility of system status | Box selection chose the wrong area. The map is rotated −29° to the street grid, but the test used a longitude/latitude rectangle. A fast drag could also lose the start point | 3 | **Fixed**: the test now runs in screen space, anchored at the press point. Re-tested: 513 of 513 expected parcels |
| F3 | 2 Match with the real world | "AI plan · 508 changes" counted the planner's own edits as the AI's. The transitions list also showed protected public facilities being converted, which were the planner's edits | 3 | **Fixed**: shows "N AI changes on top of your M", and only the AI's transitions |
| F4 | 7 Flexibility and efficiency | Staff could tick the study checklist but not add steps (requirement G11) | 2 | **Fixed**: an "Add a checklist step" field; items are validated (label at most 200 characters, at most 50 items). Acceptance test added |
| F5 | 6 Recognition rather than recall | No way to test a rezoning with the method city reviews use (requirement G14). Planners had to infer development sites themselves | 2 | **Fixed**: the Desk has a "Rezoning test" that runs the CEQR-style site screen, highlights the sites and projects homes and floor area |
| F6 | 10 Help and documentation | The vote uses Schulze, Condorcet, Smith set and Kemeny–Young without explanation | 2 | **Fixed**: a "How to read this" guide with plain-language definitions |
| F7 | 1 Visibility of system status | The redevelopment overlay and the "Previewing AI plan" mode could be active together, so it was unclear what the colours showed | 2 | **Fixed**: turning on an overlay closes the preview, and the reverse |
| F8 | 1 Visibility of system status | When zoomed out, the white selection outline hid the new colours of painted parcels | 2 | **Fixed**: the outline is thinner when zoomed out |
| F9 | 6 Recognition rather than recall | The FAR control does not show what zoning allows on the selection | 2 | Open |
| F10 | 10 Help and documentation | The plan score's units (points) were not explained | 1 | **Fixed**: a "?" tooltip explains % change, percentage points and averaging |
| F11 | 2 Match with the real world | In "If this parcel became…", open space kept most of its "tax base", because the indicator is assessed value including exempt property | 2 | **Fixed (label)**: now reads "Assessed value", with a tooltip that it is not tax revenue. Modelling exempt property is open |
| F12 | 8 Aesthetic and minimal design | Long land-use names are truncated in the palette at 1440 px | 1 | Open |
| F13 | 5 Error prevention | Painting a conversion with no precedent (e.g. an office tower to a public facility) was silent | 2 | **Fixed**: a "no precedent in Manhattan 2015–2025" warning. The optimizer skips such conversions by default |
| F14 | 4 Consistency and standards | No onboarding: a first-time user sees "Paint parcels to start a plan" but no guided first task | 2 | Open |

## What would change with real users

**Recommended next step:** a small task-based evaluation with practising planners, measuring task time, errors and the SUS questionnaire on T1–T9.
- It involves human participants, so it needs IRB review.
- It is listed for the record, not planned in this thesis.
- Without it, claims about usability stay limited to this expert review and the automated acceptance tests.
