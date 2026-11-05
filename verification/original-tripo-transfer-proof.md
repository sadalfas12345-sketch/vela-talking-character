# Original Tripo vertex deformation proof

## Architecture

This proof uses the original Tripo character mesh from `generated-rigged.glb` as the only
production deformation target. Avaturn contributes only neutral-to-`jawOpen` landmark motion.
No Avaturn face mesh is imported, no Tripo face triangles are cut, and no donor texture is used.

Evidence: `verification/vela-original-tripo-jawOpen-transfer-proof.json`.

## Measured result

- Original Tripo vertices: `999787`
- Original Tripo vertices receiving the diagnostic field: `31094`
- Neutral geometry unchanged: `true`
- Topology replacement: `false`
- Mouth surgery: `false`
- Motion handles: `476`
- Diagnostic solver: localized Gaussian RBF interpolation over the original Tripo surface
- Export: `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-jawOpen-transfer-proof.glb`

## Visual result

The neutral render preserves the original Tripo face. The transferred `jawOpen` render moves the
original textured shell, but it does not form a genuine oral aperture; the closed surface wrinkles
and collapses around the painted mouth. This is direct evidence of a topology failure, not proof
that the original-vertex architecture is invalid.

Evidence: `verification/vela-original-tripo-jawOpen-transfer-proof-render/neutral.png` and
`verification/vela-original-tripo-jawOpen-transfer-proof-render/jawOpenTransfer.png`.

## Gate status

- Architecture proof: `PASS`
- Gate 3 facial articulation: `UNVERIFIED`
- Gate 4 mouth reconstruction: `FAILED for the unmodified closed mouth topology`
- Gates 5–9: `UNVERIFIED`

The next implementation is limited to a local mouth surgery around the upper/lower lip boundary
and recessed oral cavity. Forehead, cheeks, temples, eyelids, hair, neck, body, UVs, and textures
remain outside that surgery region.
