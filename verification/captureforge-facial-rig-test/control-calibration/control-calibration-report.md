# CaptureForge 26-bone facial rig calibration

Branch: `wip/tripo-face-repair`  
Baseline: `0ca2e8d`  
Status: diagnostic complete; no rig, weight, pivot, or source GLB was modified.

## Scope and inputs

The calibration used the original Tripo meshes and the existing CaptureForge rig builder and weight generator. Goal 1 barycentric attachments were rebuilt against the exact original meshes only for measurement. All 478 attached Goal 1 landmarks were measured in the response map. The 121-frame, head-stabilized motion table was reused without re-tracking or changing targets.

The local response experiment measured 26 bones, each with translation and rotation on all three local axes: 156 DOFs per character. Small probes were ±0.001 interocular width for translation and ±0.01 radians for rotation. Larger positive probes were 0.01 interocular width and 0.10 radians. The response matrix was fitted with SciPy `lsq_linear`, bounded to ±0.05 interocular width for translation and ±0.25 radians for rotation, with ridge regularization `1e-3`.

## Reproducible commands

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/measure_captureforge_control_response.py
py scripts/fit_captureforge_control_map.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python scripts/validate_captureforge_control_fit.py
py scripts/build_captureforge_calibration_sheet.py
py scripts/build_captureforge_calibration_plot.py
```

## Response-map result

Both characters completed all 468 probe cases: 156 DOFs, with positive, negative, and larger positive measurements for every DOF. The saved `control-tests.json` files contain commanded and evaluated bone transforms, all 478 landmark responses, and local strain measurements.

The response is not uniformly useful. The strongest practical responses are global head and jaw movement. Brow controls produce measurable responses, but their response is much smaller than the observed eyebrow trajectory. The generated weight groups also show that some controls are effectively absent: `tongue.tip` has zero weighted vertices on both characters, and both male eye controls have only 31 vertices with the measured eye response effectively zero. These are measured limitations of the existing rig, not tuning decisions made in this experiment.

The complete per-bone response and weight counts are in:

- [female control definition](female/control-definition.json)
- [female response tests](female/control-tests.json)
- [female response matrix](female/response-map.npz)
- [male control definition](male/control-definition.json)
- [male response tests](male/control-tests.json)
- [male response matrix](male/response-map.npz)
- [response summary plot](control-response-summary.png)

## Fit and evaluated replay

The optimizer's linear prediction and Blender's evaluated surface response agree closely. This separates a fitting problem from a rig-capability problem: the optimizer is not predicting movement that Blender then loses. It is fitting the measured response map, and the evaluated mesh reproduces that limited response.

Mean displacement is normalized by each character's interocular width.

| Region | Female reference | Female predicted | Female actual | Female actual mean error | Male reference | Male predicted | Male actual | Male actual mean error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Eyebrows | 0.025855 | 0.006680 | 0.006676 | 0.024812 | 0.025855 | 0.012027 | 0.011981 | 0.023254 |
| Eyelids | 0.015076 | 0.006245 | 0.006238 | 0.014450 | 0.015076 | 0.009538 | 0.009435 | 0.013905 |
| Cheeks | 0.024858 | 0.007060 | 0.007058 | 0.023135 | 0.024858 | 0.012888 | 0.012762 | 0.022794 |
| Lips | 0.037107 | 0.009569 | 0.009575 | 0.030898 | 0.037107 | 0.020290 | 0.020077 | 0.020653 |
| Mouth corners | 0.025880 | 0.007741 | 0.007741 | 0.020824 | 0.025880 | 0.024395 | 0.024176 | 0.007763 |
| Jaw | 0.025007 | 0.014559 | 0.014559 | 0.017997 | 0.025007 | 0.021162 | 0.020918 | 0.017299 |

The 95th-percentile normalized landmark errors are saved in both `validation-report.json` files. Key values are:

- Female: eyebrows `0.042280`, eyelids `0.028040`, cheeks `0.050082`, lips `0.061394`, mouth corners `0.037972`, jaw `0.056838`.
- Male: eyebrows `0.038867`, eyelids `0.024535`, cheeks `0.045964`, lips `0.041193`, mouth corners `0.015375`, jaw `0.052632`.

Across all 478 landmarks and 121 frames, the actual-error median and P95 from `actual-frame-measurements.csv` were female `0.019047` and `0.054225`, and male `0.015924` and `0.043598`, in interocular units. Region medians were female eyebrows `0.024529`, eyelids `0.013559`, cheeks `0.021319`, lips `0.032530`, mouth corners `0.018599`, jaw `0.011573`; male eyebrows `0.023130`, eyelids `0.013265`, cheeks `0.021407`, lips `0.022288`, mouth corners `0.007374`, jaw `0.013641`.

The fitted control bounds were active on zero frames for both characters. That means the reported miss is not caused by the chosen transform limits being reached. It is the best fit under the measured response map and regularization.

## Geometry and evaluated surface

The validation replay used actual evaluated mesh coordinates and reconstructed every landmark from its original barycentric triangle. It sampled the face-region triangles at frames 0, 10, 20, through 120.

| Measure | Female | Male |
|---|---:|---:|
| Interocular width | 0.055842 | 0.299743 |
| Frames replayed | 121 | 121 |
| Evaluated DOFs | 156 | 156 |
| Mapped Goal 1 landmarks | 478 | 478 |
| Maximum sampled edge strain | 65.45% | 38.43% |
| Maximum sampled P95 edge strain | 7.42% | 4.49% |
| Minimum sampled area ratio | 0.8047 | 0.5539 |
| Collapsed triangles at 10% area threshold | 0 | 0 |
| Invalid coordinates | 0 | 0 |
| Blender replay runtime | 58.89 s | 44.71 s |

No production mesh was altered. The strain results do not establish absence of every possible self-intersection, but they do show that the evaluated replay had no invalid coordinates or sampled collapsed triangles. The high maximum strain means the fitted controls are not a visually safe production expression, even where the area check remains non-collapsed.

## Visual evidence

The actual textured Blender renders are available here:

### Female

- [Neutral](female/validation/neutral.png)
- [Brow inner up](female/validation/browInnerUp.png)
- [Eye blink left](female/validation/eyeBlinkLeft.png)
- [Jaw open](female/validation/jawOpen.png)
- [Mouth smile left](female/validation/mouthSmileLeft.png)

### Male

- [Neutral](male/validation/neutral.png)
- [Brow inner up](male/validation/browInnerUp.png)
- [Eye blink left](male/validation/eyeBlinkLeft.png)
- [Jaw open](male/validation/jawOpen.png)
- [Mouth smile left](male/validation/mouthSmileLeft.png)

- [Calibration contact sheet](calibration-expression-comparison.png)
- [Control response and motion plot](control-response-summary.png)

Direct inspection of the rendered neutral and expression images shows that the replay is stable but the brow raise is not visually convincing. The measured eyebrow displacement is correspondingly far below the reference trajectory. The renders do not justify calling the rig expression-ready.

## Plain-English conclusions

1. **What the controls actually move.** The head and jaw controls move the largest coherent regions. Eyelid, brow, cheek, lip, and mouth-corner controls affect their intended general areas, but with strongly different gains between the two imported meshes. `tongue.tip` has no effective skin weights. The male eye controls have effectively zero measured landmark response.

2. **How the combined controls reproduce the reference.** A bounded ridge least-squares fit was solved independently for each frame from the measured 26-bone response matrix. Blender replay reproduced the fitted prediction closely, but the fitted motion remained substantially smaller than the reference in brows, eyelids, cheeks, lips, and most other regions.

3. **What remains inaccurate or impossible with this rig.** The full eyebrow trajectory is not reachable with the existing measured controls without relying on broad head or jaw movement. Female brow movement reaches only `0.006676` versus `0.025855` interocular units. Male reaches `0.011981` versus `0.025855`. Lips and cheeks are also underrepresented, and the female evaluated replay reaches 65.45% maximum sampled edge strain.

4. **Whether control mapping alone is enough.** No. The response-map fit and Blender replay agree, while the target remains missed. Better coefficient mapping can select the available motion more consistently, but cannot create missing local eyebrow response.

5. **Smallest generalizable correction justified by the measurements.** Before changing weights, measure a second rig or control architecture with independently validated local brow and eyelid DOFs, then compare its response matrix against this baseline. If implementation work is authorized later, the smallest generalizable rig change is a broader, anatomically separated eyebrow/forehead control influence generated from landmarks and surface connectivity, validated on both meshes. This report does not implement that change.

## Final assessment

| Item | Female | Male |
|---|---|---|
| 26-bone response measurement | COMPLETE | COMPLETE |
| Reference fit and Blender replay | COMPLETE | COMPLETE |
| Full reference motion reproduced | FAIL | FAIL |
| Visual eyebrow deformation | FAIL | FAIL |
| Existing architecture sufficient | NO | NO |

The existing CaptureForge 26-bone architecture is useful as a measured baseline, but it is not sufficient for faithful reference-video facial motion on either original Tripo mesh. No rig modification was made in this calibration run.
