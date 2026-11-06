# Goal 2 normalized landmark-motion transfer

## Reference tracking

MediaPipe Face Landmarker tracked the supplied Drive video at 24 fps for 121 frames. A 2D similarity transform using stable eye, nose, and chin landmarks removed global translation, rotation, and scale. The peak brow frame was 99.

- Peak normalized brow motion: `0.0444067` interocular distances.
- Peak normalized eyelid motion: `0.0315402` interocular distances.
- Depth motion: unmeasured. The video was used as 2D evidence only.
- The clip contains gaze, head, eyelid, and mouth changes in addition to brow motion, so it is not treated as an isolated anatomical ground truth.

## Tripo landmark targets

The same normalized 2D-to-face-frame mapping was applied to both Goal1 Tripo manifests.

| Model | Interocular distance | Target brow displacement range |
|---|---:|---:|
| Female | 55.843 mm | 1.929–3.368 mm |
| Male | 299.743 mm | 10.354–18.075 mm |

Target files:

- `female-normalized-brow-targets.json`
- `male-normalized-brow-targets.json`

## Surface transfer

The mapped targets were interpolated over the original render mesh using the same compact Gaussian field, stable landmark anchors, eyelid protection, coincident-vertex grouping, and geometric backtracking on both models.

| Model | Backtracked amplitude | Achieved nearest-brow motion | Inversions | Collapsed triangles | Reimport |
|---|---:|---:|---:|---:|---|
| Female | 0.5 | 0.178–0.357 mm | 0 | 0 | PASS |
| Male | 0.0625 | 0.096–0.317 mm | 0 | 0 | PASS |

All tested weights 0, 25, 50, 75, and 100 percent had zero winding flips and zero collapsed triangles after export and reimport. The female render was inspected. The male render sweep encountered a Blender NVIDIA driver access violation after export validation; its geometric integrity report still passed.

## Decision

- Normalized video landmark extraction: **PASS, provisional 2D only**.
- Tripo landmark target construction: **PASS**.
- Original-surface deformation: **FAIL**. The surface field cannot reproduce the measured target motion without backtracking to a visually negligible displacement.

No muscle physics, coarse embedding, mouth work, or Goal3 work was started.
