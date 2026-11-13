# VELA reference-expression inverse-physics probe

Status: **frame-45 physical validation FAILED; full 121-frame replay NOT RUN**

This verification changes the expression objective from exact hard landmark
placement to compact external-force control. It does not overwrite vertices
with landmark targets.

## GPU RK4 single-source consistency gate

The new frame-45 probe was rerun with the validated GPU RK4 definitions as its
single physical source of truth. It uses the original `edgeSprings` only,
original rest lengths, source scale `0.30 m/unit`, surface stiffness
`45 N/m`, area-derived support stiffness from the `10 kPa` inner modulus, and
the original fixed inner-anchor positions. The 24 Plan A5 virtual seam springs
are excluded in this mode, so the reported cross-island spring count is zero.
This is an explicit network change from the legacy inverse probe, not a silent
reinterpretation of its result.

The offline inverse state is evaluated on the existing A5 selected facial
domain. It is not claimed to be a full GPU RK4 trajectory replay. Masses and
the RK4 integrator are used by the separate short-horizon sensitivity gate;
the frame-45 inverse is a static force-controlled equilibrium using the same
spring, support, unit, and anchor definitions.

| Gate | Female | Male |
|---|---:|---:|
| Source vertices | 41,747 | 208,351 |
| Source triangles | 79,627 | 401,474 |
| Original surface springs | 121,358 | 609,759 |
| Virtual seam springs | 0 | 0 |
| Support springs | 166,792 | 832,542 |
| Frame-45 median image error | 0.0018275 | 0.0096444 |
| Frame-45 P95 image error | 0.0040906 | 0.0212767 |
| Force-balance residual | 0.0044873 N | 0.0500302 N |
| Positive-rest P95 strain | 0.6259% | 0.7623% |
| Conservative orientation reversals | 3 | 15 |
| Triangle collapses | 0 | 0 |
| Result | FAILED | FAILED |

Both states remain invalid because the nonlinear equilibrium residual is not
converged and conservative orientation reversals remain. The measured maximum
positive-rest strains are also 41.51% female and 65.91% male, despite their
lower P95 tails. No 121-frame expansion was started.

The reversal audit classifies female triangles `27895`, `28415`, and `28416`
as local-fold candidates. Male triangles `24818`, `36899`, `37538`, `111514`,
`123032`, `158416`, `200537`, `264346`, `264348`, `271432`, `286925`,
`287875`, `288828`, and `319881` are local-fold candidates. Male triangle
`305841` is the one coherent-rotation candidate. These classifications use
neighbor dihedral and normal-consistency evidence; they are not inferred from
normal rotation alone. The exact machine-readable audits are linked below.

### Force-response sensitivity

The required forward sensitivity test now uses landmark 105's exact Goal 1
attachment triangle on original source island 50, not a nearby triangle in a
screen crop. A `0.0001 N` barycentric force was applied along the diagnostic
up axis and evaluated with the existing GPU RK4 forward model. At a
`1e-6 s` short horizon, the actual finite-difference position Jacobian norm was
`3.0309030e-5` units/N and the first-order inertial prediction was
`3.0408951e-5` units/N, for `0.3286%` relative norm error. The test used zero
cross-island springs and no virtual seam springs. This validates force
placement, barycentric distribution, source-scale conversion, and mass units
before inverse optimization. It does not validate the later spring-dominated
static equilibrium.

- [GPU-consistent physics audit](gpu-consistent-physics-audit.json)
- [Exact-triangle RK4 sensitivity](../island-spring-pinch/rk4-reference-force-sensitivity.json)
- [Female GPU-consistent frame-45 metrics](female-frame045-gpu-consistent.json)
- [Male GPU-consistent frame-45 metrics](male-frame045-gpu-consistent.json)
- [Female GPU-consistent reversal audit](female-frame045-gpu-consistent-reversal-audit.json)
- [Male GPU-consistent reversal audit](male-frame045-gpu-consistent-reversal-audit.json)

## Input audit

The existing assets contain 121 valid frames and 478 landmark columns for both
characters. IDs 0-467 trace to the raw validated tracking archive. IDs 468-477
are present in the stabilized expression table but are table-derived rather
than independently validated raw trajectories. No independently measured
per-frame 3D depth channel exists. The existing target construction keeps each
Tripo landmark's neutral depth and adds zero displacement along the target
facial-depth axis.

- [Female input audit](../plan-a5-subcutaneous-run/female-reference-replay-audit.json)
- [Male input audit](../plan-a5-subcutaneous-run/male-reference-replay-audit.json)
- [Female target metadata](../plan-a5-subcutaneous-run/female-targets-r050.json)
- [Male target metadata](../plan-a5-subcutaneous-run/male-targets-r050.json)

