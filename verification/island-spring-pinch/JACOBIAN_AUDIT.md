# Gate 8 Newton-CG mathematics audit

Date: 2026-11-11

This audit starts from commit `e990005ca191fb0719ba18ce627e309ce8d3a41` and preserves the previously recorded female held-pinch result. It changes the Newton linear solve only; material coefficients, controller gains, mesh islands, fixed inner anchors, and source GLBs are unchanged.

## 1. Jacobian derivative check

The complete production residual was audited:

`R(x) = x - x_n - dt v_n - dt^2 a(x, (x - x_n) / dt)`

The test includes surface springs, fixed-anchor springs, damping, and a barycentric compliant pin. Unequal masses are used deliberately.

| Measurement | Result | Acceptance | Result |
|---|---:|---:|---|
| Finite-difference epsilon | `1e-7` | documented test input | RECORDED |
| Maximum Jacobian-vector derivative error | `3.7821468179544127e-10` | `< 1e-7` | PASS |
| RMS derivative error | `1.4560052233677991e-10` | diagnostic | PASS |

The analytical Jacobian matches the finite-difference derivative of the complete residual.

## 2. Symmetry check

For random vectors `u` and `v`, the ordinary operator was checked through `u·Jv` versus `v·Ju`.

| Operator | Bilinear difference | Result |
|---|---:|---|
| Ordinary Euclidean `J` | `0.03499631281024618` | NOT SYMMETRIC |
| Mass-weighted `A = M^(1/2) J M^(-1/2)` | `8.881784197001252e-16` | SYMMETRIC |
| Weighted matrix transpose maximum error | `1.734723475976807e-18` | SYMMETRIC |
| Similarity-transform application error | `2.220446049250313e-16` | PASS |

The old direct CG solve was mathematically invalid for unequal vertex masses. The production solve now uses the mass-weighted similarity transform and converts the solved increment back with `M^(-1/2)`.

## 3. Negative curvature

For a compressed Hookean spring with current length `0.45`, rest length `0.90`, and stiffness `40`, the transverse spring-Hessian eigenvalue is:

`k * (1 - rest / length) = -40`

This is genuine negative curvature from the existing Hookean energy, not a material change. The weighted CG implementation detects `p·A·p <= 0` and retries the linearized solve with a numerical Levenberg shift. The shift is applied only to the linear solve; the nonlinear residual, spring energy, and physical coefficients remain unchanged. The shift history is reported in `metrics.implicit.regularizationHistory`.

## 4. Small-network integrator comparison

The unit test now checks both position and velocity against fine-step RK4. The production implicit step uses `dt = 1/12000`; the refined comparison halves that step.

| Measurement | Production | Refined production | Fine RK4 |
|---|---:|---:|---:|
| Position error | `2.5553193107040765e-6` | `1.3145308998403467e-6` | reference |
| Velocity error | `1.5755417667764789e-3` | `8.059605581368125e-4` | reference |
| Nonlinear residual max | `1.0874116332622102e-19` | recorded by test | reference |

Both position and velocity error decrease under timestep refinement. The complete unit-test suite passes.

## 5. Real female Gate 8 evidence

The preserved pre-audit female held result remains:

- implicit status: `converged`
- Newton iterations: `5`
- linear iterations: `320`
- equation residual: `4.279100007264017e-7`
- orientation flips: `0`
- collapsed triangles: `0`
- nonfinite vertices: `0`
- maximum edge strain: `0.10339098050230647`
- minimum triangle-area ratio: `0.9373759712692219`

The preserved female release result remains a failure:

- implicit status: `stagnated`
- Newton iterations: `7`
- linear iterations: `383`
- equation residual: `0.31289280607470094`
- orientation flips: `0`
- collapsed triangles: `0`
- nonfinite vertices: `0`
- maximum edge strain: `0.0027126710761425786`
- minimum triangle-area ratio: `0.9899170382150145`

The release geometry was finite and non-inverted, but the physical equation was not converged. Therefore Gate 8 was not passed.

## 6. Post-audit browser attempts

Commands used:

```powershell
node scripts/audit_implicit_jacobian.mjs
node scripts/test_pinch_physics.mjs
$env:VELA_GATE_MODELS='female'
$env:VELA_GATE_SKIP_GATE6='1'
$env:VELA_GATE_SCREENSHOTS='0'
$env:VELA_GATE_CONTROLLED_STEPS='1'
node scripts/run_browser_physics_gates.mjs
```

The CG-64 continuous female attempt ran for approximately 15 minutes with an active renderer and then ended with `mouse.move: Target page, context or browser has been closed`; no Gate 7 or Gate 8 measurement was emitted. The CG-16 controlled-step attempt was also interrupted before emitting a report. These are runtime-incomplete diagnostics, not passes.

## Conclusion

The mathematical defect was confirmed and the Newton linear system was reformulated correctly. The small-network tests pass, but the original textured female release has not yet been revalidated to converged equilibrium after this change. The male complete pinch must not be tested or declared until the female release produces a converged report.

**Gate 8: FAILED — real female release convergence remains unverified.**
