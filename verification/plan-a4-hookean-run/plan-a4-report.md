# Plan A4 scalable Hookean solver

Branch: `wip/tripo-face-repair`
Starting commit: `c46782b19ad2724d180b439eeb21adee1388aedb`

## Scope

This run kept the A3 physical model unchanged: original mesh-edge Hookean
springs, recorded virtual seam springs, hard barycentric landmark constraints,
and numerical step control only. No bending, volume, support, ARAP, bones,
morph transfer, or stretch/force caps were added.

The run stopped after the first full-face expressive-frame stage failed. The
121-frame animation was not started.

## Implementation

New files:

- `scripts/solve_plan_a4_projected_hookean.py`
- `scripts/test_plan_a4_solver.py`
- `scripts/extract_plan_a4_component.py`
- `scripts/validate_plan_a4_frame.py`
- `scripts/render_plan_a4_frame.py`

The solver constructs the sparse constraint matrix once per connected spring
component. It detects redundant rows from the small constraint Gram matrix,
factors `C C.T` once, and uses the resulting affine projector for exact
feasible initialization and every nonlinear tangent step. The linearized
Hookean residual is solved with matrix-free LSQR in the projected tangent
space. No dense vertex-space null basis or full KKT factorization is formed.

The final candidate state is accepted only when the actual nonlinear spring
energy decreases. Hard-constraint residual and projected force residual are
reported separately.

## Stage A: solver unit tests

Command:

```text
python scripts/test_plan_a4_solver.py
python scripts/test_plan_a3_topology.py
python scripts/test_plan_a3_hookean_solver.py
```

Result: PASS.

The A4 tests covered a non-vertex barycentric constraint on a triangular
spring network, redundant constraint-row detection, and a zero-rest Cartesian
spring. The A3 topology and solver regression tests also remained PASS.

## Stage B: preserved A2 failure

The original 753-vertex, 999-triangle, 110-landmark component was extracted
from the preserved A2 graph with:

```text
python scripts/extract_plan_a4_component.py --graph verification/plan-a2-hookean-run/female-spring-graph.npz --targets verification/plan-a2-hookean-run/female-targets.npz --component 7 --frame 2 --output verification/plan-a4-hookean-run/female-a2-component7.npz
python scripts/solve_plan_a4_projected_hookean.py --graph verification/plan-a4-hookean-run/female-a2-component7.npz --targets verification/plan-a4-hookean-run/female-a2-component7.npz --output verification/plan-a4-hookean-run/female-a2-component7-substeps-lsqr.json --substeps 5 --max-iterations 80 --inner-iterations 200 --force-tol 1e-5
```

Measured A4 result:

| Metric | A2/A3 baseline | A4 measured |
|---|---:|---:|
| Catastrophic update | approximately 238.10 proposed in A2 | no catastrophic update |
| Maximum accepted step | A3 0.00726 | 0.0003202 |
| Hard constraint residual | A3 approximately 2.08e-17 | 5.55e-17 |
| Normalized projected force residual | A3 4.62e-6 after 300 iterations | 3.98e-3 after 80 iterations at first staged target |
| Status | not converged | `max_iterations` |
| Runtime | — | 7.46 s |

The sparse projection fixes the runaway update and preserves the exact hard
targets. It does not yet reach the requested equilibrium criterion on this
regression component within the bounded iteration budget.

## A3 graph audit used for Stage C

| Quantity | Female | Male |
|---|---:|---:|
| Solver vertices | 10,318 | 90,599 |
| Solver triangles | 18,540 | 165,684 |
| Original edge springs | 28,910 | 256,195 |
| Virtual seam springs | 11 | 116 |
| Open-boundary edges | 2,200 | 15,338 |
| Nonmanifold edges | 0 | 0 |
| Simulation components after seams | 1 | 41 |
| Goal-1 attachments | 478 | 478 |

The male graph remains 41 simulation components. They were not indiscriminately
linked: A3's recorded normals, gaps, and anatomical component classifications
were preserved. The current one-component solve therefore cannot claim a full
male facial equilibrium.

