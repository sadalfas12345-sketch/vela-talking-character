# Goal 1: Tripo landmark detection

## Scope

This report covers only landmark detection and 3D localization on the preserved
Tripo/Mixamo GLB. No Avaturn geometry, expression transfer, mouth surgery,
teeth, tongue, or animation was used.

Source mesh: `assets/tripo/vela-photoreal/generated-rigged.glb`.
The original Tripo mesh and source GLBs were not modified.

## Method

- MediaPipe Face Landmarker with the official 478-point task model.
- Input: the original frontal Tripo render.
- Exact Blender orthographic camera and evaluated GLB transforms.
- Frontal raycasts into the evaluated original mesh.
- Front-facing normal check against the camera direction.
- Fixed image-space anatomical rejection regions for eyes, brows, nose, mouth,
  chin, and jawline.
- A second oblique camera check for first-visible-surface behavior.
- Diagnostic marker renders contain Tripo geometry and landmark helpers only.

The task model is reproducible from:
`https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`

## Measured results

| Check | Result |
|---|---:|
| Detector landmarks | 478 |
| Frontal raycast hits | 477 |
| Valid front-facing surface hits | 476 |
| Incorrect fixed-region hits | 0 |
| Back-surface hits | 0 |
| Front-normal ambiguous hits | 1 |
| Unresolved frontal landmarks | 1 |
| Oblique first-visible landmarks | 431 |
| Oblique occluded or ambiguous landmarks | 46 |
| Mean reprojection residual | 0.00009 px |
| P95 reprojection residual | 0.00019 px |
| Independently validated ground-truth landmarks | 0 |

The reprojection residual only proves camera/raycast self-consistency. It is
not an anatomical accuracy measurement.

## Exact unresolved or ambiguous points

- Index 397, `jawline_left`: no frontal surface hit.
- Index 435: frontal hit, but the surface normal is nearly tangent to the
  camera direction and is classified ambiguous.
- Oblique review rejects or cannot confirm 46 points as first-visible from the
  selected oblique camera. This includes occlusion by the character's surface
  geometry and view-dependent ambiguity; it is not silently substituted.

## Independent validation

UNVERIFIED. A separately annotated anatomical ground-truth set was not
available. The fixed ROIs and visual renders are rejection checks, not ground
truth. The repeat detector comparison averaged 0.963 px, with P95 1.890 px and
maximum 2.431 px, but this measures detector repeatability only.

## Evidence

- A: `verification/goal1-tripo-landmark-evidence/A_original_tripo_without_landmarks.png`
- B: `verification/goal1-tripo-landmark-evidence/B_original_tripo_detected_2d_landmarks.png`
- C: `verification/goal1-tripo-landmark-evidence/C_original_tripo_projected_3d_landmarks.png`
- D: `verification/goal1-tripo-landmark-evidence/D_original_tripo_anatomical_labels.png`
- E: `verification/goal1-tripo-landmark-evidence/E_original_tripo_projected_landmarks_oblique.png`
- F: `verification/goal1-tripo-landmark-evidence/F_original_tripo_projected_landmarks_side.png`
- Full measurements: `verification/goal1-tripo-landmark-evidence/goal1-tripo-landmark-report.json`
- Detector output: `verification/goal1-tripo-detected-landmarks.json`

## Determination

Detection: **PASS for producing 478 points, but anatomical correctness is UNVERIFIED**.

3D localization: **UNVERIFIED**.

Independent validation: **UNVERIFIED**.

No subsequent facial-animation goal was started.