Correspondence checks passed as an input gate: 478/478 attachments exist for
each model, all triangle indices are valid, all weights are finite, weight-sum
error is at most `2.22e-16`, and neutral attachment reconstruction is exactly
zero in the saved graph representation. The male warning remains preserved: ID
214 has one slightly negative barycentric weight of approximately
`-1.42485e-4`.

## Physical formulation

For a state increment `q` and compact force coefficient vector `u`, the first
inverse pass solves the regularized linearized equilibrium objective

`||K q - B u||² / s_eq² + ||L q - d_image||² / s_eye² + lambda ||u||²`

where `K` is assembled from the existing edge and abstract-support Hookean
Jacobians, `B` distributes each control force over its original attachment
triangle using the original barycentric weights, and `L` measures only the
existing target `right/up` image-plane coordinates. The uncertain depth channel
is not included in the image loss. The resulting state is then relaxed against
the nonlinear Hookean energy with the force vector held fixed. No positional
landmark constraint is applied during this solve.

The force basis is deterministic farthest-point selection among moving
landmarks. Female used 12 controls. Male used 4 controls for the first
resource-bounded comparison. Each control has three Cartesian force columns.

## Frame 45 results

The old hard-target baseline is retained for comparison. It satisfies the
landmarks numerically but is not an equilibrium and produces severe geometry
artifacts.

| Character | Method | Median image error | P95 image error | Force-balance residual | Positive-rest P95 strain | Orientation reversals, conservative | Collapses | Runtime | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Female | Existing hard targets | 0.0 for constrained readback | 0.0 for constrained readback | `1.35e-4` projected residual | `0.280` | `1,819` | 0 | 49.8 s | FAILED: max iterations |
| Female | Inverse force controls | `1.732e-3` | `3.944e-3` | `1.956e-3` | `1.124e-2` | 12 | 0 | 22.9 s | FAILED: orientation reversals remain |
| Male | Existing hard targets | 0.0 for solved component only | nonzero full readback | not converged | `0.107` P95 | `4,549` | 0 | prior A5 run | FAILED: max iterations |
| Male | Inverse force controls | `9.455e-3` | `2.079e-2` | `1.907e-2` | `1.525e-2` | 155 | 0 | 86.4 s | FAILED: orientation reversals remain |

The inverse formulation materially reduces the positive-rest edge-strain tail
and the conservative orientation-reversal count relative to the female hard
target probe, while no longer forcing exact 3D positions. It does not yet
produce a valid frame on either character because the remaining reversals have
not been proven to be harmless coherent rotations, and the force-balance
residual is not at equilibrium tolerance.

## Iterative force-control update

The required force-control update was also executed using an implicit local
equilibrium sensitivity map. Each control response was obtained by solving the
linearized Hookean equilibrium system for the force-basis columns. A small
regularized least-squares update was then applied, followed by nonlinear
equilibrium relaxation with the updated external force held fixed.

| Character | Controls | Response iterations | Image error before update | Image error after update | Force-balance residual | Conservative reversals | Runtime | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Female | 4 | 12 | `0.7803` normalized objective | `0.7877` normalized objective | `1.08e-1` | 105 | 99.2 s | FAILED: update rejected by objective and geometry |
| Male | 2 | 6 | `0.7712` normalized objective | `0.7906` normalized objective | `7.19e-1` | 255 | 469.4 s | FAILED: update rejected by objective and geometry |

The update worsened both force-balance and conservative geometry metrics. This
is evidence that the local response solve is ill-conditioned at the current
support and spring scales; it is not evidence that the physical system can
match the reference. The saved iterative states are retained for diagnosis.

### Acceptance correction regression

The optimizer now tests alpha `0.0` first and treats it as the immutable
baseline. A candidate is accepted only if its measured image objective
improves and it does not worsen finite-state, collapse, conservative reversal,
or force-balance metrics. The regression test passes:

```text
python scripts/test_inverse_optimizer_acceptance.py
inverse optimizer acceptance tests: PASS
```

The corrected run was initialized from the exact saved female 12-reversal
state, not a regenerated control set. All four tested updates were rejected
because they did not improve the actual image objective. Alpha zero was kept:

| Metric | Preserved initial inverse | Corrected iterative output |
|---|---:|---:|
| Median image error | `1.73157e-3` | `1.73157e-3` |
| P95 image error | `3.94392e-3` | `3.94392e-3` |
| Positive-rest P95 strain | `1.12163e-2` | `1.12163e-2` |
| Conservative reversals | 12 | 12 |
| Force-balance residual | `1.95595e-3` | `1.95595e-3` |
| Accepted alpha | baseline | `0.0` |

