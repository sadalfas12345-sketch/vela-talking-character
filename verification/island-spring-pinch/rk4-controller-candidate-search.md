# RK4 controller candidate search

Generated 2026-11-13 on the original Tripo micro stress domains.

## Candidate

The previous selected candidate produced one genuine male hold fold in sequence 19, face 101. A targeted diagnostic was added so that a known failing sequence can be replayed deterministically before a full stress run.

The successful candidate changes only the controller block:

| Parameter | Value |
|---|---:|
| Mass multiplier | 1 |
| Surface multiplier | 1 |
| Inner-support multiplier | 1 |
| Damping multiplier | 1 |
| RK4 timestep multiplier | 0.1 |
| Pinch Kp multiplier | 0.0031622776601683794 |
| Pinch Kd multiplier | 0.1 |

The physical material and mesh parameters remain unchanged.

## Targeted diagnosis

Command pattern:

```text
VELA_CALIBRATION_STRESS_COUNT=1 VELA_CALIBRATION_STRESS_START_SEQUENCE=19 VELA_CALIBRATION_PINCH_KP_LOG=-2.5 VELA_CALIBRATION_PINCH_KD_LOG=-1 node scripts/calibrate_realtime_rk4.mjs --resume verification/island-spring-pinch/rk4-waterfall-checkpoint.json --candidate-verify
```

The known male sequence 19 passed on both female and male domains with zero folds and zero collapses. The physical response gate also passed.

## Full 20-sequence result

Command pattern:

```text
VELA_CALIBRATION_STRESS_COUNT=20 VELA_CALIBRATION_STRESS_START_SEQUENCE=0 VELA_CALIBRATION_PINCH_KP_LOG=-2.5 VELA_CALIBRATION_PINCH_KD_LOG=-1 node scripts/calibrate_realtime_rk4.mjs --resume verification/island-spring-pinch/rk4-waterfall-checkpoint.json --candidate-verify
```

| Metric | Female | Male |
|---|---:|---:|
| Sequences | 20 | 20 |
| Stress result | PASS | PASS |
| Genuine folds | 0 | 0 |
| Collapsed triangles | 0 | 0 |
| Maximum edge strain | 0.3264% | 1.2988% |
| Maximum P95 edge strain | 0.0934% | 0.2130% |
| Maximum tracking error | 0.1458 mm | 0.9663 mm |
| Runtime | 155.1 s | 104.8 s |

The complete machine-readable output is `rk4-candidate-verification.json`.

This is a controller-stress pass on the selected real Tripo micro domains. It is not yet a claim that the full 5,036- and 41,920-vertex domains pass every final physical and performance gate.

