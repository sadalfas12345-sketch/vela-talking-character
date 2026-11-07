# Why the Male Landmark-105 Surface Folds Earlier

This geometry audit kept the ARAP solver, barycentric attachment, fixed boundary, neutral mesh, and stored expression trajectory unchanged.

## Local displacement comparison

| Measurement | Female | Male |
|---|---:|---:|
| Peak landmark-105 displacement | 0.0015239043 | 0.0081797315 |
| Interocular width | 0.0558428858 | 0.2997431104 |
| Displacement / eye width | 0.02729 | 0.02729 |
| Average edge length within 5 hops | 0.000642134 | 0.001487712 |
| Minimum edge length within 5 hops | 0.000118750 | 0.000307417 |
| Displacement / average local edge | 2.3732 | 5.4982 |
| Displacement / minimum local edge | 12.8328 | 26.6079 |
| Five-hop region diameter | 0.00765806 | 0.02024808 |
| Displacement / region diameter | 0.1990 | 0.4040 |
| Landmark to fixed boundary | 0.00628419 | 0.01277703 |
| Boundary distance / eye width | 0.11253 | 0.04263 |
| Five-hop vertices / edges | 129 / 349 | 121 / 325 |

The source-normalized motion is identical at 0.02729 eye widths. The male target is 2.32 times larger relative to average local edge length and 2.03 times larger relative to local-region diameter. The male landmark is also proportionally closer to the fixed boundary.

The attachment triangle itself is not smaller in the male. Female attachment edges are 0.000794442, 0.001075107, 0.000535167 with area 2.040602e-7. Male edges are 0.001032536, 0.002262379, 0.001319897 with area 3.616628e-7.

## First-fold inspection

Female triangle 7761, original vertices 435201, 433401, 433077, folds at 83%. Its area changes from 1.441955e-7 to 1.563186e-7. The normal crosses edge-on from +0.010616 at 82% to -0.003035 at 83%. One edge-sharing neighbor changes from neutral normal dot +0.76867 to -0.41027, confirming a local fold rather than coherent rotation.

Male triangles 31087 and 31321 fold at 25%. Triangle 31087 uses original vertices 940970, 813988, 301183 and its area changes from 4.675438e-7 to 4.203137e-7. Triangle 31321 uses original vertices 940970, 748962, 813988 and its area changes from 3.754591e-7 to 2.933034e-7. Neighbor normal dots change from positive neutral values to -0.99413 for triangle 31087 and -0.13682 for triangle 31321. Their areas remain positive, so this is a fold relative to neighboring surface triangles, not simple collapse.

## Controlled hypothesis test

The strongest hypothesis was excessive target displacement relative to male local edge scale. A temporary male-only diagnostic target at 25% was scaled by 0.4316304 so its displacement/average-local-edge ratio matched the female ratio. This did not modify the stored trajectory or source assets.

- Original male target at 25%: [0.000681172, 0.000945010, -0.001680654]
- Temporary ratio-matched target: [0.000294015, 0.000407895, -0.000725421]
- Original target: 2 folds
- Ratio-matched target: 0 folds

This supports the local-displacement-scale hypothesis. It does not make amplitude reduction an acceptable production fix; the original target remains unchanged and still fails.

## Evidence

- Machine-readable audit: `verification/goal2-experiment5/early-fold-audit/landmark105-male-early-fold-audit.json`
- Female close-up: `verification/goal2-experiment5/landmark105-intensity/female-first-fold-closeup.png`
- Male close-up: `verification/goal2-experiment5/landmark105-intensity/male-first-fold-closeup.png`
- Prior intensity sweep: `verification/goal2-experiment5/landmark105-intensity/landmark105-intensity-sweep.json`

Reproducible script: `scripts/diagnose_goal2_landmark105_male_early_fold.py`
