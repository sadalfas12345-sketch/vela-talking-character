# RK4 waterfall controller feedback

All probes use the same original Tripo micro-islands, seed `20261112`, 16.6667 ms held phases, and 20 ms release phases unless noted.

| Configuration | Female folds | Male folds | Female max strain | Male max strain | Result |
|---|---:|---:|---:|---:|---|
| Kp 0.1x, Kd 0.1x, surface 1x, inner 1x, 20 sequences | 0 | 78 raw | 0.007556 | 0.093395 | Male failed; genuine-fold audit not present in this older artifact |
| Kp 0.1x, Kd 1x, surface 1x, inner 1x, 20 sequences | 0 | 80 raw | 0.009661 | 0.096145 | Male failed; genuine-fold audit not present in this older artifact |
| Kp 0.1x, Kd 0.1x, surface 3.162x, inner 3.162x, 3 sequences | 0 | 9 raw | 0.007231 | 0.054238 | Male failed, short probe; genuine-fold audit not present in this older artifact |
| Kp 0.3162x, Kd 1x, surface 1x, inner 1x, 20 sequences | 1 | 110 raw; 1 genuine in the prior audit | 0.008556 | 0.134411 | Both failed |

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

## Damping return

At surface/support `3.1623x`, controller `Kp 0.1x / Kd 0.1x`, and three identical stress sequences, damping reduced male folds as follows:

| Damping multiplier | Female folds | Male folds | Gravity |
|---:|---:|---:|---|
| 3.1623x | 0 | 8 | Pass |
| 10x | 0 | 7 | Pass |
| 31.6228x | 0 | 4 | Pass |
| 100x | 0 | 2 | Pass |

The corrected full 20-sequence validation at `100x` damping produced 0 female genuine folds and 4 male genuine folds, with 10 male raw normal reversals and no collapses. It remains a failed robustness configuration, and the high damping value is not accepted as a successful physical solution. The authoritative artifact is `rk4-controller-stress-probe-s-3_1622776601683795-i-3_1622776601683795-d-100-kp-0_1-kd-0_1-n-20.json`.

## Final staged checkpoint

The preflight gate was rerun with the genuine-fold validator. The selected checkpoint candidate is mass `1x`, surface `1x`, inner support `1x`, damping `1x`, timestep `0.1x`, `Kp 1x`, `Kd 1x`. Its required 20-sequence robustness result is female valid with 0 genuine folds and male invalid with 67 genuine folds and 0 collapses. Runtime was 222.1 s for female and 228.2 s for male on the selected micro-islands. This is the current blocking result; no full facial-island physical validation is claimed.
