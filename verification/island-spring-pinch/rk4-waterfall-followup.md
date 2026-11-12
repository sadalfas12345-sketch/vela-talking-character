# RK4 waterfall follow-up

Generated 2026-11-12 on connected facial subpatches extracted from the brow-containing original Tripo islands. This is a continuation of `rk4-calibration-report.json`; the earlier full waterfall remains unchanged.

## Evaluation-domain correction

The previous multi-fidelity code selected screen and micro domains from arbitrary disconnected GLB islands based only on vertex count. That could make a reported fold belong to unrelated geometry. The implementation now builds deterministic connected subpatches from the same brow-containing original island, preserving original vertex IDs and triangles.

The corrected domains are:

| Domain | Female | Male | Source |
|---|---:|---:|---|
| Full original island | 5,036 vertices, 9,708 triangles | 41,920 vertices, 82,807 triangles | Original island 16 / 35 |
| Screen connected subpatch | 1,000 vertices, 1,855 triangles | 1,000 vertices, 1,857 triangles | Same source island |
| Micro connected subpatch | 128 vertices, 206 triangles | 128 vertices, 210 triangles | Same source island |

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
| surface 1, inner 1, damping 100, Kp 0.1, Kd 0.01 | 132.19% | 109.99% | Female clean; male 2 genuine folds in 3 sequences | Reject: male geometry |
| surface 1, inner 1, damping 316, Kp 0.1, Kd 0.01 | nonfinite | nonfinite | Female runaway with 3 collapses; male nonfinite response | Reject: numerical instability |
| surface 1, inner 1, damping 100, Kp 0.1, Kd 0.1 | 130.83% | 108.92% | Female clean; male 2 genuine folds in 3 sequences | Reject: male geometry unchanged |
| surface 1, inner 1, damping 100, Kp 0.0316, Kd 0.1 | 67.60% | 43.12% | Female clean; male 2 genuine folds in 3 sequences | Reject: male response below gate |
| surface 1, inner 1, mass 1.995, damping 100, Kp 0.1, Kd 0.01 | 119.32% | 93.70% | Female clean; male 4 genuine folds in 3 sequences | Reject: mass worsened male geometry |

The compliant candidate's definitive 20-sequence artifact is:

`rk4-controller-stress-probe-s-3_1622776601683795-i-3_1622776601683795-d-100-kp-0_1-kd-0_01-n-20.json`

Measured final stress result:

- Female: valid, 20 sequences, 0 raw orientation flips, 0 genuine folds, 0 collapses, 535470.25 ms.
- Male: invalid, 20 sequences, 10 raw orientation flips, 5 genuine folds, 0 collapses, 549674.79 ms.

The candidate reaches the force-response threshold on both models, but fails the mandatory male geometry gate. It was not promoted to the waterfall checkpoint.

The continued one-variable probes are recorded in `rk4-waterfall-continuation.json`. They include controller derivative-gain, damping, material-ratio, timestep-refinement, and effective-mass tests. The best short-probe result reduced the male fold count to one at `damping=10×, Kp=0.1×, Kd=0.1×`, but its response overshot to 209.1% of target and the remaining fold was local face 100. It was not advanced to the 20-sequence gate. The lower-gain fidelity probe reduced overshoot but still had two male folds. The timestep-refinement probe was bit-identical because the conservative local-stability estimate capped both requested timesteps.

## Fidelity progression with corrected domains

The corrected baseline candidate is `mass=1, surface=1, inner=1, damping=100, dt=0.1, Kp=0.1, Kd=0.01`.

- Micro domain, 20 sequences: female PASS with 0 folds and 0 collapses; male PASS with 0 genuine folds, 3 raw orientation flips, and 0 collapses. Runtime was 161.7 s female and 107.1 s male.
- Screen domain, 3 sequences: female FAILED with 6 genuine folds and 5,195 raw flips; male PASS with 0 folds. Lowering Kp to 0.0631x produced the same female screen failure, so the pattern is not explained by proportional overshoot alone.
- Full original island, 1 sequence: female and male timed out under the corrected segment wall protection. Female recorded no fold before timeout; male recorded 6,233 genuine folds and 6,252 raw flips before timeout.

The full-island test also found and fixed a timeout-propagation bug: `randomPinchStress` had not passed the offline wall-clock limit into its hold and release simulations. It now passes the limit and marks incomplete segments invalid instead of treating them as physical results.

The explicit candidate verification artifact records micro preflight, 20-sequence robustness, six-direction gravity, full-island validation, and profiling separately in `rk4-waterfall-candidate-verification.json`. Micro robustness and gravity pass; full validation is incomplete and profiling is deferred.

## Remaining blocker

The staged search has not found a single configuration that is both at least 50% responsive on both characters and free of genuine folds in the male 20-sequence stress set. The clean low-gain candidates are not acceptable because they are mechanically under-responsive. The compliant candidates are not acceptable because the male mesh develops genuine local folds.

The previous waterfall's baseline robustness failure remains independently recorded: female valid, male invalid with 67 genuine folds and 99 raw flips. Full-island physical progression also remains incomplete under the explicit wall-clock protection: female full evaluation 300.15 s cutoff and male full evaluation 301.47 s cutoff.

