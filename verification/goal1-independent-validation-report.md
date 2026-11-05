# Goal 1: Tripo landmark detection and independent validation

## Scope

This report covers landmark detection and 3D localization on the original Tripo mesh only. No Avaturn registration, expression transfer, solver change, topology edit, teeth, or speech work was started.

## Method

- Detector: MediaPipe Face Landmarker, official 478-point model.
- Mesh: preserved `assets/tripo/vela-photoreal/generated-rigged.glb`.
- Frontal validation used the exact calibrated Blender render camera and evaluated GLB transforms.
- 3D points were accepted only after first-visible-surface raycast, front-facing normal check, anatomical-region check, and oblique-view review.
- A 30-point reference set was manually selected from the untouched high-resolution Tripo frontal render before reading detector coordinates. The reference positions were not copied from MediaPipe, ray hits, or donor geometry.
- The reference set is assistant-selected and has not been independently reviewed by a second human reviewer. Therefore it is evidence for review, not ground truth.

## Independent 30-point comparison

| Measurement | Result |
|---|---:|
| Selected landmarks | 30 |
| Interocular distance | 286.002 px |
| Median detector-to-reference error | 1.045 px |
| P95 detector-to-reference error | 22.797 px |
| Median error / interocular distance | 0.003654 |
| P95 error / interocular distance | 0.079710 |
| Within stated manual uncertainty | 18 / 30 |
| Front-surface localizations | 29 / 30 |
| Unresolved localizations | 1 / 30 |
| Oblique-view visible | 26 / 30 |
| Oblique-view occluded or ambiguous | 3 / 30 |

The largest discrepancies were in the lower nose bridge, eyelid contour points, and lip boundary contour points. These are exactly the regions where a detector point can be visually plausible in 2D while still being anatomically imprecise. The left jawline landmark remains unresolved in the full detector report at index 397. No selected point was classified as an incorrect anatomical region or ambiguous normal in the 30-point comparison.

## 3D localization

The full 478-point surface audit recorded 477 frontal surface hits, 476 valid front-surface hits, one ambiguous normal, and one unresolved landmark. The unresolved landmark is index 397, `jawline_left`. Index 435 has a tangent normal and remains ambiguous in the full audit. In the second oblique view, 431 points were visible first-surface hits and 46 were occluded or ambiguous.

The reprojection residual was effectively zero, but that is only a projection self-consistency check and is not anatomical ground truth. The independent 30-point review therefore remains unverified.

## Evidence

- [Original Tripo without landmarks](goal1-tripo-landmark-evidence/A_original_tripo_without_landmarks.png)
- [30 numbered reference points](goal1-tripo-landmark-evidence/goal1-30-numbered-independent-reference-points.png)
- [Detected versus reference error vectors](goal1-tripo-landmark-evidence/goal1-30-detected-vs-reference-error-vectors.png)
- [Lips close-up](goal1-tripo-landmark-evidence/goal1-30-lips-closeup-reference-vs-detected.png)
- [Eyelids close-up](goal1-tripo-landmark-evidence/goal1-30-eyelids-closeup-reference-vs-detected.png)
- [Oblique 3D landmarks](goal1-tripo-landmark-evidence/E_original_tripo_projected_landmarks_oblique.png)
- [Side-view landmarks](goal1-tripo-landmark-evidence/F_original_tripo_projected_landmarks_side.png)
- [Machine-readable results](goal1-tripo-landmark-evidence/goal1-independent-validation-report.json)

Drive copies:

- [Numbered points](https://drive.google.com/file/d/1xp-4W-VBUp5OHcUHnc4mn0JYrfVyQzNw/view)
- [Lips](https://drive.google.com/file/d/1bpPRJ2tJ-lgptgcyNFF_R-DHxhqJ57KR/view)
- [Eyelids](https://drive.google.com/file/d/1SkC_ntG1CwaELkUcYvrl-jgo4wkrb8gj/view)
- [Error vectors](https://drive.google.com/file/d/1Ig00HSlZz4ZmtM4ZpbNcZZco5PMfz0Gi/view)
- [Oblique view](https://drive.google.com/file/d/1QzMbV39dzKKfyq40bQmKw5aGbH4Fz0sz/view)
- [Validation JSON](https://drive.google.com/file/d/1c9PzD15maQNdxMOd7P2PAondGHoC05zH/view)

## Determination

2D detection is visually plausible and reproducible, but precise anatomical accuracy is not proven. Lips, eyelid contours, and jawline require independent human-reviewed references before use for registration. No automatic ground truth was manufactured.

**2D anatomical detection: UNVERIFIED**
**3D surface localization: UNVERIFIED**
**Independent reference validation: UNVERIFIED**