This prevents the previous regression where a worse state replaced the better
initial inverse result.

## The twelve female reversals

The exact audit is in [female reversal audit](female-frame045-reversal-audit.json).
There are 12 conservative orientation reversals. One triangle, local ID
`44566`, is a coherent-rotation candidate: its area ratio is `0.8694` and its
mean deformed neighbor normal dot is `0.8041`. The other 11 are local-fold
candidates under the current evidence because their neighboring normal dots
are low or negative. Their local IDs are:

```text
21397, 27895, 28415, 28416, 44564, 44567, 44568,
55966, 56777, 62294, 68962
```

The audit records original source vertex IDs, areas, edge ratios, neighboring
triangles, neutral and deformed dihedral angles, and distances to landmark
105. A full triangle-intersection test has not yet been run, so the 11 are
reported as local-fold candidates rather than mathematically proven
self-intersections. The optimizer therefore continues to reject any geometry
regression and does not call the female state valid.

## Legacy physics consistency audit

The [legacy physics consistency audit](physics-consistency-audit.json) records
the mismatch in the pre-381ad11 inverse probe. That legacy state used unit
coefficient static energy in source units and retained virtual seams, so its
force magnitudes are not physically comparable to the GPU RK4 controls.
The new `gpu-rk4-consistent-static` reports remove that mismatch in units,
spring family, support construction, anchors, and cross-island policy. The
remaining limitation is explicit domain and static-versus-dynamic scope, not
an unreported physical-definition change.

Zero-rest seam springs are reported separately. Their lengths are not divided
by a rest length, so they are not folded into the positive-rest strain metric.

## Machine-readable outputs

- [Female inverse report](female-frame045-inverse-final.json)
- [Female inverse positions and force field](female-frame045-inverse-final-positions.npz)
- [Male inverse report](male-frame045-inverse.json)
- [Male inverse positions and force field](male-frame045-inverse-positions.npz)
- [Female iterative force update](female-frame045-inverse-iterative.json)
- [Female iterative positions](female-frame045-inverse-iterative-positions.npz)
- [Male iterative force update](male-frame045-inverse-iterative.json)
- [Male iterative positions](male-frame045-inverse-iterative-positions.npz)
- [Corrected female alpha-zero regression](female-frame045-inverse-corrected.json)
- [Female reversal audit](female-frame045-reversal-audit.json)
- [Physics consistency audit](physics-consistency-audit.json)
- [GPU-consistent physics audit](gpu-consistent-physics-audit.json)
- [Female GPU-consistent frame-45 render, neutral](female-frame045-gpu-consistent-render-neutral.png)
- [Female GPU-consistent frame-45 render, evaluated](female-frame045-gpu-consistent-render-supported.png)
- [Male GPU-consistent frame-45 render, neutral](male-frame045-gpu-consistent-render-neutral.png)
- [Male GPU-consistent frame-45 render, evaluated](male-frame045-gpu-consistent-render-supported.png)
- [Reference video frame 45](reference-frame045.png)
- [Female hard-target replay](female-frame045.json)
- [Male hard-target replay from the existing A5 evidence](../plan-a5-subcutaneous-run/male-stageb-frame45-supported.json)

Existing textured neutral and failed hard-target probe renders remain available
for visual comparison:

- [Female neutral](../plan-a5-subcutaneous-run/female-stageb-frame45-neutral.png)
- [Female failed supported probe](../plan-a5-subcutaneous-run/female-stageb-frame45-supported.png)
- [Male neutral](../plan-a5-subcutaneous-run/male-stageb-frame45-neutral.png)
- [Male failed supported probe](../plan-a5-subcutaneous-run/male-stageb-frame45-supported.png)

The GPU-consistent evaluated states were rendered over the untouched textured
GLBs for inspection. They are diagnostic renders only: visual inspection found
severe spikes, gross facial collapse, and dark void-like regions in both
evaluated images, consistent with the numerical geometry failure. No valid
optimized textured expression is claimed. The saved NPZ files and rendered
images are actual evaluated states, not marker-only output.

## Decision and next gate

The inverse-force formulation is implemented and executed on both original
graphs. It avoids the specific failure mode of exact hard landmark constraints
by allowing image-plane error and regularizing the external force norm. It has
not yet passed the geometry or force-balance gates. The 121-frame sequence is
therefore **NOT RUN**; starting it now would propagate an invalid state and
would not be a valid product milestone.

