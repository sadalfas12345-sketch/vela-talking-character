# Experiment 5: Isolate Landmark-105 Mesh Component

Only the temporary ARAP patch was changed. The component containing landmark 105 was retained; the unrelated disconnected component was removed. The original mesh, landmark attachment, target vector, ARAP solver, boundary rule, and validation method were unchanged.

## Patch comparison

| Measurement | Female before | Female after | Male before | Male after |
|---|---:|---:|---:|---:|
| Solver vertices | 8,689 | 4,349 | 24,126 | 8,498 |
| Solver triangles | 16,728 | 8,532 | 47,155 | 16,108 |
| Connected components | 2 | 1 | 2 | 1 |
| First fold | 83% | 83% | 25% | 25% |
| Folds at 100% | 2 | 2 | 41 | 41 |
| Maximum strain at 100% | 39.309% | 39.309% | 71.289% | 71.289% |

## Isolated intensity results

### Female

0–80%: zero folds. First fold at 83%, with 1 fold. At 88% the count becomes 2 and remains 2 at 100%.

### Male

0–24%: zero folds. First fold at 25%, with 2 folds. The count becomes 3 at 26% and remains 3 through 40%, then increases to 41 at 100%.

Landmark positional errors remained numerical-zero-level in every successful solve. The original target was not attenuated.

## Interpretation

Removing the unrelated component has no measurable effect on fold onset, fold count, or peak strain. The disconnected component was not contributing to the landmark-105 failure.

The hypothesis is therefore rejected. The cause remains local deformation incompatibility within the connected landmark component, involving the target displacement, local triangle geometry, and fixed boundary distribution.

Evidence:

- [Machine-readable report](isolated-component/isolated-component-report.json)
- [Isolated female patch](isolated-component/female-isolated-component.patch.npz)
- [Isolated male patch](isolated-component/male-isolated-component.patch.npz)
- [Existing female fold close-up](landmark105-intensity/female-first-fold-closeup.png)
- [Existing male fold close-up](landmark105-intensity/male-first-fold-closeup.png)

Reproducible script: `scripts/run_goal2_experiment5_isolate_landmark105_component.py`
