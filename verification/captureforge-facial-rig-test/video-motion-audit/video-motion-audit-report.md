# CaptureForge video-driven facial motion audit

Branch: `wip/tripo-face-repair`  
Method: temporary copies of the original Tripo GLBs with the existing CaptureForge 26-bone rig and existing skin weights. No source rig, weight, landmark, or GLB was modified.

## Inputs

- Reference coefficient archive: `verification/captureforge-facial-rig-test/worried-reference.capture.npz`
- Existing head-stabilized landmark motion: `verification/goal2-browInnerUp-proof/worried-expression-table.json`
- Female original: `assets/tripo/vela-photoreal/generated-original.glb`
- Male original: `assets/tripo/generalization-male-20261105/generated-original.glb`
- Goal 1 attachments: the existing female and male refined raycast reports

The coefficient archive contains 121 frames, 52 coefficient channels, and 478 tracked landmarks. The existing normalized motion table supplies the expected 2D face-relative displacement for IDs 0–467. Expected 3D positions were reconstructed per target as:

```text
expected = neutral_surface_point
         + dx_norm * target_eye_width * face_right
         + dy_norm * target_eye_width * anatomical_up
```

Actual positions were reconstructed from the original Goal 1 barycentric triangle attachments on the evaluated temporary mesh for every frame.

Command:

```text
blender -b --python scripts/audit_captureforge_video_motion.py
py scripts/build_captureforge_video_audit_sheet.py
```

The fixed audit command mapping uses existing named FaceForge bones, local pose-bone Euler X, and the previously used 0.25-radian command scale. It is recorded as an audit mapping, not a correction or production calibration. Head pose channels are not applied to the face rig; expected landmarks are already head-stabilized.

## Region results

Errors and magnitudes are normalized by each character's interocular width. `Response` is actual mean movement divided by expected mean movement.

### Female

| Region | Mean expected | Mean actual | Response | Mean error | P95 error |
|---|---:|---:|---:|---:|---:|
| Eyebrows | 0.025855 | 0.000375 | 1.45% | 0.025891 | 0.046210 |
| Eyelids | 0.015076 | 0.000329 | 2.18% | 0.015247 | 0.031402 |
| Cheeks | 0.024858 | 0.000362 | 1.46% | 0.024869 | 0.052503 |
| Lips | 0.037107 | 0.003915 | 10.55% | 0.039089 | 0.080808 |
| Mouth corners | 0.025880 | 0.001272 | 4.92% | 0.026424 | 0.048729 |
| Jaw | 0.025007 | 0.009925 | 39.69% | 0.029372 | 0.074770 |

Eye width: `0.0558418473` model units. 478 Goal 1 points were mapped, with median surface distance `3.401e-7`. The temporary rig contained 26 bones. Neutral attachment reconstruction error was `5.59e-9` model units.

Peak frame 99 commands included `brow.mid.L = 0.178980 rad`, `brow.mid.R = 0.179070 rad`, and `jaw = 0.075142 rad`; the corresponding bone transforms were evaluated. Sampled geometry checks found maximum edge strain `138.77%`, minimum area ratio `0.2194`, zero triangles below the 10% area-collapse threshold, and no invalid coordinates. The high localized strain is a geometric defect even though the collapse counter is zero.

### Male

| Region | Mean expected | Mean actual | Response | Mean error | P95 error |
|---|---:|---:|---:|---:|---:|
| Eyebrows | 0.025855 | 0.000220 | 0.85% | 0.025864 | 0.046290 |
| Eyelids | 0.015076 | 0.000306 | 2.03% | 0.015157 | 0.031241 |
| Cheeks | 0.024858 | 0.000113 | 0.45% | 0.024864 | 0.052489 |
| Lips | 0.037107 | 0.004616 | 12.44% | 0.039419 | 0.082381 |
| Mouth corners | 0.025880 | 0.002724 | 10.53% | 0.027259 | 0.049757 |
| Jaw | 0.025007 | 0.009955 | 39.81% | 0.030277 | 0.078748 |

