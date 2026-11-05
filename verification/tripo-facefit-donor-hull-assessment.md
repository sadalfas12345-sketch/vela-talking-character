# Donor-hull face-cut candidate assessment

## Result

`FAIL — donor-silhouette cutting is directionally better but is not watertight.`

Candidate: `assets/tripo/vela-photoreal/intermediates/vela-facefit-donor-hull-prototype.glb`

Render evidence: `verification/tripo-facefit-donor-hull-render/neutral.png` and `jawOpen.png`.

## What changed

The Tripo shell cut was derived from the convex hull of the fitted Avaturn head vertices in the
registered camera. The donor retained its full fitted head topology and existing morph targets.
This removes the previous dependency on an expanded MediaPipe face oval for the cut boundary.

## Direct observations

- The donor hull reduces the oversized lower-face cut seen in the expanded-oval candidate.
- Neutral still exposes black cavities between the fitted face, retained hair, and temple surfaces.
- The hairline remains a jagged triangular boundary, especially at the central forehead and both
  temples.
- The lower jaw still terminates above the collar with a visible irregular transition and exposed
  shell fragments.
- `jawOpen` produces a genuine visible oral opening and donor teeth/tongue movement, but it does
  not repair the head integration defects.

## Measured build evidence

- Removed Tripo triangles: `44145`
- Retained fitted head triangles: `7145`
- Retained fitted head vertices: `3663`
- Surface-conform median displacement: `1.103 mm`
- Surface-conform P95 displacement: `14.801 mm`
- Surface-conform maximum displacement: `28.678 mm`
- Vertices displaced over `10 mm`: `454`

## Gate decision

This remains a Gate 4 failure and cannot advance to Gates 5–9. The next repair needs an explicit
watertight transition surface or a boundary loop shared with the retained Tripo shell. A convex
hull alone is insufficient and should not be widened further.
