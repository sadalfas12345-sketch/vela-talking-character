# RK4 waterfall controller feedback

All probes use the same original Tripo micro-islands, seed `20261112`, 16.6667 ms held phases, and 20 ms release phases unless noted.

| Configuration | Female folds | Male folds | Female max strain | Male max strain | Result |
|---|---:|---:|---:|---:|---|
| Kp 0.1x, Kd 0.1x, surface 1x, inner 1x, 20 sequences | 0 | 78 | 0.007556 | 0.093395 | Male failed |
| Kp 0.1x, Kd 1x, surface 1x, inner 1x, 20 sequences | 0 | 80 | 0.009661 | 0.096145 | Male failed |
| Kp 0.1x, Kd 0.1x, surface 3.162x, inner 3.162x, 3 sequences | 0 | 9 | 0.007231 | 0.054238 | Male failed, short probe |
| Kp 0.3162x, Kd 1x, surface 1x, inner 1x, 20 sequences | 1 | 110 | 0.008556 | 0.134411 | Both failed |

Fold counts include held and released geometry checks. No probe produced collapsed triangles; the male failures are orientation reversals during the actual spring simulation, not pointer-only failures.

The controller-only probe is implemented with `--stress-controller-only` and reads the resumed waterfall checkpoint. It does not rerun earlier stages. The full 20-sequence artifacts are stored beside this report.

The selected waterfall candidate passed timestep, gravity, damping, timestep recheck, pinch response, and one-sequence controller preflight. The required 20-sequence robustness gate still fails on the male, so the validated physical configuration is not yet established.

## Material-block return

With `Kp 0.1x`, `Kd 0.1x`, fixed mass, damping, and timestep, a three-sequence material sweep produced:

| Surface multiplier | Inner multiplier | Female folds | Male folds | Gravity |
|---:|---:|---:|---:|---|
| 3.1623 | 1 | 0 | 22 | Both gravity-valid |
| 1 | 3.1623 | 0 | 14 | Both gravity-valid |
| 3.1623 | 3.1623 | 0 | 9 | Both gravity-valid |
| 10 | 10 | 0 | 9 | Gravity failed |

Increasing both stiffnesses reduced the short-probe male fold count but did not eliminate it, and the highest tested pair failed the gravity gate. The complete sweep is stored in `rk4-material-stress-sweep.json`.
