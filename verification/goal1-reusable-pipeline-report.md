# Goal 1: reusable facial landmark pipeline

## Reusable command

The model-agnostic onboarding entry point is:

```powershell
python scripts/onboard_goal1_model.py <model.glb> <output-directory>
```

For a model with an already calibrated detector image and surface audit:

```powershell
python scripts/onboard_goal1_model.py <model.glb> <output-directory> `
  --landmarks-json <landmarks.json> `
  --raycast-report <surface-report.json> `
  --attachment-manifest <barycentric-manifest.json>
```

The script does not assume Tripo names, vertex IDs, head height, face scale, camera axes, or fixed dimensions. It reads GLB node transforms, mesh bounds, mesh primitives, cameras, skins, joints, and head-related metadata. If a GLB does not provide calibrated facial evidence, it reports detection and orientation as UNVERIFIED instead of inventing a camera or anatomical ground truth.

No source character geometry was edited.

## Same-code execution results

| Model | GLB inspection | Head metadata | Camera/orientation | 2D landmarks | Surface attachments | Deterministic attachments | Result |
|---|---|---|---|---:|---:|---:|---|
| Original Tripo generated-rigged | PASS | candidate metadata found | calibrated evidence supplied | 478 | 476 valid | 29 of 30 selected | UNVERIFIED anatomical review |
| Existing Avaturn demo | PASS | candidate metadata found | UNVERIFIED, no calibrated render evidence | 0 | not measured | not measured | UNVERIFIED |
| Existing brunette demo | PASS | candidate metadata found | UNVERIFIED, no calibrated render evidence | 0 | not measured | not measured | UNVERIFIED |

The Avaturn and brunette runs used the same command and source code. Their GLBs were inspected successfully, but the repository did not contain independently calibrated frontal renders and model-specific 2D detector output for those assets. A GLB-only geometric hit test cannot establish anatomical landmarks, so those stages remain UNVERIFIED.

## Original Tripo regression

The original Tripo focused evidence remains unchanged in meaning:

- 478 MediaPipe points detected.
- 476 valid front-facing surface hits in the full audit.
- 30 selected anatomical anchors reviewed.
- 29 selected anchors have deterministic triangle and barycentric attachments.
- 1 selected anchor remains unresolved: `jawline_left`, MediaPipe index 397.
- 0 anchors independently validated by a second reviewer.
- 0 geometry corrections were made. The yellow outliers are provisionally accepted only where the surface audit succeeds; they are not claimed as independently validated.

The high-error manual-reference outliers remain classified as provisional reference-precision issues, not silently corrected detector points. They include eyelid contours, lower nose bridge, and lip contour anchors. The exact per-point errors remain in `goal1-independent-validation-report.json`.

## Reusable attachment format

`verification/goal1-tripo-landmark-evidence/goal1-tripo-deterministic-landmark-manifest.json` records, per selected anchor:

- standardized anatomical name and MediaPipe index
- original mesh identifier
- triangle index and triangle vertex indices
- barycentric coordinates
- local and world 3D position
- camera projection coordinates
- surface normal and frontal/oblique visibility
- reconstruction residual
- confidence, status, and cause classification

The attachment is recomputed from the original GLB POSITION accessor after converting the GLB coordinate frame into the evaluated Blender frame. The original GLB is read-only.

## Evidence and outputs

- Tripo onboarding report: `verification/goal1-onboarding/tripo/goal1-onboarding-report.json`
- Avaturn onboarding report: `verification/goal1-onboarding/avaturn/goal1-onboarding-report.json`
- Brunette onboarding report: `verification/goal1-onboarding/brunette/goal1-onboarding-report.json`
- Tripo attachment manifest: `verification/goal1-tripo-landmark-evidence/goal1-tripo-deterministic-landmark-manifest.json`
- Frontal anchors: `verification/goal1-tripo-landmark-evidence/goal1-final-30-mesh-attached-anchors-frontal.png`
- Mouth close-up: `verification/goal1-tripo-landmark-evidence/goal1-final-mouth-anchors-closeup.png`
- Eyelid close-up: `verification/goal1-tripo-landmark-evidence/goal1-final-eyelid-anchors-closeup.png`
- Oblique anchors: `verification/goal1-tripo-landmark-evidence/goal1-final-30-mesh-attached-anchors-oblique.png`
- Comparison: `verification/goal1-tripo-landmark-evidence/goal1-final-30-detected-vs-reference-color-coded.png`

## Acceptance

Cross-model execution passes only for the GLB inspection and reusable command execution. Full cross-model anatomical accuracy is UNVERIFIED because calibrated render inputs and independent references are missing for the two additional models. This work stopped at Goal 1; no Avaturn-to-Tripo registration or facial motion transfer was started.

**Original Tripo regression: PASS for execution, UNVERIFIED for independent anatomy**

**Cross-model execution: PASS for onboarding inspection, UNVERIFIED for landmark localization**

**Anatomical accuracy: UNVERIFIED**

**Deterministic 3D attachment: PASS for 29 selected Tripo anchors, UNVERIFIED across models**
