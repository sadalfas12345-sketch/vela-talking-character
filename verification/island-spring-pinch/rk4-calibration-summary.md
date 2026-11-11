# Staged RK4 waterfall calibration

Generated 2026-11-11T19:18:39.372Z.

- Stages completed through: performance
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
- pinch-preflight: PASS with 6 evaluations

Full validation and stress results are in [rk4-calibration-report.json](./rk4-calibration-report.json).

OVERALL STEP RESULT: FAILED