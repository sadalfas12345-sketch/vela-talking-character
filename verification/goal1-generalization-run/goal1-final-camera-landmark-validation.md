# Goal 1 final camera and landmark validation

## Camera refinement

The original 32-view search was retained. Refinement used the accepted 3D
attachments for left and right eye corners, nose tip, and chin to estimate a
model-derived facial frame. No world-axis or per-character camera coordinates
were added.

| Model | Original yaw | Original pitch | Original roll | Refined frame | Refined MediaPipe score |
|---|---:|---:|---:|---|---:|
| Female | 48.84° | -46.67° | 26.72° | 3D facial-frame target, Blender calibrated look-at render | 0.824 |
| Male | -8.58° | -35.84° | -7.37° | 3D facial-frame target, Blender calibrated look-at render | 0.939 |

The original female camera was measurably elevated and oblique. The refined
female render is centered on the facial landmarks but still has a residual
model-pose limitation visible in the face tilt. The male refinement is close to
frontal by the image symmetry metrics. The reported zero after-refinement
angles are target-frame angles, not an independent human judgment of visual
frontalism.

## Corrected-camera geometric results

| Model | Detected | First-visible hits | Valid front hits | Ambiguous | Unresolved |
|---|---:|---:|---:|---:|---:|
| Female | 478 | 478 | 478 | 0 | 0 |
| Male | 478 | 478 | 474 | 4 | 0 |

The male ambiguous points are retained in the corrected raycast report. They
are not converted into anatomical correctness.

## Reference contamination and blind workflow

The previous provisional reference coordinates were suspiciously close to
rounded detector coordinates. They are not used as independent evidence and
their scores are invalidated for certification.

Clean, unlabeled renders were placed in:

- `verification/goal1-generalization-run/blind-reference/female/clean-neutral.png`
- `verification/goal1-generalization-run/blind-reference/male/clean-neutral.png`

No independent human annotator was available during this run. Therefore no
blind reference coordinates were entered, and no certified 2D anatomical score
is claimed. The clean images are ready for external annotation without
detector overlays.

## Accuracy status

The earlier provisional scores, female 93.33/100 and male 91.67/100, remain
historical only. They were based on contaminated-risk, single-reviewer
coordinates and must not be used to authorize registration.

Critical unresolved issues:

- Female residual pitch and roll are not independently accepted as minimal.
- Male upper-lip vermilion boundaries are obscured by moustache and beard.
- Cheek and face-outline errors remain visible in the prior comparison and are
  not hidden by the weighted rubric.
- Independent human reference validation is pending.

Technical conclusion: automatic camera discovery, corrected-camera rendering,
MediaPipe detection, and deterministic first-visible attachments work on both
models. Anatomical certification does not.

No expression transfer, topology change, mouth reconstruction, teeth, or speech
work was performed.
