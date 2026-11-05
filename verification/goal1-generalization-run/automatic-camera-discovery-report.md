# Goal 1 automatic head and camera discovery

Baseline commit: `2a553daffc1e72a99e9f3ed8c95451c6bd02ae5a`

The pipeline was run without per-character source edits on the existing female
Tripo GLB and the generated male GLB. It searches spherical exterior views from
the imported world-space bounds, scores MediaPipe detections using eye, nose,
mouth, symmetry, centering, and face-size evidence, saves the selected camera,
then performs first-visible mesh raycasts with the actual imported GLB.

## Female Tripo regression

- Input: `assets/tripo/vela-photoreal/generated-rigged.glb`
- Meshes: 1
- Camera candidates: 32
- MediaPipe-detected candidates: 8
- Selected candidate: 16
- Selection score: 0.8641337695836693
- Head focus: `head-bone-metadata`
- Landmarks detected: 478
- First-visible surface hits: 478
- Valid front-facing surface hits: 477
- Ambiguous normal hits: 1, index 286
- Unresolved landmarks: 0
- Independent anatomical score: **UNVERIFIED**

## Male generalization model

- Input: `assets/tripo/generalization-male-20261105/generated-original.glb`
- Meshes: 1
- Skeleton, camera, and head metadata: none
- Model classification: head or bust-like single mesh, handled by full-mesh-bounds focus
- Camera candidates: 32
- MediaPipe-detected candidates: 10
- Selected candidate: 16
- Selection score: 0.90459995241319
- Head focus: `full-mesh-bounds`
- Landmarks detected: 478
- First-visible surface hits: 475
- Valid front-facing surface hits: 474
- Ambiguous normal hits: 1, index 62
- Unresolved landmarks: 3, indices 148, 377, 400
- Independent anatomical score: **UNVERIFIED**

## Regional accuracy score

The weighted regional score is not numerically claimable for either model in
this automatic-camera run. No independent reviewer annotations were created
for these selected images, and raycast success is not anatomical ground truth.

| Region | Weight | Female | Male |
|---|---:|---|---|
| Lips and mouth | 30 | UNVERIFIED | UNVERIFIED |
| Eyes and eyelids | 25 | UNVERIFIED | UNVERIFIED |
| Nose | 15 | UNVERIFIED | UNVERIFIED |
| Jaw and chin | 10 | UNVERIFIED | UNVERIFIED |
| Eyebrows | 10 | UNVERIFIED | UNVERIFIED |
| Remaining facial landmarks | 10 | UNVERIFIED | UNVERIFIED |
| Overall | 100 | UNVERIFIED | UNVERIFIED |

The earlier female provisional score of 52.8125/100 belongs to a different
fixed-camera manual-reference package and is not reused as evidence for this
automatic-camera run.

## Stage status

| Stage | Female | Male |
|---|---|---|
| Automatic exterior rendering | PASS | PASS |
| Camera discovery without fixed world axis | PASS | PASS |
| MediaPipe detection | PASS | PASS |
| First-visible 3D raycast | PASS with 1 ambiguous normal | PASS with 3 unresolved and 1 ambiguous |
| Independent anatomical accuracy | UNVERIFIED | UNVERIFIED |

No expression transfer, mouth reconstruction, dental fitting, or runtime work
was performed.

## Reproducible command

```powershell
python scripts/onboard_goal1_model.py <model.glb> <output-dir> --auto-camera
```

Optional `--blender`, `--landmarker-model`, and `--candidate-count` arguments
are available. The command writes camera metadata, selected neutral render,
landmark overlay, candidate evaluations, and raycast results below
`<output-dir>/camera-discovery`.

The direct evidence package used for this report is under
`verification/goal1-generalization-run/female-camera` and
`verification/goal1-generalization-run/male-camera`.