Eye width: `0.299743168` model units. 478 Goal 1 points were mapped, with median surface distance `1.560e-7`. The temporary rig contained 26 bones. Neutral attachment reconstruction error was `4.68e-8` model units.

Peak commands were identical because the same source coefficients were used. Sampled geometry checks found maximum edge strain `25.22%`, minimum area ratio `0.7462`, zero triangles below the 10% area-collapse threshold, and no invalid coordinates.

## Where movement is lost

| Stage | Evidence | Finding |
|---|---|---|
| Video tracking and coefficient extraction | 121 valid frames and 52 coefficient channels in the existing capture archive | No loss established here |
| Coefficient-to-command mapping | Nonzero commands and evaluated pose transforms, including approximately 0.179 rad brow-mid commands at peak | Commands reach the rig; no loss at command assignment or modifier evaluation |
| Bone-to-surface response | Eyebrow response is only 1.45% female and 0.85% male; eyelids and cheeks are about 0.5–2.2% | Confirmed loss occurs between bone transforms and anatomical surface motion |
| Weight coverage and control geometry | Brow groups exist, but their influence is localized. Earlier controlled evidence measured landmark-105 brow-mid weights above 0.94 while rotation about a pivot at the landmark produced almost no landmark translation | Localized weights plus control pivots are the primary demonstrated bottleneck |
| Control sufficiency | The 26-bone rig has one small control family per region and no calibrated mapping from each coefficient to a surface trajectory | Secondary limitation; detailed video motion cannot be reproduced by the current coarse controls |

The prior controlled landmark-105 audit remains relevant: `brow.mid.R` was correctly weighted at its attachment, but its pivot was at the landmark, so rotation moved surrounding vertices while producing almost no landmark translation. This video audit reproduces the same category of loss at sequence scale. It does not prove that every region has the same single cause; per-bone isolation would be the next diagnostic if requested.

## Visual inspection

The actual textured neutral and peak renders were inspected. The female peak shows localized lower-face deformation and no convincing eyebrow raise. The male peak remains close to neutral, with no clearly visible eyebrow raise. Neither render pair shows a gross detached mesh or invalid-coordinate artifact, but the female strain statistics indicate severe localized deformation that is not acceptable as facial performance.

Comparison sheet:

- [Reference and Tripo neutral/peak comparison](reference-and-tripo-comparison.png)
- [Female neutral](female/neutral.png) and [female peak](female/peak.png)
- [Male neutral](male/neutral.png) and [male peak](male/peak.png)
- [Reference neutral overlay](../../goal2-browInnerUp-proof/step1/neutral-468-overlay.png) and [reference peak overlay](../../goal2-browInnerUp-proof/step1/peak-468-overlay.png)

Machine-readable evidence:

- [Female result](female/result.json)
- [Male result](male/result.json)
- [Female per-frame landmark measurements](female/landmark-frame-measurements.csv)
- [Male per-frame landmark measurements](male/landmark-frame-measurements.csv)
- [Female bone commands](female/bone-commands.json)
- [Male bone commands](male/bone-commands.json)
- [Female skin weights](female/skin-weights.json)
- [Male skin weights](male/skin-weights.json)

## Recommendation

Do not change the landmarks or source motion. The smallest evidence-based next diagnostic is to isolate one existing control per region and measure pivot translation versus rotation and attachment-triangle response on both characters. That will separate pivot placement from influence spread before any generalized weighting correction is attempted.

No correction was implemented in this audit.

VIDEO-TO-CONTROL MAPPING: **SOURCE VERIFIED; PRODUCTION MAPPING NOT CALIBRATED**  
FACIAL RIG RESPONSE: **FAIL**  
FEMALE: **FAIL**  
MALE: **FAIL**  
OVERALL STEP RESULT: **FAILED**
