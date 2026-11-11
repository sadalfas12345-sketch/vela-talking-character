# Staged RK4 waterfall calibration

Generated 2026-11-11T21:40:53.157Z.

- Stages completed through: robustness
- Reference mass multiplier: 1
- Offline physical gates excluded the real-time operation estimate.
- Screen and full-island performance are reported separately.
- Estimated operation counts are informational only; physical runs use an explicit per-model wall-clock cutoff.
- Checkpoint: [rk4-waterfall-checkpoint.json](./rk4-waterfall-checkpoint.json)
- Resume: `node scripts/calibrate_realtime_rk4.mjs --resume "C:\Users\USER\talking-character-demo\verification\island-spring-pinch\rk4-waterfall-checkpoint.json"`

Stage results:

- timestep: PASS with 1 evaluations
- gravity: PASS with 3 evaluations
- damping: PASS with 3 evaluations
- timestep-recheck: PASS with 1 evaluations
- pinch: PASS with 1 evaluations
- pinch-preflight: PASS with 6 evaluations
- pinch-preflight: PASS with 9 evaluations
- robustness: FAILED with 1 evaluations

Stages after the first failed gate were NOT RUN. Their status and the full-island validation fields are recorded in [rk4-calibration-report.json](./rk4-calibration-report.json).

The micro → screen → full progression is recorded in `rk4-physical-progression.json`. Micro female completed; micro male completed but did not settle. The female screen island reached the wall-clock cutoff after 40.0 s total evaluation. The male screen island completed in 36.4 s. Both full facial islands executed actual RK4 work and reached the 20 s per-solve wall-clock protection during the composite full evaluation, so they are incomplete rather than physically validated.

OVERALL STEP RESULT: FAILED
