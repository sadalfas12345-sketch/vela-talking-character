# RK4 waterfall resume-state fix

Generated 2026-11-13.

## Defect

When a pinch-preflight candidate passed and the following robustness stage failed, the failed robustness checkpoint overwrote `current`. A later resume therefore reused the failed candidate and skipped the already-passed preflight stage.

## Correction

`runWaterfall()` now restores the candidate from the latest passed stage before falling back to checkpoint records. This preserves the last verified configuration across failed later stages. The fallback also checks the latest passed checkpoint for older checkpoint formats.

## Regression evidence

Command:

```text
node scripts/calibrate_realtime_rk4.mjs --feedback-demo
```

Result:

- `firstGeneration.allFailed`: `true`
- `nextGeneration.meanChanged`: `true`
- `resumeKeepsLastPassedCandidate`: `true`
- `passed`: `true`

The regression uses a checkpoint whose stage candidate, stale passed checkpoint candidate, and failed later candidate are different. It verifies that the passed stage candidate wins.

## Real checkpoint replay

Command:

```text
VELA_CALIBRATION_PINCH_PREFLIGHT_COUNT=1 node scripts/calibrate_realtime_rk4.mjs --resume verification/island-spring-pinch/rk4-waterfall-checkpoint.json --pinch-preflight-recheck --pinch-preflight-only
```

The real female and male Tripo domains loaded successfully. The replay completed with `PREFLIGHT_PASS` and 10 tested controller pairs. It did not claim the full robustness gate.

The subsequent 20-sequence verification of the selected `Kp=0.01`, `Kd=0.01` multipliers produced:

- Female: valid, zero genuine folds, zero collapses.
- Male: failed one genuine fold in sequence 19, zero raw orientation flips, zero collapses.

Therefore the resume bug is fixed, but the overall physical calibration remains failed until the male stress case is resolved.

## Reproduction

```text
node scripts/calibrate_realtime_rk4.mjs --feedback-demo
```

