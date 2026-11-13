# Full-island GPU RK4 stress validation

Generated 2026-11-13 on the RTX 2060 Max-Q with Warp 1.19.0, CUDA Toolkit 13.4, and the calibrated controller `Kp=0.1`, `Kd=0.01`.

The test uses the original full Tripo islands and the same resident GPU RK4 equations. It runs 20 deterministic unseen-seed pinch sequences per character, with four held target phases followed by release. The original topology, masses, surface springs, support springs, and controller parameters are unchanged.

| Character | Vertices | Sequences | Runtime | Max edge strain | P95 edge strain | Minimum area ratio | Orientation flips | Collapses | Max tracking error | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Female | 5,036 | 20 | 417.480 s | 0.37682% | 0.04570% | 0.946863 | 0 | 0 | 0.20202 mm | PASS |
| Male | 41,920 | 20 | 1,334.216 s | 0.57572% | 0.04800% | 0.967860 | 0 | 0 | 1.06453 mm | PASS |

Both runs remained finite and completed every held and release phase. The geometry validator reported zero orientation reversals and zero collapsed triangles in all 40 sequences. Minimum area ratio is reported separately from the collapse gate and remained well above the 0.001 collapse threshold.

## Execution

Female:

```powershell
python scripts/rk4_warp_gpu.py --domains female:full --stress-count 20 --stress-seed 20261113 --stress-hold-seconds 0.0166666666666667 --stress-release-seconds 0.02 --pinch-kp 0.1 --pinch-kd 0.01 --output verification/island-spring-pinch/rk4-warp-gpu-full20-female-benchmark.json --stress-output verification/island-spring-pinch/rk4-warp-gpu-full20-female-stress.json
```

Male stress-only rerun, avoiding an unrelated CPU reference preflight:

```powershell
python scripts/rk4_warp_gpu.py --domains male:full --stress-only --stress-count 20 --stress-seed 20261113 --stress-hold-seconds 0.0166666666666667 --stress-release-seconds 0.02 --pinch-kp 0.1 --pinch-kd 0.01 --graph-chunk 16 --output verification/island-spring-pinch/rk4-warp-gpu-full20-male-stressonly-benchmark.json --stress-output verification/island-spring-pinch/rk4-warp-gpu-full20-male-stressonly.json
```

## Runner correction

The stress path accepted `--graph-chunk` but `WarpSimulation.advance()` hardcoded 16. The runner now passes the selected chunk size through to resident-state advances. A `--stress-only` mode was also added so stress validation does not spend time on an unrelated CPU/GPU benchmark before entering the requested suite. Neither change alters the spring equations or physical parameters.

Raw evidence:

- [Female stress JSON](./rk4-warp-gpu-full20-female-stress.json)
- [Male stress JSON](./rk4-warp-gpu-full20-male-stressonly.json)
