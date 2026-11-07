# Experiment 5 baseline restoration

The Experiment 5 baseline now calls the existing Experiment 4 `solve()` function directly. It does not duplicate or approximate the solver.

## Confirmed differences in the failed Experiment 5 attempt

1. Experiment 4 used the saved landmark-70 patches: female 4,340 vertices and 8,387 triangles; male 31,845 vertices and 62,878 triangles.
2. The failed Experiment 5 attempt used new 128-hop union patches: female 8,689 vertices and 16,728 triangles; male 24,126 vertices and 47,155 triangles.
3. Experiment 4 converted landmark 70 into a one-ring support control set: 12 female controls and 14 male controls. The failed attempt constrained only the three vertices of the landmark triangle.
4. Experiment 4 applied its local fold-correction procedure after the ARAP solve. The failed attempt used the new union-patch path and did not reproduce the Experiment 4 control construction.
5. ARAP energy, dimension, and iteration settings were otherwise the same official libigl settings.

These patch and control-set differences are sufficient to change the deformation.

## Restored baseline results

| Model | Experiment 4 landmark error | Restored baseline error | Neighbor movement | Genuine folds after correction | Collapses | Patch vertices | Corrected max edge strain |
|---|---:|---:|---:|---:|---:|---:|---:|
| Female | `9.35e-14` | `9.35e-14` | `0.00119655` | 0 | 0 | 4,340 | 11.41% |
| Male | `4.32e-15` | `4.32e-15` | `0.00642260` | 0 | 0 | 31,845 | 13.39% |

The male ARAP solve reports one neutral-normal inversion before the existing correction, exactly as in Experiment 4. After the existing shared-edge correction, it has zero genuine folds and zero collapsed triangles.

The saved Experiment 4 and restored Experiment 5 coordinates match at the solver output level because the same implementation, patches, targets, controls, and settings are used. No separate coordinate-difference artifact was required; the regenerated measurements are identical to the saved Experiment 4 report within floating-point output precision.

## Commands

```powershell
python scripts/run_goal2_experiment5_experiment4_baseline.py
```

Machine-readable output: `experiment4-baseline/baseline-report.json`.

No two-landmark test was run after restoring the baseline.
