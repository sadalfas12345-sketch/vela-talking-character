# Expanded-boundary face-fit candidate assessment

## Result

`FAILED / ABANDONED — visual integration remains unacceptable.`

Candidate: `assets/tripo/vela-photoreal/intermediates/vela-facefit-boundary-expanded-prototype.glb`

Render evidence: `verification/tripo-facefit-boundary-expanded-render/neutral.png`, `jawOpen.png`, and `eyeBlinkLeft.png`.

## Direct observations

- Neutral still has a discontinuous forehead boundary under the hair, with jagged triangular edges and exposed dark cavities at both temples.
- The widened cut removes more Tripo shell but does not create a watertight head. The lower face still ends in a visible irregular jaw edge above the pale neck shell.
- `jawOpen` deforms the donor mouth and teeth, but the jaw/neck transition remains visibly broken and the dark cavity is still exposed around the mouth and chin.
- `eyeBlinkLeft` changes the eyelid state, while the surrounding temple and hairline defects remain unchanged.

## Build evidence

- Oval expansion: `1.24`
- Depth tolerance: `0.60 IPD`
- Removed Tripo triangles: `44603`
- Retained fitted face triangles: `4785`
- Surface-conform p95 displacement: `9.798 mm`
- Surface-conform maximum displacement: `27.243 mm`
- Vertices displaced over `10 mm`: `127`

## Architecture decision

This experiment is permanently abandoned. It widens a Tripo shell cut around a donor replacement
surface and violates the required original-Tripo-vertex architecture.

## Gate decision

This candidate is not a Gate 4 pass. Do not advance Gates 5–9 or replace the served facial asset with it. The next repair must use a topology-aware head/upper-neck boundary or a watertight transition, not another wider front oval.
