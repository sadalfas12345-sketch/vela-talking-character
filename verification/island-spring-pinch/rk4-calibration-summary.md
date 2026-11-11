# Automated RK4 calibration

Generated 2026-11-11T17:25:22.970Z.

- Seed: 20261111
- Algorithm: bounded log-space CMA-ES with multi-fidelity early rejection
- Models: female, male
- Best feasible candidate: NO
- Best parameters: `{"massMultiplier":288063.9692461627,"surfaceMultiplier":0.3343597554356497,"innerMultiplier":47.315434468853795,"dampingMultiplier":0.14695724096099927,"dtMultiplier":0.1,"logParameters":[5.459488940556897,-0.4757860011015441,1.6750028323075095,-0.8328090102587355,-1.099475803764957]}`
- Full validation: no candidate passed all numerical gates

The complete candidate history and rejection metrics are in [rk4-calibration-report.json](./rk4-calibration-report.json).

Reproduce the search from the repository root with:

```powershell
$env:VELA_CALIBRATION_MODELS='female,male'
$env:VELA_CALIBRATION_GENERATIONS='2'
$env:VELA_CALIBRATION_POPULATION='6'
$env:VELA_CALIBRATION_FULL_SURVIVORS='2'
$env:VELA_CALIBRATION_MAX_SUBSTEPS='800'
$env:VELA_CALIBRATION_MAX_STAGES='250000000'
$env:VELA_CALIBRATION_SEED='20261111'
node scripts/calibrate_realtime_rk4.mjs
```

## Target-island resource gate

| Model | Vertices | Triangles | Surface springs | Support springs | Best-candidate estimated stages | Result |
|---|---:|---:|---:|---:|---:|---|
| Female | 5,036 | 9,708 | 14,743 | 20,108 | 501,854,400 | REJECTED: operation budget |
| Male | 41,920 | 82,807 | 124,726 | 167,552 | 4,208,803,200 | REJECTED: operation budget |

The best candidate used mass multiplier 288063.9692, surface multiplier 0.33436, inner multiplier 47.3154, damping multiplier 0.14696, and timestep multiplier 0.1. It was not promoted because the original target islands exceeded the 250,000,000-stage full-validation budget. The 20-sequence pinch gate was not run because no candidate passed full gravity, geometry, convergence, and compute gates.

## Browser baseline

The compact terminal-Playwright baseline is in [realtime-rk4-browser-baseline.json](./realtime-rk4-browser-baseline.json). With the existing realtime preset, one 60 Hz step took approximately 1,037.8 ms on female and 15,138.4 ms on male. After a 50 ms down-gravity check, female had 68 orientation flips and male had 10. This is a baseline failure, not a calibrated result.

OVERALL STEP RESULT: FAILED