The low-gain boundary probe at `Kp=0.01×, damping=10×, Kd=0.01×` still produced two genuine male folds and only 42.1% male response. This is not a valid way to hide the deformation by reducing force.

The baseline-material continuation probe at `surface=1×, inner=1×, damping=100×, Kp=0.1×, Kd=0.01×` produced 132.19% female and 109.99% male force response. The female three-sequence stress probe was clean; the male probe produced 8 raw orientation flips and 2 genuine folds with no collapses. The response was adequate, but the male geometry gate still failed, so this candidate was not promoted.

The next controlled probes ruled out the remaining simple parameter levers. Damping 316× became numerically unstable, and lowering the requested RK4 timestep by 10× was bit-identical because the internal conservative timestep cap remained active. Increasing derivative gain to 0.1× left the male fold count unchanged. Lowering proportional gain to 0.0316× reduced male response to 43.12% but still left two folds. Increasing effective mass to 1.995× reduced male response to 93.70% and increased folds to four.

No material parameters, topology, spring connectivity, mesh vertices, or acceptance thresholds were changed to hide these failures. No performance stage was run after the failed robustness gate.

## Full-island timestep and damping diagnosis

The domain audit showed that the original spring-only timestep estimate was incomplete for high damping. On the full female island, damping 100x gives a minimum-mass damping rate of 7.9464e6 per second and a damping timestep estimate of 1.5101e-8 seconds. On the full male island the corresponding values are 4.5843e6 per second and 2.6176e-8 seconds. The implementation now records both spring and damping stability estimates and uses their minimum before applying the separately measured empirical multiplier.

For damping 1x, full-domain convergence over 0.005 seconds passed at 16x the spring estimate on both characters. For damping 10x, the full-domain convergence and geometry results from the prior spring-estimate run were clean at 8x the spring estimate. Under the corrected damping-aware estimate, that timestep is approximately 16x on the female and 19.5x on the male; therefore 16x is the next common multiplier to validate, rather than treating the old 8x label as a universal timestep.

The full damping 10x physical evaluation was finite and fold-free in the completed gravity samples. Female met the short-window settling thresholds. Male remained finite and fold-free but had a force-residual ratio of 0.2662 after the short 0.005-second window, so it was not marked settled. The evaluation was incomplete under the wall-clock protection while its response and convergence diagnostics were still recorded.

The full damping 100x evaluation at the old 16x spring timestep diverged on both full islands. This is classified as an explicit damping-mode timestep failure, not as a material or topology result.

The corrected damping-aware domain audit is saved in `rk4-domain-audit-damping10-stability16-corrected.json`. It records damping 10x on the same full original islands: the female damping-aware estimate is 1.5101e-7 seconds and the male estimate is 2.6176e-7 seconds. With the common empirical multiplier 16, the selected internal steps are approximately 2.4162e-6 and 4.1882e-6 seconds respectively. The audit also records zero-area-face counts, edge-length and mass distributions, support-spring counts, and the effective-mass-not-anatomical-density interpretation.

The saved full-domain evaluation was generated before the final metadata-only validator correction. Its raw main h, h/2, and h/4 convergence samples are complete and converged on both models; high-factor timestep samples are deliberately diagnostic boundary probes and are not allowed to mark the main evaluation incomplete. A fresh full-domain run will be used for the next physical settling check.

## Male full-island gravity settling follow-up

The targeted follow-up is saved in `rk4-gravity-audit-male-damping10-stability16-0_02s.json`. It uses the unchanged original male island, damping 10x, the common stability multiplier 16, and 0.02 seconds of simulated time. All six skull-relative gravity directions completed 4,776 RK4 steps without a wall-clock cutoff.

- Finite state: PASS.
- Settled in all six directions: PASS.
- Orientation flips, genuine folds, and collapsed triangles: 0 in every direction.
- Worst edge strain: 0.00175183, or 0.175183%.
- Worst final normalized velocity: 0.00011033.
- Worst force residual ratio: 0.0227295.
- Per-direction runtime: 109.1 to 142.9 seconds.

This resolves the prior male short-window gravity residual. It does not yet pass the separate 20-sequence full-island pinch gate or the performance gate.

## Full-island single pinch follow-up

The same damping 10x, stability-multiplier 16 configuration was then run on one complete held-pinch and release sequence per character. The per-model artifacts are `rk4-controller-stress-probe-f-full-s-1-i-1-d-10-kp-1-kd-1-n-1-full-damping10-stability16-female-single-pinch.json` and `rk4-controller-stress-probe-f-full-s-1-i-1-d-10-kp-1-kd-1-n-1-male.json`.

| Model | Full-island vertices | Completed | Raw orientation flips | Genuine folds | Collapses | Runtime | Result |
|---|---:|---|---:|---:|---:|---:|---|
| Female | 5,036 | held and released | 0 | 0 | 0 | 121.5 s | PASS for this sequence |
| Male | 41,920 | held and released | 1 | 0 | 0 | 755.1 s | PASS for this sequence |

The male raw orientation flip was classified by the existing local geometry validator as a non-genuine 3D rotation; the genuine-fold and collapse counts remained zero. This is a one-sequence mechanical check only. The required 20-sequence full-island robustness gate remains open.

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
