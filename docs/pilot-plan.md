# Find & Return: staff interview and pilot plan

**Status:** plan only. Do not describe proposed measures as results. No childcare-centre interviews or real-item accuracy evaluation have been completed.

## 1. Learn the current workflow

Speak with 5–8 childcare staff across at least three centres, subject to each centre's permission. Include an educator who usually handles the found-items area and, if possible, a centre administrator. Ask about a recent example; avoid asking for children's names or other identifying details.

### Interview prompts

1. Think about the last item that was found. What happened from discovery until it reached the family?
2. Where do found items wait, and how do staff decide who they belong to?
3. Which parts take the most time? How often are items still unclaimed after a week?
4. What does the centre already record, and who updates it?
5. What makes an item easy or difficult to recognise (similar uniforms, faded labels, mixed bags, wet items)?
6. At what moments could a scan station fit naturally into the day? Who would use it?
7. What would make staff distrust a suggested match? What evidence should the screen show?
8. What would the centre need to approve a camera, local photo storage, and a small moving tray?
9. If it saved time, what one-time device cost and monthly support cost could the centre consider? Who approves that spend?
10. What would make the station too slow, bulky, or difficult to clean?

### Baseline log

For one normal week, ask staff to count without recording names:

| Measure | Record |
|---|---|
| Found items | Count by broad category and day |
| Logging time | Start at discovery; stop when the item is placed in the centre's current storage spot and recorded |
| Search time | Start when a family asks; stop when staff find the item or finish a reasonable unsuccessful search |
| Unresolved items | Count still waiting after 7 and 30 days |
| Handling | Number of staff touches and any repeat searches |
| Current cost | Staff time estimate, storage/material spend, and disposal/donation practice |

Use anonymous centre IDs and aggregate counts. Do not retain individual child/family-level records.

## 2. Controlled belongings test

### Set-up

- Use 30–50 ordinary belongings: bottles, lunchboxes, bags, shoes, socks, hats, and small toys.
- Get permission from each owner or use a fully synthetic set. Remove or cover names, faces, addresses, school logos, and other personal labels.
- Create a small registry with one photo per item. Capture a separate found-item view at the station; do not use the exact same image as both registry and query photo.
- Include visually similar pairs and varied colours, patterns, sizes, and wear. Record the true item ID separately as ground truth.
- Keep tray colour, camera position, light level, and camera exposure fixed. Capture at the three tray positions.
- Have staff review suggestions in randomised order. A staff member, never the software, confirms a match.

### Metrics

| Metric | Calculation |
|---|---|
| Top-1 accuracy | Correct registered item ranked first ÷ scans with a true registry match |
| Top-3 recall | Correct item appears in the first three suggestions ÷ scans with a true registry match |
| No-match detection | Unregistered scans correctly left unconfirmed ÷ all unregistered scans |
| False-confirm rate | Wrong match confirmed ÷ all staff-confirmed matches |
| Scan completion time | Median seconds from placing item on tray to reviewed suggestions |
| Registration time | Median seconds from opening the register form to saved item |
| Find time | Median seconds to find the correct registered item from a mixed registry |
| Staff acceptance | Short 1–5 usefulness/trust rating and “would use weekly?” response |
| Cost fit | Stated acceptable one-time and recurring cost; record role of person approving spend |

Report counts and denominators alongside percentages. Break down performance by category and lighting condition. The current similarity number is not calibrated; do not label it a model confidence.

## 3. Proposed early decision gates

These are hypotheses to discuss with an interviewer, not achieved outcomes:

- At least 80% top-3 recall on a held-out set of belongings with a true register match.
- No more than 5% false confirmations after staff review, with a visible “no match” option.
- A reduction of at least 30% in median time to log and retrieve versus the centre's baseline.
- Staff can complete one three-view scan comfortably in under 30 seconds.
- At least 4 of 5 interviewed operators say the workflow fits a real handover moment; at least one budget owner accepts the prototype cost range for a trial.
- No capture of children or personal identifiers during the evaluation.

If a gate misses, identify the failure mode before proposing a larger model: inconsistent item photos, lighting/glare, similar belongings, overlong scan flow, poor registry completeness, or weak staff trust.

## 4. Hardware validation in India

The README lists example retailer prices checked on 23 October 2026. Before a centre pilot, replace them with local quotes that include GST, delivery, power supply, tray fabrication, and a child-safe enclosure. The first test should use a centre's existing computer. Compare the value of a low-cost webcam and diffused light with a phone camera the centre already owns. Do not infer affordability from component prices alone: ask the budget owner about procurement, maintenance, cleaning, replacements, and who owns the device.

## 5. Privacy and operational safeguards

- Do not collect images of children or identify a child from an image.
- Use only item photos and non-identifying room labels. Do not enter child names, family phone numbers, or addresses.
- Confirm that the centre has a suitable consent and retention process before any real belongings are photographed.
- Keep the camera aimed at the tray, not the room. Use a defined deletion schedule for photos and test data.
- Keep a staff member in the loop for both match and return. Log corrections and no-matches.
- In a physical prototype, guard the tray edge, limit rotation speed/torque, prevent pinch points, and provide a simple stop control.
