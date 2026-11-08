# Plan A3 Hookean solver repair report

Branch: `wip/tripo-face-repair`  
Baseline: Plan A2 commit `d514dbe120ba346109a17f8d96ebd81a088c7c55`

## Result

**OVERALL STEP RESULT: FAILED**

Stage A passed and Stage B reproduced the A2 numerical mechanism without the
catastrophic update. The corrected solver still did not reach the required
projected-force equilibrium on the preserved failure block within the tested
budget. The larger connected-face Stage C run was not completed because sparse
KKT factorization and the first matrix-free trial exceeded a bounded diagnostic
runtime. No full 121-frame A3 animation is claimed.

## Stage A: topology regression

The original bug was confirmed in `build_plan_a2_spring_graph.py`: edge counts
were computed after `np.unique`, so every edge had multiplicity one. The fix
counts the undirected triangle-edge multiset first, then separately reports
ordinary interior, open-boundary, and nonmanifold edges.

Regression command:

```text
py scripts/test_plan_a3_topology.py
```

Result: **PASS**. The suite covers two triangles sharing an edge, a closed
tetrahedron, two disconnected open patches, and coincident surfaces with
different vertex identities. Coincidence does not create a topological link.

## Corrected domain and graph measurements

The first A3 domain comparison uses a 0.10 interocular-width geodesic radius
with the original vertices and triangles retained in memory. The source GLBs
were not modified.

| Metric | Female | Male |
|---|---:|---:|
| Simulation vertices | 10,318 | 90,599 |
| Simulation triangles | 18,540 | 165,684 |
| Original topology components | 7 | 135 |
| Original edge springs | 28,910 | 256,195 |
| Open-boundary edges | 2,200 | 15,338 |
| Nonmanifold edges | 0 | 0 |
| Virtual seam springs | 11 | 116 |
| Components after virtual links | 1 | 41 |

This is a real improvement over A2's false boundary classification, but the
male domain still has 41 simulation components. The current evidence does not
justify indiscriminate proximity links across those remaining surfaces.

## Stage B: preserved A2 failure

The original A2 graph and target files were used unchanged for this regression.
The failing component's landmark constraint matrix has 525 rows and singular
values from `1.1110` to `0.07084`, condition number approximately `15.68`.
Therefore the catastrophic update was not caused by a rank-deficient landmark
matrix.

The stiffness update was ill-conditioned because stretching-only surface edges
have floppy modes. The old `1e-12` diagonal allowed the KKT solve to select an
enormous null-mode update. A3 adds:

- independent-row reduction for redundant barycentric and gauge rows;
- minimal rigid-mode gauges only when landmarks do not determine them;
- zero-rest springs as Cartesian Hookean residuals;
- numerical Levenberg–Marquardt damping for the linear solve;
- nonlinear merit line search;
- projected-force residual convergence checks;
- sparse matrix-free LSQR support for large blocks.

The damping is numerical step control only. It is not a physical spring,
support stiffness, stretch limit, or force cap.

### Preserved failure comparison

| Measurement | A2 behavior | A3 bounded result |
|---|---:|---:|
| First regression frame | 2, substep 10 | 1, substep 1 in the preserved block |
| Maximum proposed/accepted update | ~238.10 proposed | 0.00726 maximum accepted |
| Hard landmark residual | ~1.08e-9 at failure | 2.08e-17 |
| Projected spring residual | 124.84 | 9.46e-6 after 80 iterations; 4.62e-6 after 300 |
| Status | catastrophic update | bounded but not converged |

The A3 result removes the confirmed catastrophic numerical update, but it does
not yet satisfy the equilibrium criterion. The residual decline is too slow for
the current implementation and budget.

The LSQR variant on the same preserved graph reached hard residual
`4.08e-16` and projected residual `1.95e-6` after 100 iterations, with maximum
accepted update `1.78e-4`. It also did not meet the strict `1e-8` projected-force
criterion.

## Gauge audit

The solver no longer adds six gauge rows unconditionally. It computes the rank
of the landmark constraints on the six rigid-motion modes and adds only a
complementary subset. In the preserved failing component, the landmark
constraints already had rigid rank six, so zero extra gauge rows were added.

This prevents a numerical gauge from restricting legitimate facial motion while
still removing rigid null modes where necessary.

## Stage C status

A corrected 0.10-IPD female graph was constructed and a sparse direct solve was
started. Its KKT factorization did not finish in the bounded diagnostic window.
A matrix-free LSQR trial was then started and stopped after the same bounded
window without a result file. The male full-domain run was not started.

This is a computational completion failure, not evidence that the corrected
Hookean model has passed or failed physically on the larger domain. Because
Stage B did not reach equilibrium, the full 121-frame batch was correctly not
started.

## Preserved restrictions

- Original female and male GLBs were not modified.
- No bending, volume, support, ARAP, bone, morph, or stretch/force cap was added.
- Existing 121-frame target data and explicit zero-depth assumption were reused.
- Existing A1 and A2 evidence remains unchanged.
- No production GLB or full animation export was created.

## Reproduction

```text
py scripts/test_plan_a3_topology.py
py scripts/test_plan_a3_hookean_solver.py
py scripts/build_plan_a2_spring_graph.py --patch verification/plan-a-hookean-run/female-patch.npz --goal1 verification/plan-a2-hookean-run/female-original-attachments.json --output verification/plan-a3-hookean-run/female-spring-graph-r010.json
py scripts/build_plan_a2_spring_graph.py --patch verification/plan-a-hookean-run/male-patch.npz --goal1 verification/plan-a2-hookean-run/male-original-attachments.json --output verification/plan-a3-hookean-run/male-spring-graph-r010.json
py scripts/solve_plan_a2_hookean.py --graph verification/plan-a2-hookean-run/female-spring-graph.npz --targets verification/plan-a2-hookean-run/female-targets.npz --output verification/plan-a3-hookean-run/female-a2-regression-300.json --max-frames 3 --substeps 20 --max-iterations 300 --linear-damping 1e-6
```

## Final assessment

- Boundary correctness: **PASS**.
- Unit tests: **PASS**.
- Catastrophic A2 update prevention: **PASS**.
- Exact hard-target handling: **PASS on the tested regression path**.
- Stable nonlinear equilibrium: **FAIL**.
- Full connected-face Stage C: **NOT COMPLETED**.
- Full 121-frame female/male animation: **NOT RUN**.
- Visual animation validation: **NOT RUN**.

The remaining blocker is a slow or poorly conditioned equilibrium solve for a
stretching-only surface with many floppy modes. The next correction should
focus on a scalable constrained null-space or preconditioned equilibrium solve,
not on changing the facial physics or target trajectories.

**OVERALL STEP RESULT: FAILED**
