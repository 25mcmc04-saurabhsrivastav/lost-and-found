# Find & Return

**An AI-assisted lost-and-found scan station for childcare centres.** Staff scan found belongings, review likely visual matches from a local register, and record returns. The prototype does not identify children.

This repository contains a local-first proof of concept and a plan to validate the physical station with childcare staff in India. It is a prototype, not a deployed or accuracy-validated product.

## Demo features

- Staff dashboard for registered, found, and returned items.
- Six synthetic demo belongings seeded on first launch.
- Register an item with its photo, item type, and optional non-identifying room reference.
- Capture up to three views with a camera or upload images.
- Rank suggestions using separate colour, silhouette, and pattern comparisons; staff confirm every match.
- Record unmatched items, returns, and an activity trail.
- Store records and photos locally with SQLite; there is no account, cloud upload, or external recognition API.

## Run locally

Requires Python 3.10 or newer. From this folder:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
~~~

Open http://127.0.0.1:8000. Select a sample item to try matching without a camera, or register an item and scan it. Camera access works on localhost when granted by the browser. Image upload is also supported.

The first launch creates local_data/ for the SQLite database and photos; Git ignores that folder. These development defaults are not suitable for exposing the app to a public network.

## Matching approach

OpenCV extracts a normalized hue/saturation histogram, silhouette moments and proportions, plus grayscale and edge-density features. Descriptors from multiple scan views are combined and compared with registered photos. The score is a weighted similarity ranking, **not a probability or validated confidence score**. The item type suggestion comes from the closest registered item's staff-entered category. This baseline is not a trained deep-learning model, and generated demo images are not an accuracy benchmark.

## Physical station concept

Use an existing centre computer, a USB camera above a plain matte tray, steady diffuse LED lighting, and a slow rotating tray with three marked positions. The app guides three captures and can optionally send rotation commands to Raspberry Pi Pico firmware in hardware/pico_turntable.py. Add a physical stop switch and guard the moving tray before any pilot; the firmware is an optional build sketch.

Indicative India parts estimate observed 23 October 2026: webcam ₹2,195, ring light ₹239, NEMA 17 motor ₹436, A4988 driver ₹79, Pico ₹384, plus ₹1,000–₹2,500 for fabrication and power. Total: roughly ₹4,333–₹5,833, excluding a host computer, shipping and staff time. Prices change; start with an existing centre computer and confirm current listings before buying.

## Validate the opportunity

See docs/pilot-plan.md for staff interview questions, a non-personal item test protocol, metrics, and proposed decision gates. No staff interviews, match-accuracy measurements, centre cost acceptance, or time-savings results have been collected yet.

## Privacy and limits

- Use non-personal belongings only. Never photograph children, faces, name tags, addresses, or family contact details.
- Demo room references are fictional; use only approved non-identifying codes in a pilot.
- Photos and records remain on the machine running the app. There is no sign-in, role system, encryption-at-rest setup, backup policy, or multi-centre separation. Do not use real centre data yet.
- Matching depends on a plain background and steady lighting. Similar items can rank together; real-world accuracy is unknown.
- The app captures multiple views but does not yet control LEDs or drive a motor.

## Project layout

- backend/: FastAPI, SQLite, image matching, and optional serial control.
- frontend/: staff dashboard, camera capture, and match review.
- hardware/: optional MicroPython stepper firmware.
- docs/pilot-plan.md: interview and validation plan.
