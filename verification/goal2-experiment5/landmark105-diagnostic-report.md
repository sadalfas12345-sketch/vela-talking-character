# Experiment 5: landmark 105 diagnostic

Commit baseline: `c8b3ef64c4ade26df49a76b92d831dba9dab2f9f`

The test uses the existing 128-hop patches, the existing Goal-1 attachments, the existing video-derived targets, and exact native libigl ARAP barycentric constraints. No attachment, target, solver, or patch was changed.

Command:

```powershell
$env:PYTHONPATH='C:\Users\USER\.codex\tripo-libigl-bridge'
python scripts/diagnose_goal2_experiment5_landmark105.py --female-patch verification/goal2-experiment5/female-128-union.patch.npz --male-patch verification/goal2-experiment5/male-128-union.patch.npz --female-goal verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json --male-goal verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json --female-markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json --male-markers verification/goal2-browInnerUp-proof/step4-tripo-transfer/male/landmark_markers.json --output verification/goal2-experiment5/landmark105-diagnostic
```

Machine-readable full output:

`verification/goal2-experiment5/landmark105-diagnostic/landmark105-diagnostic.json`

## Landmark 105 attachment and motion

| Model | Original triangle vertex IDs | Barycentric weights | Neutral attachment | Requested vector | Magnitude / eye width |
|---|---|---|---|---|---:|
| Female | 434514, 434274, 433401 | 0.187655, 0.579835, 0.232511 | [0.060146, -0.019990, 0.906154] | [0.000158, 0.000694, -0.001348] | 2.729% |
| Male | 301183, 813988, 906120 | 0.388966, 0.364081, 0.246954 | [0.259169, -0.143653, 0.182218] | [0.002724, 0.003780, -0.006723] | 2.729% |

The normalized displacement is identical across models. The female attachment triangle has area `2.0406e-7` and edge lengths `0.000794, 0.001075, 0.000535`. The male attachment triangle has area `3.6166e-7` and edge lengths `0.001033, 0.002262, 0.001320`; it is a relatively low-area, narrow local triangle compared with its edge lengths. The full IDs and adjacent landmarks 63 and 70 are in the JSON manifest.

## Controlled cases

Case B uses landmark 70's existing target vector on landmark 105. Case C uses landmark 105's existing target vector on landmark 70. These diagnostic vectors are not written back to the expression dataset.

| Test | Female folds | Male folds | Female max strain | Male max strain | Female landmark error | Male landmark error |
|---|---:|---:|---:|---:|---:|---:|
| A: 105 real movement | 2 | 41 | 39.309% | 71.289% | <1e-10% | <1e-10% |
| B: 105 uses 70 vector | 0 | 13 | 27.727% | 42.913% | <1e-10% | <1e-10% |
| C: 70 uses 105 vector | 0 | 8 | 32.592% | 37.851% | <1e-10% | <1e-10% |

All three cases reached their exact barycentric targets numerically. The full damaged-triangle inventories include original vertex IDs, neutral/deformed areas, edge lengths, distances to landmark and boundary, and vertex movement.

## Interpretation

Female case A fails while B passes, which implicates the real landmark-105 vector, not merely the existence of a second control.

Male cases A and B both fail, while C also fails with fewer folds. This means the male result cannot be attributed uniquely to the 105 vector alone. The male local surface and stationary-boundary constraints are also implicated. The narrow 105 attachment triangle and the large local edge strain support that interpretation, but do not prove that the anatomical attachment is wrong.

The neutral landmark and attachment triangle are on the same visible local surface in the diagnostic views. The rendered diagnostic inspection found no evidence that 105 is attached to hair, an eye, or a remote facial region. Under the available evidence, the attachment is anatomically plausible but deformation-incompatible at this target and patch boundary.

Diagnostic images:

- `landmark105-diagnostic/female-case-A-landmark-105.png`
- `landmark105-diagnostic/male-case-A-landmark-105.png`
- `landmark105-diagnostic/female-case-B-landmark-105.png`
- `landmark105-diagnostic/male-case-B-landmark-105.png`
- `landmark105-diagnostic/female-case-C-landmark-70.png`
- `landmark105-diagnostic/male-case-C-landmark-70.png`

No correction was attempted. No additional patch sweep, landmarks, GLB export, or Experiment 6 work was performed.

LANDMARK 105 ATTACHMENT: PLAUSIBLE

PRIMARY FAILURE MECHANISM: the real landmark-105 displacement creates excessive local strain and folding under the existing constrained surface and stationary boundary; the male also has a more fragile local attachment triangle and remains damaged even with the landmark-70 diagnostic vector.

DIAGNOSTIC RESULT: COMPLETE

EXPERIMENT 5 DEFORMATION: STILL FAILED

