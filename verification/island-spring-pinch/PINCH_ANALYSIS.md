# Pinch telemetry analysis

This is a diagnostic only. No deformation threshold, material parameter, source GLB, or pinch target was changed.

## Reproduction

- Biological preset: rho 1100 kg/m^3, thickness 0.0015 m, surface modulus 30000 Pa, inner modulus 10000 Pa.
- Controller: Kp 90 N/m, Kd 0.08 N*s/m.
- Integrator: visible implicit fallback.
- Drag target: 2% of each character's measured interocular scale.
- Source-to-meter scale: 0.30 m per source unit.
- The original GLBs were loaded read-only. Only the cloned runtime position attribute was integrated.
- Telemetry was sampled during the held pinch and for 1.2 seconds after release.

Raw time-series evidence: [pinch-telemetry.json](./pinch-telemetry.json)

Textured evidence: [female peak](./female-telemetry-peak.png), [female released](./female-telemetry-released.png), [male peak](./male-telemetry-peak.png), [male released](./male-telemetry-released.png)

## Measured results

| Measurement | Female | Male |
|---|---:|---:|
| Initial displayed island | 16, 5,036 vertices / 9,708 triangles | 35, 41,920 vertices / 82,807 triangles |
| Actual pinched island | 16, 5,036 vertices / 9,708 triangles | 23, 17,693 vertices / 34,832 triangles |
| Boundary edges on actual pinched island | 362 | 552 |
| Requested displacement | 0.001148814 source units, 0.3446 mm | 0.006081990 source units, 1.8246 mm |
| Release tracking error | 0.0125 mm | 0.2325 mm |
| Peak tracking error | 0.0389 mm | 0.3526 mm |
| Peak force | 0.003496 N | 0.03172 N |
| Peak maximum edge strain | 13.56% | 56.51% |
| Peak P95 edge strain | 0.3865% | 0.2302% |
| Worst observed minimum triangle-area ratio | 0.7775 at the peak-strain sample | 0.2433 during recovery |
| Peak orientation flips | 1 | 5 |
| Collapsed triangles at the captured peak | 0 | 0 |
| State after 1.2 seconds | 0 flips, 2.21% max strain | 3 flips, 7.60% max strain |
| State after 1.2 seconds minimum area ratio | 0.8573 | 0.3637 |

## What actually breaks

The solver is not failing numerically. All captured vertices remained finite and the pointer was released. The problem is geometric:

1. The active island has an open boundary. Its boundary vertices move while the neighboring rendered islands remain unchanged because the implementation intentionally creates zero cross-island springs.
2. The female has a localized peak strain and one temporary orientation flip. It recovers to zero flips in the captured recovery window, but the boundary displacement is still 0.0008169 source units, about 0.245 mm or 1.422% of female interocular width.
3. The male has a more severe localized deformation. The maximum boundary displacement observed is 0.0028281 source units, about 0.848 mm or 0.930% of male interocular width. Five local orientation flips appear during the held/recovery trajectory, and three remain in the final captured state.
4. The male peak screenshot shows the corresponding dark horizontal seam across the forehead. The released screenshot still shows it, consistent with the remaining flipped triangles and nonzero boundary displacement.

The low P95 strain alongside the much larger maximum strain shows that the damage is concentrated in a small number of edges and triangles rather than distributed smoothly over the island.

## Important selection mismatch

The male UI initially displays island 35 with 41,920 vertices. The pointer raycast lands on a triangle belonging to island 23, so `onPointerDown` rebuilds the solver for island 23 with 17,693 vertices. The `lastPinch.activeIsland` telemetry records 23, but the visible Active island text in the captured screenshot still shows the earlier island 35. Therefore the displayed label is stale at pinch time; it is not evidence that island 35 was deformed.

This mismatch is a separate instrumentation/UI defect. It does not explain away the geometry failure: the actual pinched island 23 has 552 open boundary edges and shows the measured strain and orientation flips.

## Diagnosis

Confirmed cause: the current pinch model deforms one disconnected original mesh island in isolation. The actual selected island's open boundary is free to separate from nearby visible geometry, and the compliant controller concentrates displacement into a small set of local edges. On the male, the resulting local fold persists after the release window.

Not supported by this capture: a nonfinite numerical blow-up, zero-mass failure, or collapsed-triangle failure. No triangle met the configured collapse threshold of area ratio <= 1e-3 in the captured run. That does not make the result acceptable; orientation flips, 56.5% local strain, and the visible seam are already sufficient evidence that the pinch breaks the face.

Next correction should be reviewed separately. This report intentionally does not add cross-island springs or alter the force controller.

## Reproduction

```powershell
$env:VELA_PINCH_TELEMETRY_PORT='4187'
node scripts/collect_pinch_telemetry.mjs
```

OVERALL DIAGNOSTIC RESULT: FACE BREAK REPRODUCED