## Stage C: full-face expressive frame

Frame 30 was selected from the existing target table because it has the largest
measured facial motion in the available sequence. Targets were not changed.

Female command:

```text
python scripts/solve_plan_a4_projected_hookean.py --graph verification/plan-a3-hookean-run/female-spring-graph-r010.npz --targets verification/plan-a3-hookean-run/female-targets-r010.npz --output verification/plan-a4-hookean-run/female-frame30-partial.json --frame 30 --substeps 1 --max-iterations 20 --inner-iterations 100 --force-tol 1e-4 --save-positions
```

Male command:

```text
python scripts/solve_plan_a4_projected_hookean.py --graph verification/plan-a3-hookean-run/male-spring-graph-r010.npz --targets verification/plan-a3-hookean-run/male-targets-r010.npz --output verification/plan-a4-hookean-run/male-frame30-partial.json --frame 30 --substeps 1 --max-iterations 5 --inner-iterations 50 --force-tol 1e-4 --save-positions
```

Female actual evaluated geometry, measured from the saved mesh state:

| Metric | Measured |
|---|---:|
| Defined targets checked | 478 |
| Maximum barycentric target error | 8.38e-17 model units, 1.50e-15 eye widths |
| Hard residual reported by solver | 7.63e-17 |
| Projected force residual | 71.08 characteristic-force units |
| Maximum edge extension | 15.293 |
| Maximum edge compression | -0.859 |
| P95 absolute edge strain | 0.847 |
| New inverted triangles | 1,118 |
| Collapsed triangles | 0 by the configured area threshold |
| Invalid coordinates | 0 |
| Runtime | 10.30 s |
| Solver status | `max_iterations` |

Male stopped after the first constrained component, so a complete 478-target
accuracy claim is not valid. The first component had 13,831 vertices and 1,233
hard-constraint rows. Its actual solver measurements were:

| Metric | Measured |
|---|---:|
| Hard residual on solved component | 1.11e-16 |
| Projected force residual | 251.89 characteristic-force units |
| Maximum accepted step | 0.04774 model units |
| New inverted triangles in full affected mesh state | 8,164 |
| Collapsed triangles | 0 by the configured area threshold |
| Invalid coordinates | 0 |
| Runtime | 16.53 s |
| Solver status | `max_iterations` |

The male result is partial by design: the solver stopped at the first failed
component and did not pretend that the remaining 40 components had reached
equilibrium.

## Render evidence

The actual saved states were baked over the untouched original GLBs and
rendered with Blender 5.2:

- Female neutral: `verification/plan-a4-hookean-run/female-frame30-render/neutral.png`
- Female A4 partial: `verification/plan-a4-hookean-run/female-frame30-render/a4-partial.png`
- Male neutral: `verification/plan-a4-hookean-run/male-frame30-render/neutral.png`
- Male A4 partial: `verification/plan-a4-hookean-run/male-frame30-render/a4-partial.png`

The female partial render shows hair and surrounding facial-region geometry
pulled into long spikes and the face is not a usable expression. The male
partial render shows severe radial spikes and broken facial appearance. These
are actual deformed original meshes, not marker-only previews.

## Decision

Stage A: PASS.
Stage B: FAILED to reach equilibrium, although the catastrophic A2 update was
successfully prevented.
Stage C female: FAILED due to extreme strain and 1,118 inversions.
Stage C male: FAILED during the first component with extreme residual and
8,164 inversions.
Stage D short sequence: NOT RUN.
Stage E complete 121-frame animation: NOT RUN.

The remaining blocker is not hard landmark enforcement. The projected solver
does enforce the barycentric targets accurately. The blocker is the combination
of the current anatomically over-inclusive A3 domains, stretching-only floppy
modes, and slow/nonconvergent equilibrium optimization. The rendered evidence
shows that satisfying the targets is not sufficient for a valid face.

Original GLBs were not modified. The full position NPZ files and verbose run
logs remain local under `verification/plan-a4-hookean-run` for inspection but
are intentionally excluded from the commit because they are large intermediates.
