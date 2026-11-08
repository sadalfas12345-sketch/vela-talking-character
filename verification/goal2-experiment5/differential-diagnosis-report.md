# Experiment 5: Differential Diagnosis of Landmark 105 Folding

The diagnosis reused the isolated landmark-105 component, original target, exact barycentric bridge, and existing fold measurements. No production solver or mesh was changed.

## Hypothesis matrix

| Hypothesis | Female evidence | Male evidence | Classification |
|---|---|---|---|
| H1 Excessive tangential movement | Movement/local-edge ratio 2.373; fold at 83% | Ratio 5.498; fold at 25%; ratio-matched temporary target removed folds at 25% | INCONCLUSIVE for tangential-only cause; SUPPORTED for excessive target magnitude relative to local geometry |
| H2 Incorrect 3D direction | Monocular video does not establish depth | Same limitation; target contains a measurable normal component | INCONCLUSIVE |
| H3 Poor local triangle geometry | Folded neighbor relationship and local aspect data | P95 local aspect 3.601 versus female 2.742 | INCONCLUSIVE; conditioning was not independently tested |
| H4 ARAP concentration | 39.309% maximum strain versus 0.710% P95 | 71.289% maximum versus 0.648% P95 | SUPPORTED as an observed deformation mechanism |
| H5 Barycentric constraint defect | Real residual numerical-zero | Real residual numerical-zero | REJECTED |
| H6 Nearby stationary constraints | Boundary softening did not remove folds | Boundary distance is only 0.04263 eye widths, but no single-anchor ablation | INCONCLUSIVE |
| H7 Wrong anatomical attachment | Existing visual audit found plausible placement | Existing visual audit found plausible placement | INCONCLUSIVE; independent anatomical ground truth is absent |

## H5 controlled test

A synthetic 3x3 surface used the same one-row barycentric equality representation. The constraint matrix rank was 1, residual was `1.57e-16`, and a free vertex moved by `0.360555`. This confirms the adapter imposes one positional landmark constraint without accidentally prescribing the three triangle vertices.

## Strongest evidence

The male movement is 5.498 times its average local edge length, versus 2.373 for the female. A temporary male target scaled by `0.4316304` to match the female displacement/local-edge ratio changed the male 25% result from 2 folds to 0. This is the only controlled test that changed the outcome, and it supports local displacement magnitude relative to mesh resolution as the strongest surviving mechanism.

The peak strain distribution also shows concentration: a small number of edges carry 39.309% female and 71.289% male maximum strain while the P95 values are below 1%. That is consistent with a local ARAP deformation concentration, but it does not by itself prove that ARAP is the only cause.

## Final diagnosis

PRIMARY CAUSE: Excessive target displacement relative to the local connected mesh scale, producing concentrated ARAP strain around landmark 105.

SECONDARY CONTRIBUTORS: Male local triangle-quality variation and closer normalized proximity to fixed boundary constraints. The male boundary distance is 0.04263 eye widths versus 0.11253 female.

REJECTED HYPOTHESES: A defective barycentric constraint representation and the unrelated disconnected component.

REMAINING UNCERTAINTIES: Tangential-only versus normal-only causality, independent triangle conditioning, the exact contribution of individual fixed vertices, and whether a valid full-target deformation exists under another established energy.

RECOMMENDED NEXT INTERVENTION: Run one controlled, model-agnostic local surface-conditioning test around the first folding triangles while preserving the original target and attachment, or test an established ARAP alternative on the same isolated component. Do not attenuate the production target based only on the ratio-matched diagnostic.

FALSIFICATION TEST: If a geometry-conditioned or alternative-energy solve with the unchanged full target still folds at the same intensities and locations, the local-scale/concentration explanation is insufficient and the target direction or attachment must be reconsidered.

Evidence:

- `verification/goal2-experiment5/differential/differential-diagnosis.json`
- `verification/goal2-experiment5/early-fold-audit/landmark105-male-early-fold-audit.json`
- `verification/goal2-experiment5/isolated-component/isolated-component-report.json`
- `verification/goal2-experiment5/landmark105-intensity/landmark105-intensity-sweep.json`
- Script: `scripts/run_goal2_experiment5_differential_diagnosis.py`
