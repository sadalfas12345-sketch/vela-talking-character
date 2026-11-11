# Staged RK4 waterfall calibration

Generated 2026-11-11T21:11:37.924Z.

- Stages completed through: performance checkpoint, with robustness failed
- Reference mass multiplier: 1
- Offline physical gates excluded the real-time operation estimate.
- Screen and full-island performance are reported separately.
- Checkpoint: [rk4-waterfall-checkpoint.json](./rk4-waterfall-checkpoint.json)
- Resume: `node scripts/calibrate_realtime_rk4.mjs --resume "C:\Users\USER\talking-character-demo\verification\island-spring-pinch\rk4-waterfall-checkpoint.json"`

Stage results:

- timestep: PASS with 1 evaluations
- gravity: PASS with 3 evaluations
- damping: PASS with 3 evaluations
- timestep-recheck: PASS with 1 evaluations
- pinch: PASS with 1 evaluations
- pinch-preflight: PASS with 6 initial evaluations
- pinch-preflight: PASS with 9 genuine-fold recheck evaluations

Full validation and stress results are in [rk4-calibration-report.json](./rk4-calibration-report.json).

The selected checkpoint candidate is mass 1x, surface 1x, inner support 1x, damping 1x, timestep 0.1x, Kp 1x, Kd 1x. The full 20-sequence robustness result is female PASS with 0 genuine folds and male FAIL with 67 genuine folds and 0 collapses. Full facial-island validation was not claimed because the estimated offline cost exceeded the protection bound: female 134,193,357,288 stages and male 550,518,473,232 stages.

OVERALL STEP RESULT: FAILED
