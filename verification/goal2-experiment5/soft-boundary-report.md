# Experiment 5: Soft Boundary Constraint Test

The existing official libigl ARAP bridge, exact landmark-105 barycentric constraint, original patches, and original target were kept unchanged. Only the outer-boundary treatment changed.

Soft mode adds `0.5 * lambda * sum(||U_boundary - V0_boundary||^2)` to the ARAP position update. Lambda is normalized from the geometry as a multiplier of the median nonzero diagonal of `-igl.cotmatrix(V,F)`. Tested multipliers: 100, 10, and 1. Three automatically selected neutral boundary gauge vertices are retained only to remove ARAP rigid null modes; all other boundary vertices are penalized rather than hard-fixed. The same method and factors were used on both models.

Input patches: female 8,689 vertices and 16,728 triangles; male 24,126 vertices and 47,155 triangles.

## Results

| Boundary configuration | Female folds | Male folds | Female landmark error | Male landmark error | Female max strain | Male max strain | Female boundary motion | Male boundary motion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rigid | 2 | 41 | 1.48e-11% | 1.66e-12% | 39.309% | 71.289% | 0% | 0% |
| Strong soft, 100x scale | 2 | 41 | 2.28e-12% | 3.90e-12% | 39.307% | 71.285% | 0.000249% | 0.000160% |
| Medium soft, 10x scale | 2 | 41 | 1.46e-11% | 7.26e-12% | 39.290% | 71.253% | 0.002457% | 0.001592% |
| Weak soft, 1x scale | 2 | 42 | 2.92e-11% | 2.17e-12% | 39.133% | 70.937% | 0.021949% | 0.014976% |

The landmark error is normalized by requested landmark displacement. Boundary motion is normalized by interocular width. The exact raw measurements and inverted triangle IDs are in `soft-boundary/soft-boundary-report.json`.

## Scale and target measurements

| Model | Interocular width | Requested displacement magnitude | Stiffness scale |
|---|---:|---:|---:|
| Female | 0.0558428858 | 0.0015239043 | 4.36932959 |
| Male | 0.2997431104 | 0.0081797315 | 5.28296955 |

## Findings

- All configurations reached the exact barycentric target numerically. This confirms the constraint path is active, not that the surface deformation is valid.
- Female rigid has 2 new inverted triangles, IDs 7760 and 7761. Every soft stiffness retains the same two.
- Male rigid has 41 new inverted triangles. Strong and medium soft retain the same 41; weak soft increases the count to 42.
- Softening reduces maximum strain only marginally. The 95th-percentile strain remains approximately 0.71% female and 0.65% male.
- Boundary motion is extremely small relative to eye width, even at weak stiffness. It does not provide a useful smooth transition or remove the localized fold.

## Decision

No tested boundary stiffness satisfies full target motion, zero genuine folds or collapses, lower maximum strain without a new concentration, and a valid smooth boundary transition. The soft-boundary experiment FAILED. The evidence points to local incompatibility between landmark-105 motion and the existing patch deformation, not boundary rigidity alone.

Reproducible script: `scripts/run_goal2_experiment5_soft_boundary.py`

Evidence JSON: `verification/goal2-experiment5/soft-boundary/soft-boundary-report.json`
