# Goal 2: model-agnostic eyebrow raise

## Scope

One expression only: Avaturn `browInnerUp` motion transferred onto the original
target vertices. The same script and algorithm were run on the female Tripo and
the unrigged male Tripo. No target vertex ids, eyebrow coordinates, absolute
face dimensions, or per-character deformation constants are present in the
transfer command. Interocular distance and Goal-1 barycentric attachments are
read from each model's manifest.

## Implementation

`scripts/transfer_goal2_brow_model_agnostic.py` imports either GLB, reads its
Goal-1 attachment manifest, derives the RBF sigma and support radius as fractions
of that model's interocular distance, anchors stable semantic landmarks, and
exports a shape key named `xfer_browInnerUp_model_agnostic`. The target mesh is
the largest mesh discovered in the GLB. An armature is optional.

## Forensic diagnosis

The first report used the Goal-1 triangle vertex indices directly after GLB
export. Blender's glTF exporter reordered primitive vertices, so those indices
no longer identified the same surface points. That made real brow motion appear
near zero and falsely attributed unrelated motion to the male eyelids.

The original transfer also reused the female fit's absolute similarity scale for
the male. The corrected implementation derives motion scale as target
interocular distance divided by donor interocular distance. It then measures
the reimported GLB by spatially matching each Goal-1 attachment to the exported
neutral surface.

## Independent verification after GLB export and reimport

| model | rig required | eye width | brow max | eyelid max | visual raise | result |
|---|---:|---:|---:|---:|---|---|
| female Tripo | no, present but unused for deformation | 55.843 mm | 0.783 mm | 0.161 mm | too subtle | FAIL |
| male Tripo | no | 299.743 mm | 1.997 mm | 1.260 mm | eyelid/face distortion and failed sweep frames | FAIL |

The inversion-projection safeguard attenuated the field substantially. The
female result is only 1.40% of eye width at the largest brow landmark. The male
result is only 0.67% of eye width at the largest brow landmark, while eyelid
movement reaches 1.26 mm. The male integrity check still finds 191 winding
flips, and the intermediate-weight male sweep contains black invalid frames.

Corrected side measurements are:

| model | eye width | left brow | right brow | left eyelid | right eyelid | brow/eyelid ratio |
|---|---:|---:|---:|---:|---:|---:|
| female | 55.843 mm | 0.316 mm | 0.783 mm | 0.084 mm | 0.161 mm | 4.86 |
| male | 299.743 mm | 1.505 mm | 1.997 mm | 0.498 mm | 1.260 mm | 1.59 |

The sweep covered weights 0, 0.25, 0.5, 0.75, and 1. Female frames are
monotonic but visually too subtle. Male nonzero-weight sweep frames are
invalid black renders in the current output set.

These values are measured from the reimported GLBs by spatially matching each
Goal-1 attachment position to the exported neutral surface, not by reusing stale
pre-export vertex indices or arbitrary forehead vertices.

## Evidence

- `female-model-agnostic-render/neutral.png`
- `female-model-agnostic-render/browInnerUp_50.png`
- `female-model-agnostic-render/browInnerUp_100.png`
- `male-model-agnostic-render/neutral.png`
- `male-model-agnostic-render/browInnerUp_50.png`
- `male-model-agnostic-render/browInnerUp_100.png`
- `female-model-agnostic-transfer.json`
- `male-model-agnostic-transfer.json`
- `female-model-agnostic-measurements.json`
- `male-model-agnostic-measurements.json`
- `female-export-diagnosis.json`
- `male-export-diagnosis.json`

## Decision

Goal 2 eyebrow expression: **FAIL**.

The independent sweep and reimported geometry checks do not satisfy Goal 2.
The remaining mechanism failure is a mismatch between sparse Goal-1 surface
attachments and a stable deformation field on the male mesh. Local inversion
projection is not sufficient and can still leave invalid male triangles while
attenuating the brow motion. Goal 3 was not started.
