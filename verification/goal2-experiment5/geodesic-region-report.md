# Experiment 5: Anatomically Scaled Deformation Region

The original landmark-105 target, attachment, official libigl ARAP bridge, and fixed-boundary treatment were unchanged. Regions were selected by edge-length Dijkstra distance from the attachment triangle, with radius expressed as a fraction of each model's measured interocular width.

## Results

| Radius / eye width | Female folds | Male folds | Female landmark error | Male landmark error | Female max strain | Male max strain |
|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 1 | solver failed | 1.46e-11% | unavailable | 60.12% | unavailable |
| 0.20 | 3 | 45 | 1.47e-11% | 1.95e-12% | 45.29% | 74.78% |
| 0.30 | solver failed | solver failed | unavailable | unavailable | unavailable | unavailable |
| 0.50 | 2 | 41 | 1.46e-11% | 2.58e-12% | 39.31% | 71.29% |

All valid solves reached the exact barycentric landmark target numerically. No valid radius passed geometry on both models. The 0.10 male and 0.30 female/male regions failed during native ARAP precomputation, so they cannot qualify as deformation results.

Additional valid-solve measurements:

- 0.10 female: 252 vertices, 449 triangles, 1 fold, 0 collapses, P95 strain 15.12%.
- 0.20 female: 690 vertices, 1,288 triangles, 3 folds, 0 collapses, P95 strain 6.83%.
- 0.20 male: 2,902 vertices, 5,607 triangles, 45 folds, 0 collapses, P95 strain 8.91%.
- 0.50 female: 2,794 vertices, 5,326 triangles, 2 folds, 0 collapses, P95 strain 2.70%.
- 0.50 male: 8,422 vertices, 16,466 triangles, 41 folds, 0 collapses, P95 strain 2.50%.

Boundary displacement was zero in all valid solves because the generated outer boundary was hard-fixed, as required by the unchanged baseline rule.

## Interpretation

Increasing normalized geodesic radius lowers the high-percentile strain, but it does not remove the localized folds. The male remains invalid at every radius that successfully binds and solves. The smaller radii also expose a second limitation: some geodesically selected subregions do not produce a valid native ARAP precomputation.

Therefore equal physical region size alone is insufficient to make landmark 105 valid. The deformation remains locally incompatible with the fixed-boundary ARAP representation.

No radius was accepted, so the requested multi-intensity follow-up was not run.

## Evidence

- [Machine-readable measurements](geodesic-region/geodesic-region-report.json)
- [Female region selection](geodesic-region/female-region-selection.png)
- [Male region selection](geodesic-region/male-region-selection.png)
- Script: `scripts/run_goal2_experiment5_geodesic_region.py`

Reproducible command is documented in the script and uses the existing female and male patch, Goal 1 records, and transferred marker files.
