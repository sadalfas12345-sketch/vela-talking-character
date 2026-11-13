# VELA reference-expression inverse-physics probe

Status: **frame-45 physical validation FAILED; full 121-frame replay NOT RUN**

This verification changes the expression objective from exact hard landmark
placement to compact external-force control. It preserves the existing
Hookean edge springs, abstract support springs, original vertices, original
triangles, virtual seam list, target trajectories, and barycentric attachments.
It does not overwrite vertices with landmark targets.

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

Zero-rest seam springs are reported separately. Their lengths are not divided
by a rest length, so they are not folded into the positive-rest strain metric.

## Machine-readable outputs

- [Female inverse report](female-frame045-inverse-final.json)
- [Female inverse positions and force field](female-frame045-inverse-final-positions.npz)
- [Male inverse report](male-frame045-inverse.json)
- [Male inverse positions and force field](male-frame045-inverse-positions.npz)
- [Female hard-target replay](female-frame045.json)
- [Male hard-target replay from the existing A5 evidence](../plan-a5-subcutaneous-run/male-stageb-frame45-supported.json)

Existing textured neutral and failed hard-target probe renders remain available
for visual comparison:

- [Female neutral](../plan-a5-subcutaneous-run/female-stageb-frame45-neutral.png)
- [Female failed supported probe](../plan-a5-subcutaneous-run/female-stageb-frame45-supported.png)
- [Male neutral](../plan-a5-subcutaneous-run/male-stageb-frame45-neutral.png)
- [Male failed supported probe](../plan-a5-subcutaneous-run/male-stageb-frame45-supported.png)

No optimized textured render is claimed: the frame-45 geometry gate failed
before a valid optimized expression state existed. The saved NPZ files are the
actual evaluated inverse states, not marker-only output.

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
```

OVERALL STEP RESULT: **FAILED**

The input correspondence gate passes. The inverse-physics implementation is
executed, but a valid converged and geometrically clean frame-45 expression
has not yet been demonstrated on both characters, so the full reference
sequence is not claimed.
