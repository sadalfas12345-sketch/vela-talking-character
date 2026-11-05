# Original Tripo four-channel proof

Status: **GATE 3 FAILED / REQUIRES REPAIR**

All four proof channels below were baked as shape keys on the original Tripo
mesh from `assets/tripo/vela-photoreal/generated-rigged.glb`. Avaturn supplied
only neutral-to-expression vertex motion through the calibrated landmark
correspondence. No donor facial geometry was imported and no face replacement
was performed.

## Baked channels

| Channel | Moved original vertices | Donor displacement P95 | Visual result |
| --- | ---: | ---: | --- |
| `jawOpen` | 31,094 | 16.483 mm | Closed shell collapses and does not form a real aperture |
| `viseme_PP` | 31,094 | 0.726 mm | No independently visible lip closure on the closed shell |
| `viseme_O` | 31,094 | 6.761 mm | Visible rounded/puckered lips, but no verified oral opening |
| `eyeBlinkLeft` | 31,094 | 0.472 mm | No visible 85% eyelid closure in the rendered proof |

## Evidence

- `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-jawOpen-transfer-proof.glb`
- `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-viseme_PP-transfer-proof.glb`
- `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-viseme_O-transfer-proof.glb`
- `assets/tripo/vela-photoreal/intermediates/vela-original-tripo-eyeBlinkLeft-transfer-proof.glb`
- Corresponding neutral and full-influence renders are in
  `verification/vela-original-tripo-*-transfer-proof-render/`.

## Disposition

The architecture proof remains valid: the shape keys target original Tripo
vertices and preserve neutral geometry. The four-channel articulation gate is
not passed. Mouth channels are limited by the closed shell, while blink needs
an independently validated eyelid correspondence and local deformation field.
No runtime, speech, or certification gate is claimed from these offline
renders.