Next work should improve the force-control optimization and its geometric
validation, not return to exact hard positional constraints. The first required
falsification is a converged force-controlled frame-45 state on both models
with zero confirmed local folds or intersections and a documented residual
tolerance. Only then should frame 45 be rendered and the temporal optimizer
expanded to the full 121 frames.

## Reproduction

```powershell
cd C:\Users\USER\talking-character-demo
python scripts\audit_reference_expression_replay.py --model female --capture verification\captureforge-facial-rig-test\worried-reference.capture.npz --table verification\goal2-browInnerUp-proof\worried-expression-table.json --graph verification\plan-a5-subcutaneous-run\female-spring-graph-r050.npz --targets verification\plan-a5-subcutaneous-run\female-targets-r050.npz --output verification\plan-a5-subcutaneous-run\female-reference-replay-audit.json
python scripts\audit_reference_expression_replay.py --model male --capture verification\captureforge-facial-rig-test\worried-reference.capture.npz --table verification\goal2-browInnerUp-proof\worried-expression-table.json --graph verification\plan-a5-subcutaneous-run\male-spring-graph-r050.npz --targets verification\plan-a5-subcutaneous-run\male-targets-r050.npz --output verification\plan-a5-subcutaneous-run\male-reference-replay-audit.json
python scripts\optimize_reference_forces.py --model female --graph verification\plan-a5-subcutaneous-run\female-subcutaneous-r050.npz --targets verification\plan-a5-subcutaneous-run\female-targets-r050.npz --target-json verification\plan-a5-subcutaneous-run\female-targets-r050.json --frame 45 --controls 12 --force-regularization 1 --linear-iterations 30 --nonlinear-iterations 4 --nonlinear-inner-iterations 25 --output verification\reference-expression-replay\female-frame045-inverse-final.json
python scripts\optimize_reference_forces.py --model male --graph verification\plan-a5-subcutaneous-run\male-subcutaneous-r050.npz --targets verification\plan-a5-subcutaneous-run\male-targets-r050.npz --target-json verification\plan-a5-subcutaneous-run\male-targets-r050.json --frame 45 --controls 4 --force-regularization 1 --linear-iterations 15 --nonlinear-iterations 3 --nonlinear-inner-iterations 20 --output verification\reference-expression-replay\male-frame045-inverse.json
$env:VELA_SENSITIVITY_SECONDS='0.000001'; node scripts\calibrate_realtime_rk4.mjs --reference-force-sensitivity
python scripts\optimize_reference_forces.py --model female --gpu-consistent --graph verification\plan-a5-subcutaneous-run\female-subcutaneous-r050.npz --targets verification\plan-a5-subcutaneous-run\female-targets-r050.npz --target-json verification\plan-a5-subcutaneous-run\female-targets-r050.json --frame 45 --controls 4 --force-scale 0.001 --force-regularization 1 --linear-iterations 20 --nonlinear-iterations 3 --nonlinear-inner-iterations 18 --output verification\reference-expression-replay\female-frame045-gpu-consistent.json
python scripts\optimize_reference_forces.py --model male --gpu-consistent --graph verification\plan-a5-subcutaneous-run\male-subcutaneous-r050.npz --targets verification\plan-a5-subcutaneous-run\male-targets-r050.npz --target-json verification\plan-a5-subcutaneous-run\male-targets-r050.json --frame 45 --controls 2 --force-scale 0.001 --force-regularization 1 --linear-iterations 12 --nonlinear-iterations 3 --nonlinear-inner-iterations 16 --output verification\reference-expression-replay\male-frame045-gpu-consistent.json
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python scripts\render_plan_a5_probe.py -- --glb assets\tripo\vela-photoreal\generated-original.glb --graph verification\plan-a5-subcutaneous-run\female-subcutaneous-r050.npz --positions verification\reference-expression-replay\female-frame045-gpu-consistent-positions.npz --camera verification\reference-expression-replay\female-frame045-camera.json --output verification\reference-expression-replay\female-frame045-gpu-consistent-render
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python scripts\render_plan_a5_probe.py -- --glb assets\tripo\generalization-male-20261105\generated-original.glb --graph verification\plan-a5-subcutaneous-run\male-subcutaneous-r050.npz --positions verification\reference-expression-replay\male-frame045-gpu-consistent-positions.npz --camera verification\reference-expression-replay\male-frame045-camera.json --output verification\reference-expression-replay\male-frame045-gpu-consistent-render
```

OVERALL STEP RESULT: **FAILED**

The input correspondence gate passes. The inverse-physics implementation is
executed, but a valid converged and geometrically clean frame-45 expression
has not yet been demonstrated on both characters, so the full reference
sequence is not claimed.
