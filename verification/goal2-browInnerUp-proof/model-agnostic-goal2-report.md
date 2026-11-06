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

## Corrected results after GLB export and reimport

| model | rig required | eye width | brow max | eyelid max | visual raise | result |
|---|---:|---:|---:|---:|---|---|
| female Tripo | no, present but unused for deformation | 55.843 mm | 5.845 mm | 0.097 mm | visible, both brows raise | PASS |
| male Tripo | no | 299.743 mm | 22.119 mm | 0.396 mm | visible, both brows raise | PASS |

The female maximum is 10.47% of target eye width. The male maximum is 7.38% of
target eye width, consistent with the donor-derived motion after proportional
scaling rather than arbitrary amplification. Eyelid movement remains below
0.40 mm in both outputs. The male output is unrigged and required no facial rig.

These values are measured from the reimported GLBs using the manifest triangles
and barycentric coordinates, not from arbitrary forehead vertices.

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

Goal 2 eyebrow expression: **PASS for this one expression**.

Codex vision inspection of the final before-and-after close-ups found visible
upward movement of both eyebrow regions on both characters, with no obvious
eyelid, eye, nose, or skull distortion. This does not authorize Goal 3.
