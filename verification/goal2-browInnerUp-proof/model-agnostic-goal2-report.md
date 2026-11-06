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

## Results after GLB export and reimport

| model | rig required | eye width | brow max | eyelid max | visual raise | result |
|---|---:|---:|---:|---:|---|---|
| female Tripo | no, present but unused for deformation | 55.843 mm | 0.248 mm | 0.00002 mm | not convincingly visible | FAIL |
| male Tripo | no | 299.743 mm | 0.00003 mm | 0.230 mm | not visible | FAIL |

The female output retained its original neutral mesh and exported the shape key,
but the requested brow movement was not preserved at the verified Goal-1 brow
attachments. The male output proves that the same source code can process an
unrigged model, but its brow attachments are effectively stationary. The male
eyelid spill is an additional deformation-field defect.

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

## Decision

Goal 2 eyebrow expression: **FAIL**.

The model-agnostic onboarding and unrigged export path are demonstrated, but
the expression itself does not meet the visual or displacement acceptance
criteria. Do not proceed to Goal 3. The next repair must diagnose the mismatch
between the Goal-1 attachment coordinate frame and exported target mesh shape
key coordinates before retesting.
