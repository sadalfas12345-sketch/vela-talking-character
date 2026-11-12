# RK4 waterfall follow-up

Generated 2026-11-12 on the original Tripo female and male micro-islands. This is a continuation of `rk4-calibration-report.json`; the earlier full waterfall remains unchanged.

## Physical-gate policy correction

- Offline calibration no longer rejects a candidate because of an estimated RK4 operation count or substep count. Those counts are retained as diagnostics only.
- A model evaluation may stop only at an explicit wall-clock protection limit and is then recorded as incomplete, never as a physical pass.
- Damping candidates are ranked by measured settling velocity and force-residual ratios after they pass the gravity geometry gates.
- Pinch preflight now requires both zero stress-test geometry damage and the existing 50% nonzero force-response gate before it can replace the controller candidate.

## Candidate measurements

| Candidate | Female response / target | Male response / target | Short stress result | Decision |
|---|---:|---:|---|---|
| surface 3.1623, inner 3.1623, damping 100, Kp 0.01, Kd 0.1 | 14.24% | 7.66% | 20-sequence geometry clean in the saved probe | Reject: insufficient compliance |
| surface 3.1623, inner 3.1623, damping 100, Kp 0.0316, Kd 0.1 | 39.14% | 22.98% | 3-sequence probe clean | Reject: insufficient compliance |
| surface 3.1623, inner 3.1623, damping 100, Kp 0.0631, Kd 0.01 | 66.72% | 43.10% | Female clean; male 2 genuine folds in 3 sequences | Reject: male compliance and geometry |
| surface 3.1623, inner 3.1623, damping 100, Kp 0.1, Kd 0.0316 | 88.49% | 63.04% | Female clean; male 4 genuine folds in 3 sequences | Reject: male geometry |
| surface 3.1623, inner 3.1623, damping 100, Kp 0.1, Kd 0.01 | 88.70% | 63.16% | Female clean; male 5 genuine folds in 20 sequences | Reject: male geometry |
| surface 10, inner 10, damping 100, Kp 0.1, Kd 0.01 | 52.42% | 35.89% | Female clean; male 3 genuine folds in 3 sequences | Reject: male compliance and geometry |

The compliant candidate's definitive 20-sequence artifact is:

`rk4-controller-stress-probe-s-3_1622776601683795-i-3_1622776601683795-d-100-kp-0_1-kd-0_01-n-20.json`

Measured final stress result:

- Female: valid, 20 sequences, 0 raw orientation flips, 0 genuine folds, 0 collapses, 535470.25 ms.
- Male: invalid, 20 sequences, 10 raw orientation flips, 5 genuine folds, 0 collapses, 549674.79 ms.

The candidate reaches the force-response threshold on both models, but fails the mandatory male geometry gate. It was not promoted to the waterfall checkpoint.

The continued one-variable probes are recorded in `rk4-waterfall-continuation.json`. They include controller derivative-gain, damping, material-ratio, timestep-refinement, and effective-mass tests. The best short-probe result reduced the male fold count to one at `damping=10×, Kp=0.1×, Kd=0.1×`, but its response overshot to 209.1% of target and the remaining fold was local face 100. It was not advanced to the 20-sequence gate. The lower-gain fidelity probe reduced overshoot but still had two male folds. The timestep-refinement probe was bit-identical because the conservative local-stability estimate capped both requested timesteps.

## Remaining blocker

The staged search has not found a single configuration that is both at least 50% responsive on both characters and free of genuine folds in the male 20-sequence stress set. The clean low-gain candidates are not acceptable because they are mechanically under-responsive. The compliant candidates are not acceptable because the male mesh develops genuine local folds.

The previous waterfall's baseline robustness failure remains independently recorded: female valid, male invalid with 67 genuine folds and 99 raw flips. Full-island physical progression also remains incomplete under the explicit wall-clock protection: female full evaluation 300.15 s cutoff and male full evaluation 301.47 s cutoff.

The low-gain boundary probe at `Kp=0.01×, damping=10×, Kd=0.01×` still produced two genuine male folds and only 42.1% male response. This is not a valid way to hide the deformation by reducing force.

No material parameters, topology, spring connectivity, mesh vertices, or acceptance thresholds were changed to hide these failures. No performance stage was run after the failed robustness gate.

## Reproduction

```powershell
$env:VELA_CALIBRATION_STRESS_COUNT='20'
$env:VELA_CALIBRATION_MASS_LOG='0'
$env:VELA_CALIBRATION_SURFACE_LOG='0.5'
$env:VELA_CALIBRATION_INNER_LOG='0.5'
$env:VELA_CALIBRATION_DAMPING_LOG='2'
$env:VELA_CALIBRATION_DT_LOG='-1'
$env:VELA_CALIBRATION_PINCH_KP_LOG='-1'
$env:VELA_CALIBRATION_PINCH_KD_LOG='-2'
node scripts/calibrate_realtime_rk4.mjs --resume verification/island-spring-pinch/rk4-waterfall-checkpoint.json --stress-controller-only
```

## Result

Stage 1 timestep: PASS.

Stage 2 gravity: PASS.

Stage 3 damping: PASS.

Stage 4 pinch compliance: PASS for the promoted baseline, but the later compliant-candidate checks above were not geometrically valid on male.

Stage 5 robustness: FAILED.

Stage 6 performance: NOT RUN.

OVERALL STEP RESULT: FAILED
