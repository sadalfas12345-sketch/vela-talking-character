# Calibrated controller full-domain validation

Generated 2026-11-13.

## Candidate

The candidate comes from the controller search in `rk4-controller-candidate-search.md`:

- mass multiplier: 1
- surface multiplier: 1
- inner-support multiplier: 1
- damping multiplier: 1
- RK4 timestep multiplier: 0.1
- Kp multiplier: 0.0031622776601683794
- Kd multiplier: 0.1
- effective controller values used by Warp: Kp 0.284604989 N/m, Kd 0.008 N s/m

The original Tripo topology and independent-island architecture are unchanged.

## Full-domain smoke

One held-and-released sequence was run on each full original-island fixture with the RTX 2060, CUDA graphs, and the actual 16.7 ms hold and 20 ms release durations.

| Metric | Female | Male |
|---|---:|---:|
| Vertices | 5,036 | 41,920 |
| Result | PASS | PASS |
| Runtime | 21.6 s | 61.2 s |
| Genuine folds | 0 | 0 |
| Collapses | 0 | 0 |
| Maximum edge strain | 0.13396% | 0.27261% |
| P95 edge strain | 0.01921% | 0.04107% |
| Minimum area ratio | 0.997478 | 0.984355 |

The complete output is in `rk4-warp-gpu-calibrated-controller-stress-full-smoke.json`.

## Graph scheduling comparison

The male full-island one-sequence comparison with graph chunk 16 also passed with zero folds and zero collapses in 53.1 seconds. This was slightly faster than graph chunk 1024 at 61.2 seconds, so chunk 16 remains the measured choice for this workload.

## Full 20-sequence attempt

The required unseen-seed full-domain batch was started with seed 20261113, graph chunk 16, and the same actual hold and release durations. After 20 minutes it was still active without producing a result, so it was stopped at the wall-clock performance boundary. No partial batch is counted as a pass.

The micro-domain 20-sequence CPU validation remains a PASS for both characters. Full-domain correctness is demonstrated for one sequence per character, but full-domain 20-sequence robustness and real-time feasibility remain NOT COMPLETE.

## Reproduction

```text
py -3.11 scripts/rk4_warp_gpu.py --manifest verification/island-spring-pinch/gpu-fixtures/manifest.json --domains female:full,male:full --pinch-kp 0.284604989 --pinch-kd 0.008 --cuda-graph --graph-chunk 16 --stress-count 1 --stress-seed 20261112 --stress-hold-seconds 0.016666666666666666 --stress-release-seconds 0.02 --stress-output verification/island-spring-pinch/rk4-warp-gpu-calibrated-controller-stress-full-smoke.json
```

