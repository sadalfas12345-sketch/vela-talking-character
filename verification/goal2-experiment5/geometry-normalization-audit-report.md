# Landmark 105 Geometry and Normalization Audit

This audit did not modify Goal 1, the stored trajectory, the original mesh, or the ARAP formulation. The full 100-iteration run was bounded because the male patch required excessive runtime. A second run using the same ARAP bridge with a 20-iteration diagnostic cap was also stopped before completion. Therefore normalization and directional ARAP comparisons are not claimed complete.

## Measured geometry

| Measurement | Female | Male |
|---|---:|---:|
| Patch connected components | 2 | 2 |
| Component containing landmark 105 | 4,349 vertices | 8,498 vertices |
| Other patch component | 4,340 vertices | 15,628 vertices |
| Boundary vertices | 646 | 1,094 |
| Nonmanifold edges | 0 | 0 |
| Patch median edge length | 0.000695158 | 0.001781737 |
| Triangle aspect median / P95 | 1.652 / 2.742 | 1.933 / 3.601 |
| Median adjacent-triangle normal dot | 0.99860 | 0.99914 |

The existing solver patches contain two disconnected components. Landmark 105 is in the smaller component for both models, while the other component is unrelated to its local deformation. This is a confirmed structural property of the input patch, but it has not yet been isolated as the direct folding cause.

## Movement decomposition

Using the normal of landmark 105's attachment triangle:

| Component | Female | Male |
|---|---:|---:|
| Peak requested displacement | 0.001523904 | 0.008179732 |
| Normal component magnitude | 0.000130031 | 0.001378231 |
| Tangential component magnitude | 0.001518347 | 0.008062784 |

The target is predominantly tangential in both models. The male normal component is also larger relative to its local surface scale, but direction-only deformation solves were not completed and are therefore unverified.

## Avenue status

### Numerical normalization: INCONCLUSIVE

The original and interocular-normalized solves were launched with identical topology, target scaling, boundary scaling, and ARAP code. They did not finish within the bounded run, so no scale-invariance claim is made.

### Local surface structure: SUPPORTED

The patches contain two disconnected components, with the landmark component and an unrelated second component. Both patches have zero nonmanifold edges, but the male has worse triangle aspect ratios. This supports a structural mismatch as a stronger suspect than raw coordinate units, but does not prove the second component causes the local fold.

### Movement direction: INCONCLUSIVE

The vector decomposition shows mostly tangential motion, but the controlled tangential-only and normal-only ARAP solves were not completed. No causal direction claim is made.

### Deformation distribution: SUPPORTED

Existing intensity evidence shows a localized fold near landmark 105, high maximum strain with much lower P95 strain, and earlier male onset. This supports local strain concentration rather than global failure.

### Constraint feasibility: NOT TESTED

Testing feasibility independently would require another established constrained deformation solver or a separate optimization formulation. That was outside this run and no mathematical infeasibility is claimed.

## Recommendation

The next experiment should isolate the landmark-containing connected component from the unrelated patch component and rerun the unchanged ARAP diagnostic on that component only. This is preferable to another radius or boundary sweep because disconnected components are confirmed in both current patches and have not yet been separated experimentally. A result that leaves the fold onset unchanged would falsify the disconnected-component hypothesis and move attention to local triangle quality or target direction.

Evidence JSON: `verification/goal2-experiment5/geometry-audit/geometry-normalization-audit.json` was not produced because the bounded solve did not complete. Geometry values above come from the reproducible audit script's completed preprocessing pass.

Script: `scripts/audit_goal2_landmark105_geometry_normalization.py`
