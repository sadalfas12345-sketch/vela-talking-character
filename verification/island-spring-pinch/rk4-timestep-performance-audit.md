# RK4 timestep performance audit

This audit tests larger multiples of the conservative fixture timestep on the original full Tripo islands. It does not change mass, stiffness, damping, controller gains, topology, or spring connectivity.

## Stability boundary

The test trajectory used the calibrated controller `Kp=0.1`, `Kd=0.01`, the same deterministic pinch seed `20261113`, a 16.667 ms held interval, and a 20 ms release interval.

| Timestep factor | Female | Male | Interpretation |
| ---: | --- | --- | --- |
| 8x | PASS, 0 flips, 0 collapses | PASS, 0 flips, 0 collapses | Full-duration single-sequence probe |
| 16x | PASS, 0 flips, 0 collapses | PASS, 0 flips, 0 collapses | Full-duration single-sequence probe |
| 24x | PASS, 0 flips, 0 collapses | PASS, 0 flips, 0 collapses | Full-duration single-sequence probe |
| 32x | FAIL, 67 flips | PASS, 0 flips, 0 collapses | Female stability boundary exceeded |

The largest common timestep that passed the full-duration probe was therefore 24x. At 32x the female maximum edge strain reached 21.86% and the minimum area ratio fell to 0.7826. The male happened to remain valid at that factor, but the common configuration must satisfy both models.

## Full stress at the selected 24x factor

The same 20 unseen-seed sequences were run on each original full island.

| Character | Vertices | Runtime | Max edge strain | P95 edge strain | Minimum area ratio | Flips | Collapses | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Female | 5,036 | 14.175 s | 0.44917% | 0.08148% | 0.954143 | 0 | 0 | PASS |
| Male | 41,920 | 49.629 s | 1.01567% | 0.02466% | 0.951008 | 0 | 0 | PASS |

## State refinement against 1x

The direct resident-state audit used one identical pinch and compared the final released state to the validated 1x state.

| Character | Factor | Steps | Runtime | Max released position delta / face scale | Max released velocity delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Female | 1x | 278,091 | 16.513 s | reference | reference |
| Female | 12x | 23,176 | 1.400 s | 0.11485% | 0.04855 source units/s |
| Female | 24x | 11,590 | 0.710 s | 0.24491% | 0.04758 source units/s |
| Male | 1x | 136,037 | 52.896 s | reference | reference |
| Male | 12x | 11,341 | 4.522 s | 0.03414% | 0.02814 source units/s |
| Male | 24x | 5,673 | 2.285 s | 0.03589% | 0.02847 source units/s |

All states in this comparison were finite and had zero orientation flips and collapsed triangles. The 24x factor is a validated performance candidate for the tested trajectory, not a claim that every possible motion has identical integration error.

## Remaining real-time bottleneck

The selected 24x factor materially reduces offline cost, but it is not yet real-time on the full original islands. The 20-sequence suite takes 14.175 seconds female and 49.629 seconds male, and one 36.667 ms held/release sequence takes 0.710 seconds female and 2.285 seconds male in the direct state audit. The remaining cost is the number of RK4 substeps and repeated spring-force gathering over the 41,920-vertex male island, not rendering or a failed stability gate.

## Reproduction

```powershell
python scripts/audit_rk4_timestep_multiplier.py --model female --factors 1,12,24 --output verification/island-spring-pinch/rk4-timestep-multiplier-female.json
python scripts/audit_rk4_timestep_multiplier.py --model male --factors 1,12,24 --output verification/island-spring-pinch/rk4-timestep-multiplier-male.json
python scripts/rk4_warp_gpu.py --domains female:full,male:full --stress-only --stress-count 20 --stress-seed 20261113 --stress-hold-seconds 0.0166666666666667 --stress-release-seconds 0.02 --pinch-kp 0.1 --pinch-kd 0.01 --dt-factor 24 --graph-chunk 16 --output verification/island-spring-pinch/rk4-dt-factor-24-full20-benchmark.json --stress-output verification/island-spring-pinch/rk4-dt-factor-24-full20.json
```

Raw evidence:

- [Female timestep state audit](./rk4-timestep-multiplier-female.json)
- [Male timestep state audit](./rk4-timestep-multiplier-male.json)
- [24x full stress](./rk4-dt-factor-24-full20.json)
- [32x failure probe](./rk4-dt-factor-32-stress1.json)
