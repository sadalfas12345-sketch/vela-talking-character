# Original Tripo localized-mouth prototype assessment

Status: **FAILED FOR GATE 4 REVIEW**

This prototype keeps the original Tripo mesh as the deformation target. Avaturn
is used only for measured jawOpen landmark displacement. No Avaturn facial mesh
or donor face geometry is imported.

## What was preserved

- Original Tripo source: `assets/tripo/vela-photoreal/generated-rigged.glb`
- Original target vertex count: 999,787
- Original Tripo mesh remains the body of the result
- Surgery is restricted to the measured lip-region face selection
- No forehead, temple, cheek, eyelid, hair, ear, or neck boundary was created
- Donor geometry imported: false

## Prototype output

- Builder: `scripts/build_original_tripo_local_mouth_prototype.py`
- Output: `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-local-mouth-prototype.glb`
- Measurement: `verification/vela-original-tripo-local-mouth-prototype.json`
- Neutral render: `verification/vela-original-tripo-local-mouth-prototype-render/neutral.png`
- Full jawOpen render: `verification/vela-original-tripo-local-mouth-prototype-render/jawOpenTransfer.png`
- Localized faces removed: 2,852
- Estimated localized vertices: 1,781
- Cavity vertices: 39
- Cavity faces: 38

## Result

The neutral state retains the Tripo identity, but the cavity reads as a dark,
block-like opening. At full transferred jawOpen, the surrounding lip and cheek
surface collapses into a wrinkled ring and the cavity remains visibly jagged.
This is not a Gate 4 pass and is not suitable for Vela runtime integration.

The failure is localized to the mouth surgery and its interaction with the
transferred deformation field. It does not invalidate the original-Tripo
vertex-transfer architecture. The next repair must preserve the original
Tripo vertices outside the smallest lip boundary while improving upper/lower
lip separation, cavity depth and occlusion, and jaw/lip deformation constraints.

## Gate disposition

- Original-vertex architecture proof: PASS from
  `verification/original-tripo-transfer-proof.md`
- Localized mouth surgery: FAILED FOR VISUAL REVIEW
- Gate 4: FAILED
- Gates 5-9: UNVERIFIED

No success claim is made.
