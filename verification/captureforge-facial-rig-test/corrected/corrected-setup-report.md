# CaptureForge corrected setup diagnostic

Branch: `wip/tripo-face-repair`

This run used the original female and male GLBs. The source files were not modified. No video coefficients were replayed.

## Female source mismatch correction

The existing female Goal 1 report was generated from `generated-rigged.glb`, while the requested input is `generated-original.glb`. Both files contain 999,787 vertices and 1,943,912 polygons. Their mesh bounds showed the rigged source translated upward relative to the original. The automatic bounding-box alignment applied to the stored Goal 1 points was:

```text
[-0.0000739209, 0.0004921779, -0.4902182891]
```

This is a measured source-to-target alignment, not a character-specific facial offset. After alignment, the exact original female surface accepted all 478 landmarks:

```text
median nearest-surface error: 3.4009753e-7
P95:                       1.1006327e-6
maximum:                   1.6645046e-6
```

Male uses the same source and target GLB, so its automatic translation is zero. Its 478-landmark surface errors are:

```text
median: 1.5595683e-7
P95:    5.4111829e-7
maximum:8.5526045e-7
```

## Controlled bone test

CaptureForge's own FaceForge builder generated 26 bones on each temporary exact-vertex copy. The original mesh was bound with an Armature modifier. All six brow bones had nonzero weights and evaluated transforms. The same axis/sign search was used on both models, selecting local X positive at 0.25 radians because it produced the greatest positive anatomical-up response.

| Measurement | Female | Male |
|---|---:|---:|
| Original vertices | 999,787 | 991,219 |
| Mapped landmarks | 478 | 478 |
| Interocular width | 0.05584185 | 0.29974317 |
| FaceForge bones | 26 | 26 |
| Brow-weighted vertices | 2,403 nonzero affected vertices | 11,651 nonzero affected vertices |
| Maximum affected-region motion | 0.00032437 | 0.00178406 |
| Landmark 70 motion | 0.000000858 | 0.000001561 |
| Minimum triangle area ratio | 0.912878 | 0.876861 |
| Collapsed triangles | 0 | 0 |
| Armature modifier evaluated | Yes | Yes |
| Controlled skin movement | PASS | PASS |

The movement is real but not a convincing eyebrow raise. Landmark motion is approximately `0.0015%` of female eye width and `0.0005%` of male eye width. The neutral and controlled renders show no meaningful eyebrow lift. This is a CaptureForge control/deformation mapping limitation, not a missing modifier or zero-weight problem.

## Visual evidence

- Female [neutral](female/neutral.png) and [controlled brow](female/controlled-brow.png)
- Male [neutral](male/neutral.png) and [controlled brow](male/controlled-brow.png)
- Female [surface attachments](female/attachments.json)
- Male [surface attachments](male/attachments.json)
- Female [measurements](female/result.json)
- Male [measurements](male/result.json)

## Decision

Preliminary rig-mechanics check: **PASS** for both. Both fitted armatures evaluate and move thousands of original-copy facial vertices with zero collapsed triangles.

Full eyebrow-expression visual check: **FAIL** for both. The controlled pose does not produce a convincing eyebrow raise. Per the stop condition, no video-coefficient replay was attempted.

FEMALE: FAIL

MALE: FAIL

OVERALL STEP RESULT: FAILED
