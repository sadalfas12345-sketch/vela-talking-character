# Automated RK4 calibration

Generated 2026-11-11T18:01:55.222Z.

- Seed: 20261111
- Algorithm: adaptive bounded log-space CMA-ES with failure-distance feedback, multi-fidelity promotion, caching, and checkpoints
- Models: female, male
- Cycles completed: 8 of 8
- Best feasible candidate: NO
- Best parameters: `{"massMultiplier":13017.915449170669,"surfaceMultiplier":14.26657249329415,"innerMultiplier":626.6661083388067,"dampingMultiplier":100,"dtMultiplier":1,"logParameters":[4.1145414464900965,1.154319647533392,2.7970362076097355,2,0]}`
- Dominant final diagnosis: substep-budget
- Full validation: no candidate passed all numerical gates
- Checkpoint: [rk4-calibration-checkpoint.json](./rk4-calibration-checkpoint.json)
- Resume: `node scripts/calibrate_realtime_rk4.mjs --resume "C:\Users\USER\talking-character-demo\verification\island-spring-pinch\rk4-calibration-checkpoint.json"`

The complete candidate history, feedback decisions, convergence diagnostics, and rejection metrics are in [rk4-calibration-report.json](./rk4-calibration-report.json).

Feedback demonstration: first generation deliberately failed all candidates, detected operation-budget as the dominant mechanism, and changed the next-generation mean and bounds: PASS.

OVERALL STEP RESULT: FAILED