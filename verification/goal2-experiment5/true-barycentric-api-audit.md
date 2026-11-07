# True barycentric constraint API audit

## Existing two-landmark failure

The preserved old vertex-handle result is `two-landmark-baseline-extension/results-2.json`:

- Female: landmark 70 error 2.072%, landmark 105 error 22.484%, 11 orientation failures, 61.96% maximum edge strain.
- Male: landmark 70 error 9.619%, landmark 105 error 0.348%, 21 orientation failures, 324.58% maximum edge strain.

This is the baseline failure to replace. The original Goal-1 barycentric attachments and target trajectories were not changed.

## Installed libigl API

The installed Python binding exposes:

- `igl.arap_precomputation(V, F, dim, b, data)`
- `igl.arap_solve(bc, data, U)`
- `igl.min_quad_with_fixed(...)`
- `igl.min_quad_with_fixed_precompute(...)`
- `igl.min_quad_with_fixed_solve(...)`

`arap_solve` accepts `bc`, a matrix of positions for fixed vertex handles. It does not accept a sparse equality matrix such as:

```text
w70_A V_A + w70_B V_B + w70_C V_C = target70
w105_D V_D + w105_E V_E + w105_F V_F = target105
```

`ARAPData` exposes only `G`, `energy`, `f_ext`, `h`, `max_iter`, `n`, `vel`, `with_dynamics`, and `ym`. It does not expose the local rotations or the global position-update matrix/right-hand side needed to insert `Aeq` into each ARAP iteration.

`igl.min_quad_with_fixed` can solve a sparse equality-constrained quadratic problem, but using it here would require reconstructing libigl's ARAP local-rotation update and matrix assembly outside the official `arap_solve` implementation. That would be a reimplementation of the ARAP solver, which this task explicitly forbids.

## Official C++ source cross-check

The official C++ implementation confirms that `arap_solve` performs a local/global
iteration and calls `min_quad_with_fixed_solve` for each coordinate column. Its
`ARAPData` contains the internal quadratic-solver state, but the Python binding
does not expose that state or the position-update matrix.

Therefore, a native bridge could theoretically preserve the official ARAP local
rotation and solve loop while replacing only the internal equality-constrained
quadratic precomputation. That bridge is not present in this checkout, and this
runtime has no C or C++ compiler available to build one. Constructing the ARAP
position-update loop in Python would still be a prohibited reimplementation.

## Decision

The exact requested true-barycentric integration is not available through the
installed official Python API. The remaining technically valid path is an
official-source native bridge that preserves `arap_solve` and exposes the
constrained internal position update. No custom ARAP reimplementation was
introduced, and no false claim that `arap_solve` supports barycentric constraints
was made.

Reproducible audit command:

```powershell
python scripts/audit_libigl_barycentric_constraint_support.py
```

The correct next action requires either an official libigl API that exposes constrained ARAP position updates or authorization to use a different established solver/API. The two-landmark experiment is stopped here.
