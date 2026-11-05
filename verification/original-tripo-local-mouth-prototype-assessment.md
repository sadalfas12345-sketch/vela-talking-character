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

## Prototype outputs

- Builder: `scripts/build_original_tripo_local_mouth_prototype.py`
- Output: `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-local-mouth-prototype.glb`
- Measurement: `verification/vela-original-tripo-local-mouth-prototype.json`
- Neutral render: `verification/vela-original-tripo-local-mouth-prototype-render/neutral.png`
- Full jawOpen render: `verification/vela-original-tripo-local-mouth-prototype-render/jawOpenTransfer.png`
- Localized faces removed: 2,852
- Estimated localized vertices: 1,781
- Cavity vertices: 39
- Cavity faces: 38

The subsequent constrained candidate is:

- Output: `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-local-mouth-v2.glb`
- Neutral render: `verification/vela-original-tripo-local-mouth-v2-render/neutral.png`
- Full jawOpen render: `verification/vela-original-tripo-local-mouth-v2-render/jawOpenTransfer.png`
- Localized cut: 954 faces
- Cavity: 73 vertices and 72 faces
- Motion constraint: explicit upper-lip and lower-lip donor displacement fields

The v3 candidate additionally removes the measured lateral component from the
jawOpen upper/lower lip fields while retaining vertical and facial-depth motion:

- Output: `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-local-mouth-v3.glb`
- Render: `verification/vela-original-tripo-local-mouth-v3-render/jawOpenTransfer.png`
- Result: slightly improved symmetry, but Gate 4 remains failed because the
  lip boundary and recessed interior are still visibly synthetic.

The v4/v5 candidates replace spatially varying mouth RBF motion with measured
upper/lower lip group constraints and a multi-ring cavity. V5 also tested a
brighter emissive cavity material. The render still contains a black central
artifact and fails Gate 4, so the defect is not accepted as a lighting-only
issue. Evidence is in `verification/vela-original-tripo-local-mouth-v5-render/`.

Topology measurement for v3 is recorded in
`verification/vela-original-tripo-local-mouth-v3-measurements.json`.
The imported original shell has 55,196 boundary edges and the v3 body has
55,546, an increase of 350 localized boundary edges, with zero non-manifold
edges in both measurements. The separate cavity has an intentional open front
boundary, so this is evidence for diagnosis, not a Gate 4 pass.

## Result

The first prototype removed too much depth and produced a dark block-like
opening. The constrained v2 candidate corrects the cut to a thin seam and
separates upper and lower donor motion more plausibly. It still fails visual
Gate 4: the recessed interior is too dark, the lip boundary remains visibly
synthetic, and the full jawOpen pose does not yet provide a clean anatomical
oral opening. It is not suitable for Vela runtime integration.

The failure is localized to mouth surgery and its interaction with the
transferred deformation field. It does not invalidate the original-Tripo
vertex-transfer architecture. The next repair must preserve the original
Tripo vertices outside the smallest lip boundary while improving cavity
occlusion and the upper/lower lip boundary, then measure the aperture and
self-intersection state in neutral, half-open, and full-open poses.

## Gate disposition

- Original-vertex architecture proof: PASS from
  `verification/original-tripo-transfer-proof.md`
- Localized mouth surgery: FAILED FOR VISUAL REVIEW
- Gate 4: FAILED
- Gates 5-9: UNVERIFIED

No success claim is made.
