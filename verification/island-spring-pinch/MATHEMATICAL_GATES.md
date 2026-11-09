# VELA mathematical verification gates

Executed from the working tree containing commit `75ad7c2`, with the original female and male Tripo GLBs loaded read-only in terminal Playwright Chromium. The gates are fail-fast: the browser runner stopped at Gate 8 and did not run any later experiment.

## Deterministic gates

| Gate | Result | Evidence |
|---|---|---|
| 1 Physical units | PASS | `mathematical-gates.json`: 1 N / 1 kg = 1 m/s², and at 0.30 m/source unit the source acceleration is 3.3333333333333335 units/s². Surface, inner, damping, and pinch conversion checks pass. |
| 2 One fixed-anchor spring | PASS | 40 N/m × 0.001 m = 0.04 N; 0.001 kg gives 40 m/s²; zero extension gives zero force; anchor displacement is zero. |
| 3 Two moving vertices | PASS | Equal/opposite force sum is zero; Hookean energy is 0.000020 J. Note: the dimensionally correct energy is 1/2 k ΔL². The literal k ΔL value is 0.04 N, a force, not joules. |
| 4 RK4 analytical oscillator | PASS | ω = 200 rad/s; period = 0.031415926535897934 s; error ratios after halving dt are 15.5568, 15.8936, and 15.9735. |
| 5 Damping and energy | PASS | Initial energy 1.9999999999999998e-5 J; final energy 3.4997612465365213e-14 J; maximum positive per-step energy change 0 J. |

## Browser gates

### Gate 6 — one actual Tripo island: PASS

The test used original indexed mesh geometry, one selected island, original edge rest lengths, area-derived masses, fixed inner anchors, and zero cross-island springs.

| Model | Active vertices | Triangles | Surface springs | Support springs | Face width m | Initial force N | Neighbor movement | Energy/recovery |
|---|---:|---:|---:|---:|---:|---|---:|---|
| Female | 5,036 | 9,708 | 14,743 | 20,108 | 0.01723221496805733 | (-0.0026606183, 0.0003845844, 0.0004212808) | 3.8518827e-6 | PASS |
| Male | 41,920 | 82,807 | 124,726 | 167,552 | 0.0912295861317181 | (-0.0134809909, -0.0088827981, 0.0033171235) | 2.6678814e-5 | PASS |

Both nudge tests had finite positions, nonzero neighboring response, reduced energy, and restored displacement. The browser also verified the unique-edge invariant and zero cross-island springs.

### Gate 7 — barycentric pinch controller: PASS

Female and male both completed hold, drag, and release. Barycentric weights summed to 1, and the sum of the three per-vertex force contributions matched the single total controller force within 1e-9 N. The active physics island, UI island value, and pointer-hit island matched. The actual pointer tracking errors were recorded in `browser-mathematical-gates.json`.

### Gate 8 — original 3D face pinch and recovery: FAIL

This gate stopped the run. A held pinch must have zero triangle orientation reversals and a converged implicit equation residual; neither model met that requirement.

| Model | Held orientation flips | Held min area ratio | Held max edge strain | Held implicit residual | Released orientation flips | Result |
|---|---:|---:|---:|---:|---:|---|
| Female | 1 | 0.9423556402 | 0.0942221756 | 3.9961591721 source velocity units | 0 | FAIL |
| Male | 1 | 0.9087279498 | 0.3962673163 | 2.3387817383 source velocity units | 0 | FAIL |

The female held fold was reported at local face `791485`; the male held fold at local face `723770`. Release recovery removed the orientation reversal in this run, but that does not satisfy the held-pinch gate. No triangle was classified as collapsed and no vertex was nonfinite.

The remaining numerical blocker is explicit in the telemetry: `integrateImplicitOne` uses eight nonlinear updates, and its final `converged` flag is false during the held pinch. The earlier update-order defect was corrected so velocity is recomputed from the final accepted position, but the residual remains nonzero. The geometry blocker is independently measured: one held triangle normal reverses on each model.

## Reproduction

```powershell
node scripts/run_physics_gates.mjs
node scripts/run_browser_physics_gates.mjs
```

Artifacts:

- [deterministic gate JSON](./mathematical-gates.json)
- [browser gate JSON](./browser-mathematical-gates.json)
- [female held screenshot](./female-gate7-held.png)
- [female released screenshot](./female-gate7-released.png)
- [male held screenshot](./male-gate7-held.png)
- [male released screenshot](./male-gate7-released.png)

OVERALL STEP RESULT: FAILED

The mathematical unit gates and controller gates pass. The original 3D face gate fails because the held pinch still produces a genuine orientation reversal and the implicit residual is not converged. No parameters were tuned and no additional physics, cross-island springs, remeshing, or stretch caps were introduced.
