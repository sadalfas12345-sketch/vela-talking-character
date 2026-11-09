# Gate 8 integrator repair report

## Scope

This report continues from commit `53eb930`. The biological preset, source mesh
coordinates, independent Tripo mesh islands, Hookean surface springs, fixed inner
anchors, controller gains, stiffnesses, and unlimited spring extension were kept
unchanged.

The implementation change is numerical only:

- The implicit residual is solved with nonlinear Newton iterations rather than
  the previous fixed eight updates.
- The surface-spring Jacobian sign was corrected to match
  `R(x) = x - x_n - dt*v_n - dt^2*a(x)`.
- A preconditioned matrix-free CG solve is used for the Newton position update.
- Actual residual history and stagnation status are recorded.
- The nonlinear solve uses a finer backtracking floor and expanded iteration
  budgets. These are numerical solve controls, not physical force or stretch
  limits.

## Small-network comparison

Command:

```powershell
node scripts/test_pinch_physics.mjs
```

The production implicit oscillator and fine RK4 use identical initial position,
velocity, force law, stiffness, mass, damping, and duration.

| Measurement | Production implicit | Fine RK4 | Result |
|---|---:|---:|---|
| Duration | 0.05 s | 0.05 s | same |
| Time step | 8.333333333333333e-5 s | 1e-6 s | — |
| Final position | 0.0009611502848824991 | 0.0009585949655717950 | error 2.5553193107040765e-6 |
| Final velocity | 0.01503770436386484 | 0.01661324613064132 | recorded |
| Maximum production equation residual | 1.0874116332622102e-19 | — | converged |
| Acceptance tolerance | 2e-5 source units | — | PASS |

All six deterministic tests in
`verification/island-spring-pinch/physics-unit-tests.json` pass, including the
production-versus-RK4 comparison.

## Real Tripo evidence

The numerical values below are the completed real-mesh evidence from the
Jacobian-sign correction before the final iteration-budget expansion. The
expanded `32` Newton / `256` CG budget passed the deterministic small-network
tests but was not completed on both real models before the bounded browser run
was stopped; it must not be treated as validated Gate 8 evidence.

The corrected surface-Jacobian sign was exercised on the original female and
male GLB islands. Gate 6 passed for both models with finite positions, neighbor
movement, energy reduction, and zero geometry defects.

Female Gate 6 selected island:

- 5,036 vertices, 9,708 triangles, 14,743 unique surface springs.
- 0 nonfinite vertices, 0 collapsed triangles, 0 orientation flips.
- 30-step nudge recovery reduced energy from `2.2975665975483107e-8` to
  `2.3770161065897223e-14`.
- Implicit status: `converged`; residual history
  `[2.162062209714899e-4, 1.8184706602824378e-8]`.

Male Gate 6 selected island:

- 41,920 vertices, 82,807 triangles, 124,726 unique surface springs.
- 0 nonfinite vertices, 0 collapsed triangles, 0 orientation flips.
- 30-step nudge recovery reduced energy from `6.178612127685309e-7` to
  `1.9835408601182503e-13`.
- Implicit status: `converged`; residual history
  `[4.396468154683447e-5, 1.0976826763559953e-8]`.

## Gate 8 failure mechanism

The female held pinch solve converged and geometry remained valid:

- Implicit status: `converged`.
- Residual history:
  `[4.3357141394727164e-4, 4.29270954946407e-7,
  1.4133171588322813e-7, 5.52984048379291e-8,
  9.74174345267269e-9]`.
- 0 nonfinite vertices, 0 collapsed triangles, 0 orientation flips.
- Minimum triangle area ratio `0.9373759712692219`.
- Maximum edge strain `0.10339098050230647`.

The female release geometry remained finite and non-inverted, but the release
implicit equation did not converge:

- Status: `stagnated`.
- Residual history:
  `[1.0894307831108851, 0.09367960003927775,
  0.08638936282530495, 0.021898223838215092,
  0.00960729764785155, 0.0020458827236315056,
  0.001955580037966881]`.
- Final equation residual: `0.31289280607470094` after the production
  normalization by `dt`.
- Geometry at the captured release readback: 0 nonfinite vertices, 0 collapsed
  triangles, 0 orientation flips, minimum area ratio `0.9899170382150145`.

Therefore this is a numerical convergence failure, not a false-positive triangle
classification.

The first corrected browser run reached the male held state and wrote
`male-gate7-held.png`, but the document screenshot call timed out before the
release diagnostics were assigned to the report. A follow-up diagnostics-only
run passed male Gate 6 but did not finish the male held/release readback within
the bounded execution window. No male release result is claimed.

## Gate status

| Gate | Result | Evidence |
|---|---|---|
| Small-network physical-unit and integrator tests | PASS | `physics-unit-tests.json` |
| Gate 6 actual-island response | PASS | `browser-mathematical-gates.json` |
| Gate 7 barycentric controller | PASS for the recorded female interaction; male release readback not retained | browser report and force-distribution telemetry |
| Gate 8 held/released original-face validation | **FAIL** | Female release stagnation; male release not completed |

## Reproduction

```powershell
node scripts/test_pinch_physics.mjs
node scripts/run_physics_gates.mjs
node scripts/run_browser_physics_gates.mjs
```

The browser run is intentionally not reported as successful unless both held
and released states have converged implicit solves and valid original-mesh
geometry on both characters.

## Conclusion

The Jacobian-sign defect is fixed and the small-network comparison passes, but
Gate 8 remains FAILED. The remaining blocker is the real-mesh release solve:
the female release step stagnates at a nonzero equation residual, and the male
release readback is incomplete. No material coefficient or controller gain was
changed, and no new physical mechanism was introduced.
