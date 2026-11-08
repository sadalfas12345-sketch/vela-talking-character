# CaptureForge facial rig construction correction

Baseline: `9b379b4`  
Branch: `wip/tripo-face-repair`

## What was changed

The existing CaptureForge construction was inspected before changing the test rig:

1. Brow bone tails were built with world-space `UP = (0, 0, 1)`, not an anatomical face frame.
2. Skin weights used isotropic Euclidean distance to each anchor, allowing influence across unrelated mesh surfaces when they shared an object.
3. A nearest-vertex fallback could create a local influence even when the intended falloff did not reach the surface.
4. Jaw gating used a world-axis split and had to remain bounded by the existing face-window rule.

The correction tested one shared construction method:

- derive right, front, and up axes from both eye centers and the top-to-chin direction;
- orient brow bone tails along that derived anatomical up axis;
- gate each anchored influence to the connected mesh component containing its surface seed;
- use an anisotropic face-frame falloff for the connected surface;
- preserve the original bounded jaw face-window gate.

The 26-bone architecture, bone names, original meshes, Goal 1 attachments, and video motion were unchanged. No hand-painted or character-specific weights were used.

## Commands

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/run_captureforge_rig_correction_measurement.py
py scripts/fit_captureforge_rig_correction.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/validate_captureforge_rig_correction.py
py scripts/build_captureforge_rig_correction_sheet.py
```

## Eyebrow gate

| Metric | Female baseline | Female corrected | Male baseline | Male corrected |
|---|---:|---:|---:|---:|
| Reference eyebrow movement / eye width | 0.025855 | 0.025855 | 0.025855 | 0.025855 |
| Actual eyebrow movement / eye width | 0.006676 | 0.006619 | 0.011981 | 0.011859 |
| Mean eyebrow error / eye width | 0.024812 | 0.024711 | 0.023254 | 0.023030 |
| P95 eyebrow error / eye width | 0.042280 | 0.042067 | 0.038867 | 0.038255 |
| Max edge strain | 65.45% | 66.06% | 38.43% | 62.65% |
| P95 edge strain maximum | 7.42% | 7.60% | 4.49% | 2.99% |
| Minimum sampled area ratio | 0.8047 | 0.8083 | 0.5539 | 0.3776 |
| Collapsed triangles sampled | 0 | 0 | 0 | 0 |

The corrected fit remains far below the reference brow motion on both models. Female actual movement changed by -0.9%; male changed by -1.0%. The correction therefore did not solve the demonstrated insufficient brow response.

## Visual result

Actual textured renders were inspected, not only marker or bone movement. The eyebrow remains visually almost stationary in both corrected renders. The comparison sheet shows that the corrected brow frame and connected-surface weighting do not produce a convincing eyebrow raise.

- [Baseline versus corrected comparison](baseline-versus-corrected.png)
- [Female corrected brow render](female/validation/browInnerUp.png)
- [Male corrected brow render](male/validation/browInnerUp.png)
- [Female corrected neutral](female/validation/neutral.png)
- [Male corrected neutral](male/validation/neutral.png)

## Interpretation

The construction audit found real defects, but fixing the face frame and connectivity gate did not materially increase eyebrow response. This rejects the hypothesis that world-Z orientation or unrestricted component leakage alone explains the under-reach.

The remaining limitation is structural: the existing 26 controls and their generated deformation response do not provide enough independent, correctly directed brow/forehead motion. A better control mapping cannot create that missing response. The female also remains near the baseline high-strain regime; the male has a lower P95 but a worse minimum area ratio after correction.

Because the eyebrow gate failed on both characters, eyelid and mouth results are not accepted as generalization evidence. They were replayed only as part of the same diagnostic frame sequence. No independent facial-control generalization pass was started.

## Final assessment

FEMALE: FAIL  
MALE: FAIL  
GENERALIZATION: NOT TESTED  
OVERALL STEP RESULT: FAILED
